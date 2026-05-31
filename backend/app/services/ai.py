from __future__ import annotations

import json
from typing import Any, Dict, List

from groq import Groq

from app.config import settings
from app.exceptions import AIServiceError
from app.logging import get_logger

logger = get_logger(__name__)


class AIService:
    def __init__(self) -> None:
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

    def _log_usage(self, response: Any, action: str) -> None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info("AI %s usage: %s", action, usage)

    def generate_repo_summary(self, repo_name: str, file_list: List[str]) -> str:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

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
            self._log_usage(response, "repo summary")
            return summary
        except Exception as exc:
            raise AIServiceError(str(exc)) from exc

    def analyze_file(self, file_path: str, content: str) -> Dict[str, str]:
        if not self.client:
            raise AIServiceError("GROQ_API_KEY not configured")

        snippet = "\n".join(content.splitlines()[:200])
        prompt = (
            "Analyze the following source file and return only a JSON object with keys: summary, complexity, role. "
            "summary should be 1-2 sentences, complexity should be one of low/medium/high, role should be one of: "
            "entry_point, api_router, data_model, service, utility, config, test, static, unknown. "
            f"File: {file_path}. Content:\n{snippet}"
        )

        logger.info("Sending file analysis prompt to Groq for %s", file_path)
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.5,
            )
            raw_text = response.choices[0].message.content.strip()
            self._log_usage(response, "file analysis")
            parsed = json.loads(raw_text)

            if not all(key in parsed for key in ("summary", "complexity", "role")):
                raise AIServiceError("Groq response JSON is missing required keys")

            return {
                "summary": str(parsed["summary"]),
                "complexity": str(parsed["complexity"]),
                "role": str(parsed["role"]),
            }
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"Invalid JSON returned from AI: {exc}") from exc
        except Exception as exc:
            raise AIServiceError(str(exc)) from exc
