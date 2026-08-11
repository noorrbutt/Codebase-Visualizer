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
    def __init__(
        self,
        hourly_limit: int | None = None,
        daily_limit: int | None = None,
        client_hourly_limit: int | None = None,
        client_daily_limit: int | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.hourly_limit = hourly_limit if hourly_limit is not None else settings.AI_MAX_REQUESTS_PER_HOUR
        self.daily_limit = daily_limit if daily_limit is not None else settings.AI_MAX_REQUESTS_PER_DAY
        self.client_hourly_limit = (
            client_hourly_limit if client_hourly_limit is not None else settings.AI_MAX_CLIENT_REQUESTS_PER_HOUR
        )
        self.client_daily_limit = (
            client_daily_limit if client_daily_limit is not None else settings.AI_MAX_CLIENT_REQUESTS_PER_DAY
        )
        self._redis_client = redis_client

    def _get_redis_client(self) -> Redis:
        return self._redis_client or get_redis_client()

    def ensure_budget_available(self, client_ip: str | None = None) -> None:
        redis_client = self._get_redis_client()
        client_identifier = client_ip or "unknown"

        hourly_key = "ai_budget:hourly"
        daily_key = "ai_budget:daily"
        client_hourly_key = f"ai_budget:hourly:{client_identifier}"
        client_daily_key = f"ai_budget:daily:{client_identifier}"

        hourly_count = int(redis_client.incr(hourly_key))
        if hourly_count == 1:
            redis_client.expire(hourly_key, 3600)

        daily_count = int(redis_client.incr(daily_key))
        if daily_count == 1:
            redis_client.expire(daily_key, 86400)

        client_hourly_count = int(redis_client.incr(client_hourly_key))
        if client_hourly_count == 1:
            redis_client.expire(client_hourly_key, 3600)

        client_daily_count = int(redis_client.incr(client_daily_key))
        if client_daily_count == 1:
            redis_client.expire(client_daily_key, 86400)

        if hourly_count > self.hourly_limit:
            logger.warning(
                "AI hourly budget exceeded for client {}: global_hourly={} limit={}",
                client_identifier,
                hourly_count,
                self.hourly_limit,
            )
            raise AIServiceError("AI request hourly budget exceeded")
        if daily_count > self.daily_limit:
            logger.warning(
                "AI daily budget exceeded for client {}: global_daily={} limit={}",
                client_identifier,
                daily_count,
                self.daily_limit,
            )
            raise AIServiceError("AI request daily budget exceeded")
        if client_hourly_count > self.client_hourly_limit:
            logger.warning(
                "AI hourly client budget exceeded for client {}: client_hourly={} limit={}",
                client_identifier,
                client_hourly_count,
                self.client_hourly_limit,
            )
            raise AIServiceError(f"AI request hourly client budget exceeded for {client_identifier}")
        if client_daily_count > self.client_daily_limit:
            logger.warning(
                "AI daily client budget exceeded for client {}: client_daily={} limit={}",
                client_identifier,
                client_daily_count,
                self.client_daily_limit,
            )
            raise AIServiceError(f"AI request daily client budget exceeded for {client_identifier}")

    def generate_repo_summary(
        self,
        repo_name: str,
        file_list: List[str],
        client_ip: str | None = None,
    ) -> str:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        self.ensure_budget_available(client_ip=client_ip)

        prompt = (
            "Write a 2-3 sentence plain-English summary as a senior developer explaining this repository to a teammate. "
            "Cover what the project does, the main technology or framework, and the core modules or areas of responsibility. "
            f"Base it only on the repository name and file structure: {repo_name}, files: {', '.join(file_list[:50])}. "
            "Keep it factual and under 60 words."
        )

        logger.info("Sending repo summary prompt to Groq for {}", repo_name)
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
                logger.info("AI repo summary usage: {}", usage)
            return summary
        except Exception as exc:
            raise AIServiceError(str(exc)) from exc

    def _call_analyze_file(self, file_path: str, snippet: str) -> Dict[str, str]:
        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": (
                "Analyze the following source file and return ONLY a JSON object with exactly these keys: "
                "summary, summary_detail, complexity, role. "
                "summary: 2 sentences, plain-English, what this file does. "
                "summary_detail: exactly 3 sentences, no more, covering key functions/classes, how this file connects to other parts of the codebase, and any notable complexity or design choices. "
                "complexity: one of low/medium/high. "
                "role: one of entry_point/api_router/data_model/service/utility/config/test/static/unknown. "
                "Return nothing else — no markdown, no explanation, just the JSON object. "
                f"File: {file_path}. Content:\n{snippet}"
            )}],
            response_format={"type": "json_object"},
            max_tokens=900,
            temperature=0.3,
        )
        raw_text = response.choices[0].message.content.strip()
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info("AI file analysis usage: {}", usage)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise Exception("invalid_json: " + raw_text[:120]) from exc

        if not all(key in parsed for key in ("summary", "summary_detail", "complexity", "role")):
            raise Exception("missing_keys: " + str(list(parsed.keys())))

        return {
            "summary": str(parsed["summary"]),
            "summary_detail": str(parsed["summary_detail"]),
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

    def _is_json_validate_error(self, exc: Exception) -> bool:
        # Some Groq errors surface as exceptions with a `body` attribute
        # containing {'error': {'code': 'json_validate_failed'}}. Others
        # may include the code in the text message. Treat these as
        # retryable so a truncated JSON can be retried.
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            code = body.get("error", {}).get("code")
            if code == "json_validate_failed":
                return True

        msg = str(exc)
        if "json_validate_failed" in msg or "json_validate" in msg:
            return True

        return False

    async def analyze_file(
        self,
        file_path: str,
        content: str,
        timeout_seconds: float = 30.0,
        client_ip: str | None = None,
    ) -> Dict[str, str]:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        self.ensure_budget_available(client_ip=client_ip)

        snippet = "\n".join(content.splitlines()[:200])
        last_exc: Exception = Exception("unknown error")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds

        logger.info("Sending file analysis prompt to Groq for {}", file_path)

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
                retryable = self._is_retryable_rate_limit_error(exc) or self._is_json_validate_error(exc)
                if not retryable or attempt == 2:
                    raise AIServiceError(str(exc)) from exc

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise AIServiceError(f"AI file analysis timed out after {timeout_seconds}s")

            wait = min(2.0, remaining)
            logger.warning("Groq rate limit hit for {}, waiting {:.1f}s before retry", file_path, wait)
            await asyncio.sleep(wait)

        raise AIServiceError(str(last_exc))