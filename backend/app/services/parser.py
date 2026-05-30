from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from app.logging import get_logger

logger = get_logger(__name__)
PYTHON_STDLIB = {
    "os",
    "sys",
    "re",
    "json",
    "datetime",
    "pathlib",
    "typing",
    "collections",
    "itertools",
    "math",
    "random",
    "logging",
    "functools",
    "subprocess",
    "asyncio",
    "http",
    "time",
    "dataclasses",
}


class CodeParser:
    def parse(self, file_path: str, content: str) -> dict:
        extension = Path(file_path).suffix.lower()
        line_count = content.count("\n") + (0 if content == "" else 1)

        if extension == ".py":
            language = "python"
            imports = self._parse_python(content)
        elif extension in {".js", ".jsx", ".ts", ".tsx"}:
            language = "javascript"
            imports = self._parse_js_ts(content)
        elif extension == ".html":
            language = "html"
            imports = self._parse_html(content)
        elif extension == ".css":
            language = "css"
            imports = self._parse_css(content)
        elif extension == ".md":
            language = "markdown"
            imports = []
        else:
            language = "text"
            imports = []

        logger.debug("Parsed %s -> %s imports", file_path, len(imports))

        return {
            "language": language,
            "line_count": line_count,
            "imports": imports,
        }

    def _parse_python(self, content: str) -> list[str]:
        imports: list[str] = []
        pattern = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+(.+))", re.MULTILINE)

        for match in pattern.finditer(content):
            module = match.group(1) or match.group(2) or ""
            module = module.strip()
            if not module:
                continue

            if match.group(1):
                if module.startswith("."):
                    imports.append(module)
                    continue
                root = module.split(".")[0]
                if root in PYTHON_STDLIB:
                    continue
                imports.append(module)
                continue

            for token in module.split(","):
                token = token.strip().split(" ")[0]
                if not token or token.startswith("."):
                    imports.append(token)
                    continue

                root = token.split(".")[0]
                if root in PYTHON_STDLIB:
                    continue
                imports.append(token)

        return list(dict.fromkeys([item for item in imports if item]))

    def _parse_js_ts(self, content: str) -> list[str]:
        imports: list[str] = []
        patterns = [
            re.compile(r"from\s+[\'\"]([^\'\"]+)[\'\"]"),
            re.compile(r"import\s+[\'\"]([^\'\"]+)[\'\"]"),
            re.compile(r"require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)"),
        ]

        for pattern in patterns:
            for match in pattern.finditer(content):
                source = match.group(1).strip()
                if source:
                    imports.append(source)

        return list(dict.fromkeys(imports))

    def _parse_html(self, content: str) -> list[str]:
        imports: list[str] = []
        script_pattern = re.compile(r"<script[^>]+src=[\'\"]([^\'\"]+)[\'\"]", re.IGNORECASE)
        link_pattern = re.compile(r"<link[^>]+href=[\'\"]([^\'\"]+)[\'\"]", re.IGNORECASE)

        for match in script_pattern.finditer(content):
            imports.append(match.group(1).strip())

        for match in link_pattern.finditer(content):
            imports.append(match.group(1).strip())

        return list(dict.fromkeys([value for value in imports if value]))

    def _parse_css(self, content: str) -> list[str]:
        imports: list[str] = []
        pattern = re.compile(r"@import\s+(?:url\()?['\"]([^'\"]+)['\"]\)?;?", re.IGNORECASE)

        for match in pattern.finditer(content):
            imports.append(match.group(1).strip())

        return list(dict.fromkeys([value for value in imports if value]))
