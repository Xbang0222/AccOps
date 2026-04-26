"""add tags tables

Revision ID: 638875af4104
Revises: 785fbf1b23f0
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '638875af4104'
down_revision: Union[str, Sequence[str], None] = '785fbf1b23f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_tags_name'),
    )

    op.create_table(
        'account_tags',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('account_id', 'tag_id'),
    )
    op.create_index('ix_account_tags_tag_id', 'account_tags', ['tag_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_account_tags_tag_id', table_name='account_tags')
    op.drop_table('account_tags')
    op.drop_table('tags')
