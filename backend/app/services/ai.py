from __future__ import annotations

import json
import time
from typing import Dict, List

from groq import Groq

from app.config import settings
from app.exceptions import AIServiceError
from app.logging import get_logger

logger = get_logger(__name__)


class AIService:
    def __init__(self, hourly_limit: int | None = None, daily_limit: int | None = None) -> None:
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.hourly_limit = hourly_limit if hourly_limit is not None else settings.AI_MAX_REQUESTS_PER_HOUR
        self.daily_limit = daily_limit if daily_limit is not None else settings.AI_MAX_REQUESTS_PER_DAY
        self._hourly_usage: list[float] = []
        self._daily_usage: list[float] = []

    def ensure_budget_available(self) -> None:
        now = time.time()
        self._hourly_usage = [ts for ts in self._hourly_usage if now - ts < 3600]
        self._daily_usage = [ts for ts in self._daily_usage if now - ts < 86400]

        if len(self._hourly_usage) >= self.hourly_limit:
            raise AIServiceError("AI request hourly budget exceeded")
        if len(self._daily_usage) >= self.daily_limit:
            raise AIServiceError("AI request daily budget exceeded")

        self._hourly_usage.append(now)
        self._daily_usage.append(now)

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
                model="llama-3.3-70b-versatile",
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
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": (
                "Analyze the following source file and return ONLY a JSON object with exactly these keys: "
                "summary, complexity, role. "
                "summary: 1-2 sentences. "
                "complexity: one of low/medium/high. "
                "role: one of entry_point/api_router/data_model/service/utility/config/test/static/unknown. "
                "Return nothing else — no markdown, no explanation, just the JSON object. "
                f"File: {file_path}. Content:\n{snippet}"
            )}],
            max_tokens=300,
            temperature=0.3,
        )
        raw_text = response.choices[0].message.content.strip()
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info("AI file analysis usage: %s", usage)

        if not raw_text.startswith("{"):
            raise Exception("rate_limit: " + raw_text[:120])

        parsed = json.loads(raw_text)

        if not all(key in parsed for key in ("summary", "complexity", "role")):
            raise Exception("missing_keys: " + str(list(parsed.keys())))

        return {
            "summary": str(parsed["summary"]),
            "complexity": str(parsed["complexity"]),
            "role": str(parsed["role"]),
        }

    def analyze_file(self, file_path: str, content: str) -> Dict[str, str]:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        self.ensure_budget_available()

        snippet = "\n".join(content.splitlines()[:200])
        wait_times = [20, 60]
        last_exc: Exception = Exception("unknown error")

        logger.info("Sending file analysis prompt to Groq for %s", file_path)

        for attempt in range(3):
            try:
                return self._call_analyze_file(file_path, snippet)
            except Exception as exc:
                last_exc = exc
                err = str(exc).lower()
                is_rate_limit = "429" in err or "rate_limit" in err or "rate limit" in err

                if not is_rate_limit or attempt == 2:
                    raise AIServiceError(str(exc)) from exc

                wait = wait_times[attempt]
                logger.warning("Groq rate limit hit for %s, waiting %ss before retry", file_path, wait)
                time.sleep(wait)

        raise AIServiceError(str(last_exc))