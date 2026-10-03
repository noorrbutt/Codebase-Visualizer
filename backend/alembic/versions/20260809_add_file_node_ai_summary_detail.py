"""add ai_summary_detail to file_node

Revision ID: 20260809_add_file_node_ai_summary_detail
Revises: 20260706_add_repo_indexes
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260809_add_file_node_ai_summary_detail"
down_revision = "20260706_add_repo_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres sizes alembic_version.version_num as VARCHAR(32), but this revision id is longer.
    # Widen it here; alembic updates the version row after this step in the same transaction.
    # SQLite does not enforce the length, so it is skipped there.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(32),
            type_=sa.String(255),
        )

    with op.batch_alter_table("file_node") as batch_op:
        batch_op.add_column(sa.Column("ai_summary_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("file_node") as batch_op:
        batch_op.drop_column("ai_summary_detail")
