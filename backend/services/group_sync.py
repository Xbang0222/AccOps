"""家庭组与本地分组关系同步。"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.constants import (
    ACTION_FAMILY_ACCEPT,
    ACTION_FAMILY_CREATE,
    ACTION_FAMILY_LEAVE,
    ACTION_FAMILY_REMOVE,
    FAMILY_MAX_MEMBERS,
)
from models.database import get_db_session
from models.orm import Account, Group

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Iterator[Session]]


@contextmanager
def _session_scope(session_factory: SessionFactory):
    with session_factory() as db:
        yield db


def sync_group_after_action(
    action: str,
    account_id: int,
    success: bool,
    result_msg: str,
    extra: dict | None = None,
    session_factory: SessionFactory = get_db_session,
) -> None:
    """自动化操作成功后，同步家庭组关系到数据库分组。"""
    if not success:
        return

    try:
        with _session_scope(session_factory) as db:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return

            if action == ACTION_FAMILY_CREATE:
                _sync_created_group(db, account)
                return

            if action == ACTION_FAMILY_ACCEPT:
                _sync_accepted_group(db, account, extra or {})
                return

            if action == ACTION_FAMILY_REMOVE:
                _sync_removed_member(db, extra or {})
                return

            if action == ACTION_FAMILY_LEAVE:
                _sync_left_group(db, account)
    except Exception as exc:
        logger.error("[sync_group] 同步分组失败: %s", exc)


def sync_group_from_discover(
    account_id: int,
    discover_result,
    session_factory: SessionFactory = get_db_session,
) -> None:
    """根据发现结果同步数据库中的家庭组关系。"""
    if not discover_result or not discover_result.success:
        return

    try:
        with _session_scope(session_factory) as db:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                return

            if not discover_result.has_group:
                clear_account_family_state(account)
                if account.family_group_id:
                    logger.info("[discover_sync] %s 已不在家庭组, 清除分组关系", account.email)
                else:
                    logger.info("[discover_sync] %s 无家庭组, 无需更新", account.email)
                return

            if discover_result.role == "manager":
                _sync_manager_discover(db, account, discover_result)
                return

            if discover_result.role == "member":
                _sync_member_discover(db, account, discover_result)
    except Exception as exc:
        logger.error("[discover_sync] 同步失败: %s", exc)


def _sync_created_group(db: Session, account: Account) -> None:
    if account.family_group_id:
        logger.info("[sync_group] 账号 %s 已在分组 %s 中, 跳过创建", account.email, account.family_group_id)
        return

    group = Group(name=f"{account.email} 的家庭组")
    db.add(group)
    db.flush()
    group.main_account_id = account.id
    group.member_count = max(group.member_count or 0, 1)
    account.family_group_id = group.id
    account.updated_at = datetime.now(UTC)
    logger.info("[sync_group] 已创建分组 #%s 并设置 %s 为管理员", group.id, account.email)


def _sync_accepted_group(db: Session, account: Account, extra: dict) -> None:
    joined_group_id = account.family_group_id
    if joined_group_id:
        logger.info("[sync_group] 账号 %s 已在分组 %s 中, 跳过", account.email, joined_group_id)
    else:
        joined_group_id = _resolve_join_group_id(db, extra)
        if joined_group_id:
            account.family_group_id = joined_group_id
            account.updated_at = datetime.now(UTC)
            logger.info("[sync_group] 已将 %s 加入分组 #%s", account.email, joined_group_id)

    if joined_group_id:
        _inherit_owner_subscription(db, account, joined_group_id)


def _resolve_join_group_id(db: Session, extra: dict) -> int | None:
    group_id = extra.get("group_id")
    if group_id:
        group = db.query(Group).filter(Group.id == group_id).first()
        if group:
            return group_id

    manager_id = extra.get("manager_account_id")
    if manager_id:
        manager = db.query(Account).filter(Account.id == manager_id).first()
        if manager and manager.family_group_id:
            return manager.family_group_id

    # 单条聚合查询：拿到每个有主号的分组及其成员数，避免循环 COUNT (1+N → 1)
    rows = (
        db.query(Group, func.count(Account.id).label("member_count"))
        .outerjoin(Account, Account.family_group_id == Group.id)
        .filter(Group.main_account_id.isnot(None))
        .group_by(Group.id)
        .all()
    )
    for group, member_count in rows:
        if member_count < FAMILY_MAX_MEMBERS:
            logger.info("[sync_group] 兜底: 选择分组 #%s (%s)", group.id, group.name)
            return group.id

    logger.warning("[sync_group] 接受邀请: 未找到可加入的分组")
    return None


def _inherit_owner_subscription(db: Session, account: Account, group_id: int) -> None:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not group.main_account_id:
        return

    main_account = db.query(Account).filter(Account.id == group.main_account_id).first()
    if not main_account or main_account.subscription_status != "ultra":
        return

    account.subscription_status = main_account.subscription_status
    account.subscription_expiry = main_account.subscription_expiry or ""
    account.updated_at = datetime.now(UTC)
    logger.info("[sync_group] %s 继承主号 Ultra 订阅", account.email)


def _sync_removed_member(db: Session, extra: dict) -> None:
    member_email = extra.get("member_email", "")
    if not member_email:
        return

    member = db.query(Account).filter(func.lower(Account.email) == member_email.lower()).first()
    if not member or not member.family_group_id:
        return

    old_group_id = member.family_group_id
    clear_account_family_state(member)
    logger.info("[sync_group] 已将 %s 从分组 #%s 中移除", member_email, old_group_id)


def _sync_left_group(db: Session, account: Account) -> None:
    if not account.family_group_id:
        return

    group_id = account.family_group_id
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        return

    if group.main_account_id == account.id:
        members = db.query(Account).filter(Account.family_group_id == group_id).all()
        for member in members:
            clear_account_family_state(member)
        db.delete(group)
        logger.info("[sync_group] 管理员 %s 删除了分组 #%s", account.email, group_id)
        return

    clear_account_family_state(account)
    logger.info("[sync_group] 成员 %s 退出了分组 #%s", account.email, group_id)


def _sync_manager_discover(db: Session, account: Account, discover_result) -> None:
    if account.family_group_id:
        group = db.query(Group).filter(Group.id == account.family_group_id).first()
        if group and group.main_account_id == account.id:
            group.member_count = discover_result.member_count
            group.updated_at = datetime.now(UTC)
            logger.info("[discover_sync] %s 已是分组 #%s 管理员, 更新成员数=%s", account.email, group.id, discover_result.member_count)
            _sync_members_from_discover(db, group.id, discover_result.members)
            return

        # 账号在一个分组里但不是管理员 → 可能是用户手动创建的分组，
        # 检查是否有该账号作为管理员的其他分组
        existing_group = db.query(Group).filter(Group.main_account_id == account.id).first()
        if existing_group:
            # 复用已有分组，但不覆盖用户设置的名称
            existing_group.member_count = discover_result.member_count
            existing_group.updated_at = datetime.now(UTC)
            account.family_group_id = existing_group.id
            account.updated_at = datetime.now(UTC)
            logger.info("[discover_sync] %s 旧分组无效, 切换到已有管理员分组 #%s", account.email, existing_group.id)
            _sync_members_from_discover(db, existing_group.id, discover_result.members)
            return

        logger.info("[discover_sync] %s 旧分组 #%s 无效, 将重建", account.email, account.family_group_id)
        account.family_group_id = None

    # 查找该账号已有的管理员分组
    group = db.query(Group).filter(Group.main_account_id == account.id).first()
    if group:
        group.member_count = discover_result.member_count
        # 不覆盖用户手动设置的分组名
        group.updated_at = datetime.now(UTC)
        account.family_group_id = group.id
        account.updated_at = datetime.now(UTC)
        logger.info("[discover_sync] 复用已有分组 #%s 给管理员 %s", group.id, account.email)
    else:
        group = Group(name=f"{account.email} 的家庭组", member_count=discover_result.member_count)
        db.add(group)
        db.flush()
        group.main_account_id = account.id
        account.family_group_id = group.id
        account.updated_at = datetime.now(UTC)
        logger.info("[discover_sync] 为管理员 %s 创建分组 #%s", account.email, group.id)

    _sync_members_from_discover(db, group.id, discover_result.members)


def _sync_member_discover(db: Session, account: Account, discover_result) -> None:
    if account.family_group_id:
        logger.info("[discover_sync] %s 已在分组 #%s 中", account.email, account.family_group_id)
        return

    manager_names = [member["name"] for member in discover_result.members if member.get("role") == "manager"]
    candidates = db.query(Account).filter(Account.family_group_id.isnot(None)).all()

    for manager_name in manager_names:
        manager_name_lower = manager_name.lower()
        for candidate in candidates:
            email_prefix = candidate.email.split("@")[0].lower()
            if email_prefix in manager_name_lower or manager_name_lower in candidate.email.lower():
                group = db.query(Group).filter(Group.id == candidate.family_group_id).first()
                if group and group.main_account_id == candidate.id:
                    account.family_group_id = group.id
                    account.updated_at = datetime.now(UTC)
                    logger.info("[discover_sync] 成员 %s 加入管理员 %s 的分组 #%s", account.email, candidate.email, group.id)
                    return

    logger.info("[discover_sync] 成员 %s 未找到匹配的管理员分组", account.email)


def _sync_members_from_discover(db: Session, group_id: int, members: list[dict]) -> None:
    """根据发现的成员列表同步数据库中的成员关系。"""
    try:
        discovered_emails = {
            member.get("email", "").strip().lower()
            for member in members
            if member.get("email", "").strip()
        }

        old_members = db.query(Account).filter(Account.family_group_id == group_id).all()
        for old_account in old_members:
            if old_account.email.lower() in discovered_emails:
                continue
            logger.info("[discover_sync] 成员 %s 不在 discover 结果中, 从分组 #%s 移除", old_account.email, group_id)
            clear_account_family_state(old_account)

        for member in members:
            if member.get("role") == "manager":
                _clear_pending_flag(db, member.get("email", ""))
                continue

            email = member.get("email", "").strip()
            if not email:
                logger.info("[discover_sync] 成员 %s 无邮箱, 跳过", member.get("name", "?"))
                continue

            _upsert_discovered_member(db, group_id, email, member.get("role") == "pending")
    except Exception:
        db.rollback()
        raise


def _clear_pending_flag(db: Session, email: str) -> None:
    if not email:
        return

    account = db.query(Account).filter(func.lower(Account.email) == email.lower()).first()
    if account and account.is_family_pending:
        account.is_family_pending = False
        account.updated_at = datetime.now(UTC)


def _upsert_discovered_member(db: Session, group_id: int, email: str, is_pending: bool) -> None:
    now = datetime.now(UTC)
    account = db.query(Account).filter(func.lower(Account.email) == email.lower()).first()
    if not account:
        account = Account(email=email, family_group_id=group_id, is_family_pending=is_pending)
        db.add(account)
        logger.info("[discover_sync] 新建成员账号 %s 并关联到分组 #%s", email, group_id)
        return

    changed = False
    if account.family_group_id != group_id:
        account.family_group_id = group_id
        changed = True
    if account.is_family_pending != is_pending:
        account.is_family_pending = is_pending
        changed = True

    if changed:
        account.updated_at = now
        logger.info("[discover_sync] 已有关联成员 %s 更新到分组 #%s", account.email, group_id)


def clear_account_family_state(account: Account) -> None:
    now = datetime.now(UTC)
    if account.family_group_id and not account.is_family_pending:
        account.retired_at = now
        account.status = "retired"
    account.family_group_id = None
    account.is_family_pending = False
    account.subscription_status = ""
    account.subscription_expiry = ""
    account.updated_at = now
