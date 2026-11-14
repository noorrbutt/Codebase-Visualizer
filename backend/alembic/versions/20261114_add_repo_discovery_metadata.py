"""add repository discovery metadata

Revision ID: 20261114_add_repo_discovery_metadata
Revises: 20261109_add_repo_commit_sha
Create Date: 2026-11-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261114_add_repo_discovery_metadata"
down_revision = "20261109_add_repo_commit_sha"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.add_column(sa.Column("discovered_files", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("truncated", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.drop_column("truncated")
        batch_op.drop_column("discovered_files")
