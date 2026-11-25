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

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
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
        assert revision == "20261125_add_repo_skipped_files"
    finally:
        engine.dispose()
