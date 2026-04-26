"""db_hardening_indexes_and_timestamptz

D2 数据库一次性收口：
- email 函数唯一索引（lower(email)）+ 外键索引（family_group_id / sms_activations.provider_id）+ status 索引
- 全部 DateTime 列切到 TIMESTAMPTZ（旧 naive 值按 UTC 解释，无数据丢失）

Revision ID: 640a8aedf3cf
Revises: b878cdb82c7e
Create Date: 2026-04-26 20:40:41.617003

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '640a8aedf3cf'
down_revision: str | Sequence[str] | None = 'b878cdb82c7e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TIMESTAMP_COLUMNS: list[tuple[str, str]] = [
    ("accounts", "created_at"),
    ("accounts", "updated_at"),
    ("accounts", "retired_at"),
    ("family_groups", "created_at"),
    ("family_groups", "updated_at"),
    ("tags", "created_at"),
    ("tags", "updated_at"),
    ("browser_profiles", "created_at"),
    ("browser_profiles", "updated_at"),
    ("sms_providers", "created_at"),
    ("sms_providers", "updated_at"),
    ("sms_activations", "created_at"),
    ("sms_activations", "updated_at"),
]


def upgrade() -> None:
    op.create_index(
        "ix_accounts_email_lower",
        "accounts",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index("ix_accounts_family_group_id", "accounts", ["family_group_id"])
    op.create_index("ix_sms_activations_provider_id", "sms_activations", ["provider_id"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    for table, col in TIMESTAMP_COLUMNS:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {col} '
            f"TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for table, col in TIMESTAMP_COLUMNS:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {col} '
            f"TYPE TIMESTAMP USING {col} AT TIME ZONE 'UTC'"
        )
    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_sms_activations_provider_id", table_name="sms_activations")
    op.drop_index("ix_accounts_family_group_id", table_name="accounts")
    op.drop_index("ix_accounts_email_lower", table_name="accounts")
