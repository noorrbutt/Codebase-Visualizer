from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Integer, create_engine, inspect, text

from app.config import settings


def test_repository_skipped_files_migration_upgrades_sqlite(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)

    backend_path = Path(__file__).resolve().parents[1]
    config = Config(str(backend_path / "alembic.ini"))
    config.set_main_option("script_location", str(backend_path / "alembic"))

    command.upgrade(config, "20261125_add_repo_skipped_files")

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO repository "
                    "(github_url, repo_name, owner, total_files, status) "
                    "VALUES ('https://github.com/octocat/lang-test', 'lang-test', "
                    "'octocat', 5, 'ready')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO file_node "
                    "(repo_id, file_path, language, line_count, import_count) "
                    "VALUES "
                    "(1, 'src/app.ts', 'javascript', 1, 0), "
                    "(1, 'src/view.tsx', 'javascript', 1, 0), "
                    "(1, 'src/Uppercase.TSX', 'javascript', 1, 0), "
                    "(1, 'src/legacy.js', 'javascript', 1, 0), "
                    "(1, 'src/component.jsx', 'javascript', 1, 0)"
                )
            )

        command.upgrade(config, "head")

        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("repository")
        }
        assert isinstance(columns["skipped_files"]["type"], Integer)
        assert columns["skipped_files"]["nullable"] is True
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            languages = dict(
                connection.execute(
                    text("SELECT file_path, language FROM file_node")
                ).all()
            )
        assert revision == "20261126_relabel_typescript"
        assert languages == {
            "src/app.ts": "typescript",
            "src/view.tsx": "typescript",
            "src/Uppercase.TSX": "typescript",
            "src/legacy.js": "javascript",
            "src/component.jsx": "javascript",
        }

        command.downgrade(config, "base")
        command.upgrade(config, "head")

        rebuilt_tables = set(inspect(engine).get_table_names())
        assert {"repository", "file_node", "file_edge"} <= rebuilt_tables
        with engine.connect() as connection:
            rebuilt_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert rebuilt_revision == "20261126_relabel_typescript"
    finally:
        engine.dispose()
