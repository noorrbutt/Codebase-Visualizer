"""add blob sha to file nodes

Revision ID: 20261116_add_file_node_blob_sha
Revises: 20261114_add_repo_discovery_metadata
Create Date: 2026-11-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261116_add_file_node_blob_sha"
down_revision = "20261114_add_repo_discovery_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("file_node") as batch_op:
        batch_op.add_column(sa.Column("blob_sha", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("file_node") as batch_op:
        batch_op.drop_column("blob_sha")
