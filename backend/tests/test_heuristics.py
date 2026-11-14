import pytest

from app.services.heuristics import infer_complexity, infer_file_role


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_routes.py", "test"),
        ("src/services/user_test.py", "test"),
        ("src/app.test.js", "test"),
        ("src/App.spec.jsx", "test"),
        ("src/main.py", "entry_point"),
        ("src/index.js", "entry_point"),
        ("src/routes/users.py", "api_router"),
        ("src/api/client.py", "api_router"),
        ("src/models/user.py", "data_model"),
        ("src/schema.py", "data_model"),
        ("src/config/settings.py", "config"),
        ("src/vite.config.js", "config"),
        ("src/services/users.py", "service"),
        ("src/utils/paths.py", "utility"),
        ("src/helpers/format.py", "utility"),
        ("src/static/app.css", "static"),
        ("src/misc/worker.py", "unknown"),
    ],
)
def test_infer_file_role(path, expected):
    assert infer_file_role(path) == expected


@pytest.mark.parametrize(
    ("line_count", "import_count", "fan_out", "expected"),
    [
        (99, 4, 4, "low"),
        (100, 4, 4, "medium"),
        (401, 0, 0, "high"),
        (100, 16, 0, "high"),
        (100, 0, 16, "high"),
    ],
)
def test_infer_complexity(line_count, import_count, fan_out, expected):
    assert infer_complexity(line_count, import_count, fan_out) == expected
