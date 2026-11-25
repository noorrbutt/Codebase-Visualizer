"""add skipped file count to repositories

Revision ID: 20261125_add_repo_skipped_files
Revises: 20261116_add_file_node_blob_sha
Create Date: 2026-11-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261125_add_repo_skipped_files"
down_revision = "20261116_add_file_node_blob_sha"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.add_column(sa.Column("skipped_files", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.drop_column("skipped_files")
