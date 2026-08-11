"""add unique index on repository.github_url

Revision ID: 20260811_add_repo_github_unique
Revises: 20260809_add_file_node_ai_summary_detail
Create Date: 2026-08-11 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260811_add_repo_github_unique"
down_revision = "20260809_add_file_node_ai_summary_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create a unique index on repository.github_url to enforce uniqueness at the DB level.
    op.create_index(op.f("uq_repository_github_url"), "repository", ["github_url"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("uq_repository_github_url"), table_name="repository")
