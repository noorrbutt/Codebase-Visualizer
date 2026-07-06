"""add indexes for repo_id on file_node and file_edge

Revision ID: 20260706_add_repo_indexes
Revises: 20260706_add_repo_locking
Create Date: 2026-07-06 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260706_add_repo_indexes"
down_revision = "20260706_add_repo_locking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_file_node_repo_id"), "file_node", ["repo_id"], unique=False)
    op.create_index(op.f("ix_file_edge_repo_id"), "file_edge", ["repo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_file_edge_repo_id"), table_name="file_edge")
    op.drop_index(op.f("ix_file_node_repo_id"), table_name="file_node")
