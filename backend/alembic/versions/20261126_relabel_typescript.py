"""relabel TypeScript files

Revision ID: 20261126_relabel_typescript
Revises: 20261125_add_repo_skipped_files
Create Date: 2026-11-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261126_relabel_typescript"
down_revision = "20261125_add_repo_skipped_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE file_node SET language = 'typescript' "
            "WHERE lower(file_path) LIKE '%.ts' "
            "OR lower(file_path) LIKE '%.tsx'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE file_node SET language = 'javascript' "
            "WHERE lower(file_path) LIKE '%.ts' "
            "OR lower(file_path) LIKE '%.tsx'"
        )
    )
