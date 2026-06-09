from app.api.routes.repos import _build_edges
from app.services.parser import CodeParser


def test_parse_python_imports():
    parser = CodeParser()
    result = parser.parse(
        "main.py",
        "from fastapi import APIRouter\nimport os\n",
    )

    assert result["language"] == "python"
    assert "fastapi" in result["imports"]
    assert "os" not in result["imports"]


def test_parse_js_imports():
    parser = CodeParser()
    result = parser.parse(
        "src/App.jsx",
        "import { useState } from \"react\"\nimport App from \"./App\"\n",
    )

    assert result["language"] == "javascript"
    assert "react" in result["imports"]
    assert "./App" in result["imports"]


def test_parse_relative_import_resolution():
    parsed = {
        "src/App.jsx": ["./components/Header"],
        "src/components/Header.jsx": [],
    }
    edges = _build_edges(parsed)

    assert any(
        edge.source == "src/App.jsx" and edge.target == "src/components/Header.jsx"
        for edge in edges
    )


def test_line_count():
    parser = CodeParser()
    result = parser.parse("foo.py", "one\ntwo\nthree\nfour\nfive\n")

    assert result["line_count"] == 6


def test_unsupported_extension():
    parser = CodeParser()
    result = parser.parse("data.json", '{"hello": "world"}')

    assert result["language"] == "text"
    assert result["imports"] == []
