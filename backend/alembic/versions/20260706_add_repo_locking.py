"""add locked_at and worker_id to repository

Revision ID: 20260706_add_repo_locking
Revises: 
Create Date: 2026-07-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260706_add_repo_locking'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add columns in a way compatible with sqlite by using batch_alter_table
    with op.batch_alter_table('repository') as batch_op:
        batch_op.add_column(sa.Column('locked_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('worker_id', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('repository') as batch_op:
        batch_op.drop_column('worker_id')
        batch_op.drop_column('locked_at')
