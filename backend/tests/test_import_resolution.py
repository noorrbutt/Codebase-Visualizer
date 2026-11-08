from __future__ import annotations

from app.api.routes.repos import (
    _build_edges,
    _resolve_python_absolute_import,
    _resolve_python_relative_import,
    _resolve_relative_import,
)
from app.services.parser import CodeParser


def test_resolve_relative_import_handles_nested_paths_and_extensions():
    module_map = {
        "src.components.Header": "src/components/Header.jsx",
        "src.utils.index": "src/utils/index.ts",
        "src.utils": "src/utils/index.ts",
    }

    assert _resolve_relative_import("src/App.jsx", "./components/Header", module_map) == "src/components/Header.jsx"
    assert _resolve_relative_import("src/pages/Home.jsx", "../utils", module_map) == "src/utils/index.ts"


def test_build_edges_resolves_extension_fallback_and_index_files():
    parsed = {
        "src/App.jsx": ["./components/Header", "./utils"],
        "src/components/Header.jsx": [],
        "src/utils/index.ts": [],
    }

    edges = _build_edges(parsed)

    assert any(edge.source == "src/App.jsx" and edge.target == "src/components/Header.jsx" for edge in edges)
    assert any(edge.source == "src/App.jsx" and edge.target == "src/utils/index.ts" for edge in edges)


def test_python_absolute_imports_match_source_root_suffixes():
    parsed = {
        "backend/app/api/routes/repos.py": ["app.services.github"],
        "backend/app/services/github.py": [],
    }

    edges = _build_edges(parsed)

    assert any(
        edge.source == "backend/app/api/routes/repos.py"
        and edge.target == "backend/app/services/github.py"
        for edge in edges
    )


def test_python_package_import_resolves_to_init_file():
    parsed = {
        "backend/app/client.py": ["app.api"],
        "backend/app/api/__init__.py": [],
    }

    edges = _build_edges(parsed)

    assert any(
        edge.source == "backend/app/client.py"
        and edge.target == "backend/app/api/__init__.py"
        for edge in edges
    )


def test_python_absolute_suffix_matching_ignores_ambiguous_names():
    module_map = {
        "one.app.models": "one/app/models.py",
        "two.app.models": "two/app/models.py",
    }

    assert _resolve_python_absolute_import("app.models", module_map) is None
    assert _resolve_python_absolute_import("models", module_map) is None
    assert (
        _resolve_python_absolute_import("models", {"backend.app.models": "backend/app/models.py"})
        == "backend/app/models.py"
    )


def test_python_relative_imports_use_package_levels_and_submodules():
    module_map = {
        "backend.app.api.routes.helpers": "backend/app/api/routes/helpers.py",
        "backend.app.models": "backend/app/models/__init__.py",
        "backend.app.services.github": "backend/app/services/github.py",
        "backend.app.services": "backend/app/services/__init__.py",
    }

    assert (
        _resolve_python_relative_import(
            "backend/app/api/routes/repos.py", ".helpers", module_map
        )
        == "backend/app/api/routes/helpers.py"
    )
    assert (
        _resolve_python_relative_import(
            "backend/app/api/routes/repos.py", "...models", module_map
        )
        == "backend/app/models/__init__.py"
    )
    assert (
        _resolve_python_relative_import(
            "backend/app/api/routes/repos.py", "...services.github", module_map
        )
        == "backend/app/services/github.py"
    )


def test_python_from_import_resolves_submodule_candidates():
    parser = CodeParser()
    imports = parser.parse("backend/app/client.py", "from app import services\n")[
        "imports"
    ]
    parsed = {
        "backend/app/client.py": imports,
        "backend/app/__init__.py": [],
        "backend/app/services.py": [],
    }

    edges = _build_edges(parsed)

    assert any(
        edge.source == "backend/app/client.py"
        and edge.target == "backend/app/services.py"
        for edge in edges
    )


def test_python_relative_from_import_resolves_submodule_candidates():
    imports = CodeParser().parse(
        "backend/app/client.py", "from . import services\n"
    )["imports"]
    parsed = {
        "backend/app/client.py": imports,
        "backend/app/__init__.py": [],
        "backend/app/services.py": [],
    }

    edges = _build_edges(parsed)

    assert any(
        edge.source == "backend/app/client.py"
        and edge.target == "backend/app/services.py"
        for edge in edges
    )
