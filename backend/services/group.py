"""分组服务 - 处理分组 CRUD 和成员管理"""
from datetime import datetime, timezone
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from models.orm import Group, Account
from services.account import AccountService
from core.constants import FAMILY_MAX_MEMBERS, POOL_MAX_USE_COUNT, POOL_STATUS_RETIRED


class GroupService:
    """分组业务逻辑"""

    MAX_MEMBERS = FAMILY_MAX_MEMBERS  # 1 个主号 + 5 个子号

    def __init__(self, db: Session, account_service: AccountService):
        self.db = db
        self.account_service = account_service

    def _to_dict(self, group: Group, main_email: str = None) -> Dict:
        return {
            "id": group.id,
            "name": group.name,
            "main_account_id": group.main_account_id,
            "main_account_email": main_email or "",
            "notes": group.notes or "",
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        }

    def _ensure_main_account(self, accounts: List[Dict], main_id: int, group_id: int) -> List[Dict]:
        """主号的 family_group_id 意外丢失时，自动修复并补入列表"""
        if not main_id or any(a["id"] == main_id for a in accounts):
            return accounts
        main_acc = self.db.get(Account, main_id)
        if main_acc:
            main_acc.family_group_id = group_id
            self.db.commit()
            accounts.insert(0, self.account_service._to_dict(main_acc))
        return accounts

    def get_all(self, search: str = "") -> List[Dict]:
        rows = (
            self.db.query(Group, Account.email)
            .outerjoin(Account, Group.main_account_id == Account.id)
            .order_by(Group.name)
            .all()
        )
        result = []
        keyword = search.strip().lower()
        for group, email in rows:
            d = self._to_dict(group, email)
            accounts = self.get_accounts(group.id)
            d["accounts"] = self._ensure_main_account(accounts, group.main_account_id, group.id)
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

    def get_by_id(self, group_id: int) -> Optional[Dict]:
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

    def get_with_accounts(self, group_id: int) -> Optional[Dict]:
        """获取分组详情（含成员列表）"""
        group_dict = self.get_by_id(group_id)
        if group_dict:
            accounts = self.get_accounts(group_id)
            group_dict["accounts"] = self._ensure_main_account(
                accounts, group_dict.get("main_account_id"), group_id
            )
        return group_dict

    def get_accounts(self, group_id: int) -> List[Dict]:
        """获取分组内所有账号"""
        rows = (
            self.db.query(Account)
            .filter(Account.family_group_id == group_id)
            .order_by(Account.email)
            .all()
        )
        return [self.account_service._to_dict(row) for row in rows]

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
        group.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def delete(self, group_id: int):
        group = self.db.get(Group, group_id)
        if group:
            # 先清除关联账号的 family_group_id
            self.db.query(Account).filter(Account.family_group_id == group_id).update(
                {"family_group_id": None}
            )
            self.db.delete(group)
            self.db.commit()

    def add_account(self, group_id: int, account_id: int):
        count = self.db.query(Account).filter(Account.family_group_id == group_id).count()
        if count >= self.MAX_MEMBERS:
            raise ValueError(f"分组最多只能有{self.MAX_MEMBERS}个账号（1个主号+5个子号）")

        account = self.db.query(Account).get(account_id)
        if account:
            account.family_group_id = group_id
            account.updated_at = datetime.now(timezone.utc)
            self.db.commit()

    def remove_account(self, account_id: int):
        account = self.db.query(Account).get(account_id)
        if account:
            account.family_group_id = None
            account.updated_at = datetime.now(timezone.utc)
            self.db.commit()

    def set_main_account(self, group_id: int, account_id: int):
        account = self.db.query(Account).get(account_id)
        if not account or account.family_group_id != group_id:
            raise ValueError("该账号不在指定的分组内")

        group = self.db.get(Group, group_id)
        if group:
            group.main_account_id = account_id
            group.updated_at = datetime.now(timezone.utc)
            self.db.commit()

    # ── 号池管理 ──

    def get_pool_accounts(self, group_id: int) -> List[Dict]:
        """获取分组号池中的账号（不在家庭组中的备用号），附带号池状态

        注意: 此方法是只读的，不修改数据库。过期状态通过内存计算返回给前端。
        """
        rows = (
            self.db.query(Account)
            .filter(
                Account.pool_group_id == group_id,
                Account.family_group_id.is_(None),
            )
            .order_by(Account.pool_use_count.asc(), Account.email)
            .all()
        )
        beijing_tz = ZoneInfo("Asia/Shanghai")
        today_beijing = datetime.now(beijing_tz).date()
        result = []
        for r in rows:
            d = self.account_service._to_dict(r)
            use_count = r.pool_use_count or 0
            pool_status = r.pool_status or ""
            # 惰性计算: 上次使用不是今天 → 显示为废弃
            if pool_status == "" and use_count >= 1 and r.pool_last_used_at:
                last_used_date = r.pool_last_used_at.replace(tzinfo=timezone.utc).astimezone(beijing_tz).date()
                if last_used_date < today_beijing:
                    pool_status = POOL_STATUS_RETIRED
            d["pool_status"] = pool_status
            result.append(d)
        return result

    def add_to_pool(self, group_id: int, account_ids: List[int]) -> int:
        """将账号批量添加到号池"""
        count = 0
        for aid in account_ids:
            account = self.db.query(Account).get(aid)
            if account and account.pool_group_id != group_id:
                account.pool_group_id = group_id
                account.updated_at = datetime.now(timezone.utc)
                count += 1
        self.db.commit()
        return count

    def remove_from_pool(self, group_id: int, account_ids: List[int]) -> int:
        """将账号批量从号池移除"""
        count = 0
        for aid in account_ids:
            account = self.db.query(Account).get(aid)
            if account and account.pool_group_id == group_id:
                account.pool_group_id = None
                account.updated_at = datetime.now(timezone.utc)
                count += 1
        self.db.commit()
        return count

    def mark_pool_unusable(self, account_id: int) -> bool:
        """标记账号为「无法使用」（地区限制等）。返回 True 表示成功。"""
        from core.constants import POOL_STATUS_UNUSABLE
        account = self.db.query(Account).get(account_id)
        if not account:
            return False
        account.pool_status = POOL_STATUS_UNUSABLE
        account.pool_group_id = None  # 移出号池
        account.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def clear_pool_status(self, account_id: int) -> bool:
        """清除号池状态标记，恢复正常。返回 True 表示成功。"""
        account = self.db.query(Account).get(account_id)
        if not account:
            return False
        account.pool_status = ""
        account.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True
