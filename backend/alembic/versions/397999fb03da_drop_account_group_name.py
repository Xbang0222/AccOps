"""drop accounts.group_name (replaced by tags)

Revision ID: 397999fb03da
Revises: 638875af4104
Create Date: 2026-04-26 13:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '397999fb03da'
down_revision: str | Sequence[str] | None = '638875af4104'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('accounts', 'group_name')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'accounts',
        sa.Column('group_name', sa.String(), server_default='', nullable=True),
    )
