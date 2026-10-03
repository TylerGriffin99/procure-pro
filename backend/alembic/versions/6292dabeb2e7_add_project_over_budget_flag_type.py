"""add_project_over_budget_flag_type

Revision ID: 6292dabeb2e7
Revises: 89a9f40959af
Create Date: 2026-05-12 16:49:44.832282
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6292dabeb2e7'
down_revision: Union[str, None] = '89a9f40959af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE flag_type ADD VALUE IF NOT EXISTS 'project_over_budget'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; leave as-is
    pass
