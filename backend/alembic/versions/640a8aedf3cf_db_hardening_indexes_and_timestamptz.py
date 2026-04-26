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


def _check_email_case_uniqueness() -> None:
    """创建 lower(email) 唯一索引前的前置检查。

    若库中存在大小写差异的重复邮箱（如 Foo@x.com / foo@x.com 共存），
    `CREATE UNIQUE INDEX` 会直接报错回滚整个迁移。这里提前检查并 raise，
    给运维明确的错误信息以便人工 dedupe 后再升级。
    """
    # alembic 1.9+ 推荐 op.get_context().bind 替代 op.get_bind()
    bind = op.get_context().bind
    rows = bind.execute(sa.text(
        "SELECT lower(email) AS lemail, count(*) AS cnt "
        "FROM accounts GROUP BY lower(email) HAVING count(*) > 1"
    )).fetchall()
    if rows:
        dupes = ", ".join(f"{r.lemail} ({r.cnt} 行)" for r in rows)
        raise RuntimeError(
            "邮箱大小写重复, 无法创建 lower(email) 唯一索引: "
            f"{dupes}. 请先手工合并/删除冲突账号后重新执行 alembic upgrade。"
        )


def upgrade() -> None:
    _check_email_case_uniqueness()

    op.create_index(
        "ix_accounts_email_lower",
        "accounts",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index("ix_accounts_family_group_id", "accounts", ["family_group_id"])
    op.create_index("ix_sms_activations_provider_id", "sms_activations", ["provider_id"])
    # status partial index: 绝大多数行 status='', 只索引非空状态以提升选择性
    op.create_index(
        "ix_accounts_status",
        "accounts",
        ["status"],
        postgresql_where=sa.text("status != ''"),
    )

    # table/col 均为本文件硬编码常量, 无 SQL 注入风险; 用 sa.text 显式声明语法树位置
    for table, col in TIMESTAMP_COLUMNS:
        op.execute(sa.text(
            f"ALTER TABLE {table} ALTER COLUMN {col} "
            f"TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
        ))


def downgrade() -> None:
    for table, col in TIMESTAMP_COLUMNS:
        op.execute(sa.text(
            f"ALTER TABLE {table} ALTER COLUMN {col} "
            f"TYPE TIMESTAMP USING {col} AT TIME ZONE 'UTC'"
        ))
    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_sms_activations_provider_id", table_name="sms_activations")
    op.drop_index("ix_accounts_family_group_id", table_name="accounts")
    op.drop_index("ix_accounts_email_lower", table_name="accounts")
