"""add error message to repository

Revision ID: 20261108_add_repo_error_message
Revises: 20260811_add_repo_github_unique
Create Date: 2026-11-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261108_add_repo_error_message"
down_revision = "20260811_add_repo_github_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.drop_column("error_message")
