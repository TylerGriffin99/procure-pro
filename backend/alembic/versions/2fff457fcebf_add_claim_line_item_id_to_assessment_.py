"""add claim_line_item_id to assessment_variations and assessment_provisional_sums

Revision ID: 2fff457fcebf
Revises: 6292dabeb2e7
Create Date: 2026-05-15 15:10:04.104801
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2fff457fcebf'
down_revision: Union[str, None] = '6292dabeb2e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_provisional_sums', sa.Column('claim_line_item_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_assessment_ps_claim_line_item',
        'assessment_provisional_sums', 'claim_line_items',
        ['claim_line_item_id'], ['id'],
    )
    op.add_column('assessment_variations', sa.Column('claim_line_item_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_assessment_var_claim_line_item',
        'assessment_variations', 'claim_line_items',
        ['claim_line_item_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_assessment_var_claim_line_item', 'assessment_variations', type_='foreignkey')
    op.drop_column('assessment_variations', 'claim_line_item_id')
    op.drop_constraint('fk_assessment_ps_claim_line_item', 'assessment_provisional_sums', type_='foreignkey')
    op.drop_column('assessment_provisional_sums', 'claim_line_item_id')
