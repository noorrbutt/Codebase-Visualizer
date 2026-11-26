from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from app.logging import get_logger

logger = get_logger(__name__)
PYTHON_STDLIB = sys.stdlib_module_names


class CodeParser:
    def parse(self, file_path: str, content: str) -> dict:
        extension = Path(file_path).suffix.lower()
        line_count = content.count("\n") + (0 if content == "" else 1)

        if extension == ".py":
            language = "python"
            imports = self._parse_python(content)
        elif extension in {".ts", ".tsx"}:
            language = "typescript"
            imports = self._parse_js_ts(content)
        elif extension in {".js", ".jsx"}:
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

        logger.debug("Parsed {} -> {} imports", file_path, len(imports))

        return {
            "language": language,
            "line_count": line_count,
            "imports": imports,
        }

    def _parse_python(self, content: str) -> list[str]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._parse_python_regex(content)

        imports: list[str] = []
        import_nodes = sorted(
            (node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for node in import_nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module.split(".")[0] not in PYTHON_STDLIB:
                        imports.append(module)
                continue

            module = "." * node.level + (node.module or "")
            if not module.startswith(".") and module.split(".")[0] in PYTHON_STDLIB:
                continue
            if module:
                imports.append(module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                submodule = (
                    f"{module}{alias.name}"
                    if module.endswith(".")
                    else f"{module}.{alias.name}"
                    if module
                    else alias.name
                )
                imports.append(submodule)

        return list(dict.fromkeys(item for item in imports if item))

    def _parse_python_regex(self, content: str) -> list[str]:
        imports: list[str] = []
        pattern = re.compile(
            r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import\s+([^\r\n]+)|import\s+(.+))",
            re.MULTILINE,
        )

        for match in pattern.finditer(content):
            module = (match.group(1) or match.group(3) or "").strip()
            if not module:
                continue

            if not match.group(1):
                for token in module.split(","):
                    token = token.strip().split(" ")[0]
                    if not token or token.startswith("."):
                        imports.append(token)
                        continue

                    root = token.split(".")[0]
                    if root not in PYTHON_STDLIB:
                        imports.append(token)
                continue

            if not module.startswith(".") and module.split(".")[0] in PYTHON_STDLIB:
                continue
            imports.append(module)
            imported_names = match.group(2).split("#", 1)[0].strip().strip("()")
            for name in imported_names.split(","):
                name = name.strip().split(" as ")[0].strip()
                if name and name != "*":
                    imports.append(
                        f"{module}{name}" if module.endswith(".") else f"{module}.{name}"
                    )

        return list(dict.fromkeys([item for item in imports if item]))

    def _parse_js_ts(self, content: str) -> list[str]:
        imports: list[str] = []
        content = self._strip_js_comments(content)
        patterns = [
            re.compile(r"from\s+[\'\"]([^\'\"]+)[\'\"]"),
            re.compile(r"import\s+[\'\"]([^\'\"]+)[\'\"]"),
            re.compile(r"require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)"),
            re.compile(r"\bimport\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)"),
        ]

        for pattern in patterns:
            for match in pattern.finditer(content):
                source = match.group(1).strip()
                if source:
                    imports.append(source)

        return list(dict.fromkeys(imports))

    def _strip_js_comments(self, content: str) -> str:
        result: list[str] = []
        index = 0
        quote: str | None = None
        while index < len(content):
            char = content[index]

            if quote is not None:
                result.append(char)
                if char == "\\" and index + 1 < len(content):
                    index += 1
                    result.append(content[index])
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char in {"'", '"', "`"}:
                quote = char
                result.append(char)
                index += 1
                continue

            if content.startswith("//", index):
                while index < len(content) and content[index] not in "\r\n":
                    result.append(" ")
                    index += 1
                continue

            if content.startswith("/*", index):
                result.extend((" ", " "))
                index += 2
                while index < len(content) and not content.startswith("*/", index):
                    result.append("\n" if content[index] == "\n" else " ")
                    index += 1
                if index < len(content):
                    result.extend((" ", " "))
                    index += 2
                continue

            result.append(char)
            index += 1

        return "".join(result)

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
