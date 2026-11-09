"""add stage to repository

Revision ID: 20261109_add_repo_stage
Revises: 20261108_add_repo_error_message
Create Date: 2026-11-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261109_add_repo_stage"
down_revision = "20261108_add_repo_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.add_column(sa.Column("stage", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("repository") as batch_op:
        batch_op.drop_column("stage")
