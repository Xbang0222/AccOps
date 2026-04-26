"""分组服务 - 处理分组 CRUD 和成员管理"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.constants import FAMILY_MAX_MEMBERS
from models.orm import Account, Group
from services.account import AccountService
from services.group_sync import clear_account_family_state


class GroupService:
    """分组业务逻辑"""

    MAX_MEMBERS = FAMILY_MAX_MEMBERS  # 1 个主号 + 5 个子号

    def __init__(self, db: Session, account_service: AccountService):
        self.db = db
        self.account_service = account_service

    def _to_dict(self, group: Group, main_email: str = None) -> dict:
        return {
            "id": group.id,
            "name": group.name,
            "main_account_id": group.main_account_id,
            "main_account_email": main_email or "",
            "notes": group.notes or "",
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        }

    def _ensure_main_account(self, accounts: list[dict], main_id: int, group_id: int,
                             *, _group_cache: dict = None) -> list[dict]:
        """主号的 family_group_id 意外丢失时，自动修复并补入列表"""
        if not main_id or any(a["id"] == main_id for a in accounts):
            return accounts
        main_acc = self.db.get(Account, main_id)
        if main_acc:
            main_acc.family_group_id = group_id
            self.db.commit()
            accounts.insert(0, self.account_service._to_dict(main_acc, _group_cache=_group_cache))
        return accounts

    def get_all(self, search: str = "") -> list[dict]:
        # 一次查出所有分组 + 主号邮箱
        rows = (
            self.db.query(Group, Account.email)
            .outerjoin(Account, Group.main_account_id == Account.id)
            .order_by(Group.name)
            .all()
        )
        group_ids = [group.id for group, _ in rows]

        # 一次查出所有分组的成员，按 group_id 分组（消除 N+1）
        all_members = (
            self.db.query(Account)
            .filter(Account.family_group_id.in_(group_ids))
            .order_by(Account.email)
            .all()
        ) if group_ids else []

        # 构建 group 缓存，供 _to_dict 内部使用（避免成员列表的 N+1）
        group_cache = {group.id: group for group, _ in rows}

        members_by_group: dict[int, list[dict]] = {}
        for member in all_members:
            gid = member.family_group_id
            if gid not in members_by_group:
                members_by_group[gid] = []
            members_by_group[gid].append(self.account_service._to_dict(member, _group_cache=group_cache))

        result = []
        keyword = search.strip().lower()
        for group, email in rows:
            d = self._to_dict(group, email)
            accounts = members_by_group.get(group.id, [])
            d["accounts"] = self._ensure_main_account(accounts, group.main_account_id, group.id,
                                                       _group_cache=group_cache)
            # 搜索过滤: 匹配分组名、主号邮箱或任意子号邮箱
            if keyword:
                match = (
                    keyword in (group.name or "").lower()
                    or keyword in (email or "").lower()
                    or any(keyword in (a.get("email", "")).lower() for a in d["accounts"])
                )
                if not match:
                    continue
            result.append(d)
        return result

    def get_by_id(self, group_id: int) -> dict | None:
        result = (
            self.db.query(Group, Account.email)
            .outerjoin(Account, Group.main_account_id == Account.id)
            .filter(Group.id == group_id)
            .first()
        )
        if not result:
            return None
        group, email = result
        return self._to_dict(group, email)

    def get_with_accounts(self, group_id: int) -> dict | None:
        """获取分组详情（含成员列表）"""
        group_dict = self.get_by_id(group_id)
        if group_dict:
            accounts = self.get_accounts(group_id)
            group_dict["accounts"] = self._ensure_main_account(
                accounts, group_dict.get("main_account_id"), group_id
            )
        return group_dict

    def get_accounts(self, group_id: int, *, _group_cache: dict | None = None) -> list[dict]:
        """获取分组内所有账号"""
        rows = (
            self.db.query(Account)
            .filter(Account.family_group_id == group_id)
            .order_by(Account.email)
            .all()
        )
        # 一次性查 group 缓存供 _to_dict 使用，消除 N+1
        if _group_cache is None:
            group_obj = self.db.get(Group, group_id)
            _group_cache = {group_id: group_obj} if group_obj else {}
        return [self.account_service._to_dict(row, _group_cache=_group_cache) for row in rows]

    def create(self, name: str, notes: str = "") -> int:
        group = Group(name=name, notes=notes)
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group.id

    def update(self, group_id: int, name: str, main_account_id: int = None, notes: str = ""):
        group = self.db.get(Group, group_id)
        if not group:
            return
        group.name = name
        group.main_account_id = main_account_id
        group.notes = notes
        group.updated_at = datetime.now(UTC)
        self.db.commit()

    def delete(self, group_id: int):
        group = self.db.get(Group, group_id)
        if group:
            members = self.db.query(Account).filter(Account.family_group_id == group_id).all()
            for member in members:
                clear_account_family_state(member)
            self.db.delete(group)
            self.db.commit()

    def add_account(self, group_id: int, account_id: int):
        count = self.db.query(Account).filter(Account.family_group_id == group_id).count()
        if count >= self.MAX_MEMBERS:
            raise ValueError(f"分组最多只能有{self.MAX_MEMBERS}个账号（1个主号+5个子号）")

        account = self.db.query(Account).get(account_id)
        if account:
            now = datetime.now(UTC)
            if account.family_group_id != group_id:
                # 已在其他分组 → 先走退出逻辑
                if account.family_group_id is not None:
                    clear_account_family_state(account)
            account.family_group_id = group_id
            account.updated_at = now
            self.db.commit()

    def remove_account(self, account_id: int):
        account = self.db.query(Account).get(account_id)
        if account:
            clear_account_family_state(account)
            self.db.commit()

    def set_main_account(self, group_id: int, account_id: int):
        account = self.db.query(Account).get(account_id)
        if not account or account.family_group_id != group_id:
            raise ValueError("该账号不在指定的分组内")

        group = self.db.get(Group, group_id)
        if group:
            group.main_account_id = account_id
            group.updated_at = datetime.now(UTC)
            self.db.commit()
