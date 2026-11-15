from app.api.routes.repos import _build_edges
from app.exceptions import RepoParseError
from app.services.github import GithubService
from app.services.parser import CodeParser

import pytest


def test_parse_python_imports():
    parser = CodeParser()
    result = parser.parse(
        "main.py",
        "from fastapi import APIRouter\nimport os\n",
    )

    assert result["language"] == "python"
    assert "fastapi" in result["imports"]
    assert "os" not in result["imports"]


def test_parse_multiline_python_from_imports_includes_submodules():
    imports = CodeParser().parse(
        "main.py",
        "from app.services import (\n    ai,\n    github,\n)\n",
    )["imports"]

    assert imports == [
        "app.services",
        "app.services.ai",
        "app.services.github",
    ]


def test_parse_python_ignores_imports_in_docstrings_and_comments():
    imports = CodeParser().parse(
        "main.py",
        '"""import fake_module\nfrom fake_package import fake_submodule"""\n'
        "# import also_fake\nimport real_module\n",
    )["imports"]

    assert imports == ["real_module"]


def test_parse_python_relative_from_import_keeps_leading_dots():
    imports = CodeParser().parse(
        "main.py",
        "from . import sibling\nfrom ..package import module\n",
    )["imports"]

    assert imports == [".", ".sibling", "..package", "..package.module"]


def test_parse_js_imports():
    parser = CodeParser()
    result = parser.parse(
        "src/App.jsx",
        "import { useState } from \"react\"\nimport App from \"./App\"\n",
    )

    assert result["language"] == "javascript"
    assert "react" in result["imports"]
    assert "./App" in result["imports"]


def test_parse_js_dynamic_import_and_ignores_comment_imports():
    imports = CodeParser().parse(
        "src/App.jsx",
        "// import('./commented-out')\n"
        "/* import('./also-commented') */\n"
        'const url = "https://example.com/a//b";\n'
        "const page = import('./Page');\n",
    )["imports"]

    assert imports == ["./Page"]


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


def test_parse_repo_url_rejects_invalid_owner_or_repo():
    service = GithubService()

    with pytest.raises(RepoParseError):
        service.parse_repo_url("https://github.com/bad!/repo")

    with pytest.raises(RepoParseError):
        service.parse_repo_url("https://github.com/owner/bad repo")
