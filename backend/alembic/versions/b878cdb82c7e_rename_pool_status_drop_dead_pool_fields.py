"""rename_pool_status_drop_dead_pool_fields

号池机制已移除（commit b70bda7），但 4 个 pool_* 字段残留。本次：
- pool_status 重命名为 status，承担「unusable / retired」状态机功能
- pool_group_id / pool_use_count / pool_last_used_at 三个真死字段彻底删除

Revision ID: b878cdb82c7e
Revises: 397999fb03da
Create Date: 2026-04-26 20:31:48.678908

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = 'b878cdb82c7e'
down_revision: str | Sequence[str] | None = '397999fb03da'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('accounts', 'pool_status', new_column_name='status')
    # PostgreSQL 不允许直接 drop 带 FK 约束的列, 必须先 drop_constraint
    op.drop_constraint('accounts_pool_group_id_fkey', 'accounts', type_='foreignkey')
    op.drop_column('accounts', 'pool_group_id')
    op.drop_column('accounts', 'pool_use_count')
    op.drop_column('accounts', 'pool_last_used_at')


def downgrade() -> None:
    op.alter_column('accounts', 'status', new_column_name='pool_status')
    # 先加列(不带 FK), 再显式 create_foreign_key, 这样 constraint 名字能保持 'accounts_pool_group_id_fkey'
    op.add_column(
        'accounts',
        sa.Column('pool_group_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'accounts_pool_group_id_fkey',
        'accounts', 'family_groups',
        ['pool_group_id'], ['id'],
        ondelete='SET NULL',
    )
    op.add_column(
        'accounts',
        sa.Column('pool_use_count', sa.Integer(), server_default='0', nullable=True),
    )
    op.add_column(
        'accounts',
        sa.Column('pool_last_used_at', sa.DateTime(), nullable=True),
    )
