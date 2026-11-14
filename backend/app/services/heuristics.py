from __future__ import annotations

from pathlib import PurePosixPath


_ENTRY_POINTS = {"main.py", "app.py", "index.js", "main.jsx", "server.js"}


def infer_file_role(path: str) -> str:
    normalized = path.lower().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    basename = parts[-1] if parts else ""

    if (
        any(part in {"test", "tests", "__tests__"} for part in parts[:-1])
        or basename.startswith("test_")
        or basename.endswith("_test.py")
        or ".spec." in basename
        or ".test." in basename
    ):
        return "test"
    if basename in _ENTRY_POINTS:
        return "entry_point"
    if "static" in parts or "assets" in parts or "public" in parts:
        return "static"
    if any(part in {"routes", "router", "routers", "api"} for part in parts[:-1]) or any(
        token in basename for token in ("route", "router", "api")
    ):
        return "api_router"
    if any(part in {"models", "schema", "schemas"} for part in parts[:-1]) or any(
        token in basename for token in ("model", "schema")
    ):
        return "data_model"
    if basename.startswith(("config.", "settings.")) or basename in {
        "vite.config.js",
        "vite.config.ts",
    }:
        return "config"
    if "services" in parts[:-1]:
        return "service"
    if any(part in {"utils", "helpers"} for part in parts[:-1]) or any(
        token in basename for token in ("util", "helper")
    ):
        return "utility"
    return "unknown"


def infer_complexity(line_count: int, import_count: int, fan_out: int) -> str:
    if line_count > 400 or import_count > 15 or fan_out > 15:
        return "high"
    if line_count < 100 and import_count < 5 and fan_out < 5:
        return "low"
    return "medium"
