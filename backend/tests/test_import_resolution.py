from __future__ import annotations

from app.api.routes.repos import _build_edges, _resolve_relative_import


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
