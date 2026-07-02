from __future__ import annotations

import asyncio
import json
from typing import Dict, List

from groq import Groq
from redis import Redis

from app.config import settings
from app.exceptions import AIServiceError
from app.logging import get_logger
from app.services.redis_client import get_redis_client

logger = get_logger(__name__)

GROQ_MODEL = "openai/gpt-oss-120b"


class AIService:
    def __init__(self, hourly_limit: int | None = None, daily_limit: int | None = None, redis_client: Redis | None = None) -> None:
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.hourly_limit = hourly_limit if hourly_limit is not None else settings.AI_MAX_REQUESTS_PER_HOUR
        self.daily_limit = daily_limit if daily_limit is not None else settings.AI_MAX_REQUESTS_PER_DAY
        self._redis_client = redis_client

    def _get_redis_client(self) -> Redis:
        return self._redis_client or get_redis_client()

    def ensure_budget_available(self) -> None:
        redis_client = self._get_redis_client()

        hourly_key = "ai_budget:hourly"
        daily_key = "ai_budget:daily"

        hourly_count = int(redis_client.incr(hourly_key))
        if hourly_count == 1:
            redis_client.expire(hourly_key, 3600)

        daily_count = int(redis_client.incr(daily_key))
        if daily_count == 1:
            redis_client.expire(daily_key, 86400)

        if hourly_count > self.hourly_limit:
            raise AIServiceError("AI request hourly budget exceeded")
        if daily_count > self.daily_limit:
            raise AIServiceError("AI request daily budget exceeded")

    def generate_repo_summary(self, repo_name: str, file_list: List[str]) -> str:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        self.ensure_budget_available()

        prompt = (
            "Write a 2-3 sentence plain-English summary as a senior developer explaining this repository to a teammate. "
            "Cover what the project does, the main technology or framework, and the core modules or areas of responsibility. "
            f"Base it only on the repository name and file structure: {repo_name}, files: {', '.join(file_list[:50])}. "
            "Keep it factual and under 60 words."
        )

        logger.info("Sending repo summary prompt to Groq for %s", repo_name)
        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            summary = response.choices[0].message.content.strip()
            usage = getattr(response, "usage", None)
            if usage is not None:
                logger.info("AI repo summary usage: %s", usage)
            return summary
        except Exception as exc:
            raise AIServiceError(str(exc)) from exc

    def _call_analyze_file(self, file_path: str, snippet: str) -> Dict[str, str]:
        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": (
                "Analyze the following source file and return ONLY a JSON object with exactly these keys: "
                "summary, complexity, role. "
                "summary: 1-2 sentences. "
                "complexity: one of low/medium/high. "
                "role: one of entry_point/api_router/data_model/service/utility/config/test/static/unknown. "
                "Return nothing else — no markdown, no explanation, just the JSON object. "
                f"File: {file_path}. Content:\n{snippet}"
            )}],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0.3,
        )
        raw_text = response.choices[0].message.content.strip()
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info("AI file analysis usage: %s", usage)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise Exception("invalid_json: " + raw_text[:120]) from exc

        if not all(key in parsed for key in ("summary", "complexity", "role")):
            raise Exception("missing_keys: " + str(list(parsed.keys())))

        return {
            "summary": str(parsed["summary"]),
            "complexity": str(parsed["complexity"]),
            "role": str(parsed["role"]),
        }

    @staticmethod
    def _is_retryable_rate_limit_error(exc: Exception) -> bool:
        if exc.__class__.__name__ == "RateLimitError":
            return True

        if getattr(exc, "status_code", None) == 429:
            return True

        response = getattr(exc, "response", None)
        if getattr(response, "status_code", None) == 429:
            return True

        return False

    async def analyze_file(self, file_path: str, content: str, timeout_seconds: float = 30.0) -> Dict[str, str]:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        self.ensure_budget_available()

        snippet = "\n".join(content.splitlines()[:200])
        last_exc: Exception = Exception("unknown error")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds

        logger.info("Sending file analysis prompt to Groq for %s", file_path)

        for attempt in range(3):
            try:
                remaining = max(0.1, deadline - loop.time())
                return await asyncio.wait_for(
                    asyncio.to_thread(self._call_analyze_file, file_path, snippet),
                    timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                last_exc = exc
                if deadline <= loop.time():
                    raise AIServiceError(f"AI file analysis timed out after {timeout_seconds}s") from exc
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable_rate_limit_error(exc) or attempt == 2:
                    raise AIServiceError(str(exc)) from exc

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise AIServiceError(f"AI file analysis timed out after {timeout_seconds}s")

            wait = min(2.0, remaining)
            logger.warning("Groq rate limit hit for %s, waiting %.1fs before retry", file_path, wait)
            await asyncio.sleep(wait)

        raise AIServiceError(str(last_exc))