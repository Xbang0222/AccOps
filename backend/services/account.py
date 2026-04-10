"""账号服务 - 处理账号 CRUD"""
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from models.orm import Account


class AccountService:
    """账号业务逻辑"""

    def __init__(self, db: Session, crypto=None):
        self.db = db

    def _to_dict(self, account: Account, *, _group_cache: dict = None) -> Dict:
        """ORM 对象转字典

        Args:
            _group_cache: 外部传入的 {group_id: Group} 缓存，避免 N+1 查询。
                          为 None 时回退到单次查询（兼容单条调用）。
        """
        from models.orm import Group

        # 判断是否是家庭组管理员 + 成员数
        is_family_owner = False
        family_member_count = 0
        if account.family_group_id:
            if _group_cache is not None:
                group = _group_cache.get(account.family_group_id)
            else:
                group = self.db.get(Group, account.family_group_id)
            if group:
                family_member_count = group.member_count or 0
                if group.main_account_id == account.id:
                    is_family_owner = True

        return {
            "id": account.id,
            "email": account.email,
            "password": account.password or "",
            "recovery_email": account.recovery_email or "",
            "totp_secret": account.totp_secret or "",
            "tags": account.tags or "",
            "group_name": account.group_name or "",
            "family_group_id": account.family_group_id,
            "pool_group_id": account.pool_group_id,
            "is_family_owner": is_family_owner,
            "is_family_pending": bool(account.is_family_pending),
            "family_member_count": family_member_count,
            "subscription_status": account.subscription_status or "",
            "subscription_expiry": account.subscription_expiry or "",
            "has_oauth_credential": bool(account.oauth_credential_json),
            "validation_url": self._get_validation_url(account.oauth_credential_json),
            "notes": account.notes or "",
            "retired_at": account.retired_at.isoformat() if account.retired_at else None,
            "pool_use_count": account.pool_use_count or 0,
            "pool_status": account.pool_status or "",
            "pool_last_used_at": account.pool_last_used_at.isoformat() if account.pool_last_used_at else None,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
        }

    def _get_validation_url(self, oauth_json: str) -> str:
        """从 oauth_credential_json 中提取 validation_url"""
        if not oauth_json:
            return ""
        try:
            cred = json.loads(oauth_json)
            return cred.get("validation_url", "")
        except Exception:
            return ""

    # 允许排序的字段白名单
    SORTABLE_FIELDS = {"email", "created_at", "updated_at", "group_name"}

    def get_all(
        self, search: str = "", group_filter: str = "", tag_filter: str = "",
        page: int = 1, page_size: int = 20, owner_only: bool = False,
        sort_by: str = "created_at", sort_order: str = "desc",
    ) -> tuple[List[Dict], int]:
        from models.orm import Group

        query = self.db.query(Account)

        if search:
            like = f"%{search}%"
            query = query.filter(Account.email.ilike(like) | Account.notes.ilike(like))
        if group_filter:
            query = query.filter(Account.group_name == group_filter)
        if tag_filter:
            query = query.filter(Account.tags.ilike(f"%{tag_filter}%"))
        if owner_only:
            # 仅显示家庭组创建者 (main_account_id 指向自己的账号)
            query = query.filter(
                Account.family_group_id.isnot(None),
                Account.id.in_(
                    self.db.query(Group.main_account_id).filter(Group.main_account_id.isnot(None))
                ),
            )

        # 动态排序（白名单校验防注入）
        if sort_by not in self.SORTABLE_FIELDS:
            sort_by = "created_at"
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"
        column = getattr(Account, sort_by)
        order_clause = column.desc() if sort_order == "desc" else column.asc()
        query = query.order_by(order_clause)

        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()

        # 一次性查出所有相关 Group，避免 _to_dict 里 N+1 查询
        group_ids = {r.family_group_id for r in rows if r.family_group_id}
        group_cache: dict = {}
        if group_ids:
            groups = self.db.query(Group).filter(Group.id.in_(group_ids)).all()
            group_cache = {g.id: g for g in groups}

        return [self._to_dict(row, _group_cache=group_cache) for row in rows], total

    def get_available(self, search: str = "", limit: int = 200, pool_group_id: int = None) -> List[Dict]:
        """获取可邀请的账号：未在家庭组 + 未废弃/不可用 + 使用次数未满 + 当日有效

        如果指定 pool_group_id，只返回该号池的账号。
        """
        from core.constants import POOL_MAX_USE_COUNT
        beijing_tz = ZoneInfo("Asia/Shanghai")
        today_beijing = datetime.now(beijing_tz).date()
        today_start = datetime.combine(today_beijing, datetime.min.time()).replace(tzinfo=beijing_tz)

        # 公共过滤: 未在家庭组 + 状态正常 + 使用次数未满 + 使用日期是今天（或从未使用）
        base_filters = [
            Account.family_group_id.is_(None),
            (Account.pool_status.is_(None)) | (Account.pool_status == ""),
            (Account.pool_use_count.is_(None)) | (Account.pool_use_count < POOL_MAX_USE_COUNT),
            (Account.pool_last_used_at.is_(None)) | (Account.pool_last_used_at >= today_start),
        ]

        if pool_group_id is not None:
            query = self.db.query(Account.id, Account.email).filter(
                Account.pool_group_id == pool_group_id,
                *base_filters,
            )
        else:
            query = self.db.query(Account.id, Account.email).filter(
                Account.pool_group_id.is_(None),
                *base_filters,
            )
        if search:
            query = query.filter(Account.email.ilike(f"%{search}%"))
        # 优先选未用过的号
        query = query.order_by(Account.pool_use_count.asc(), Account.email).limit(limit)
        return [{"id": row.id, "email": row.email} for row in query.all()]

    def get_by_id(self, account_id: int) -> Optional[Dict]:
        row = self.db.get(Account, account_id)
        return self._to_dict(row) if row else None

    def find_by_email(self, email: str) -> Optional[Dict]:
        """通过邮箱查找账号（不区分大小写）"""
        row = self.db.query(Account).filter(Account.email.ilike(email)).first()
        return self._to_dict(row) if row else None

    def create(
        self,
        email: str,
        password: str = "",
        recovery_email: str = "",
        totp_secret: str = "",
        tags: str = "",
        group_name: str = "",
        family_group_id: int = None,
        notes: str = "",
    ) -> int:
        account = Account(
            email=email,
            password=password,
            recovery_email=recovery_email,
            totp_secret=totp_secret,
            tags=tags,
            group_name=group_name,
            family_group_id=family_group_id,
            notes=notes,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account.id

    def update(
        self,
        account_id: int,
        email: str,
        password: str = "",
        recovery_email: str = "",
        totp_secret: str = "",
        tags: str = "",
        group_name: str = "",
        family_group_id: int = None,
        notes: str = "",
    ):
        account = self.db.get(Account, account_id)
        if not account:
            return

        account.email = email
        account.password = password
        account.recovery_email = recovery_email
        account.totp_secret = totp_secret
        account.tags = tags
        account.group_name = group_name
        # 仅在显式传入时更新，避免编辑账号时意外清空分组关联
        if family_group_id is not None:
            account.family_group_id = family_group_id
        account.notes = notes
        account.updated_at = datetime.now(timezone.utc)

        self.db.commit()

    def delete(self, account_id: int):
        account = self.db.get(Account, account_id)
        if account:
            self.db.delete(account)
            self.db.commit()

    def get_all_groups(self) -> List[str]:
        rows = (
            self.db.query(Account.group_name)
            .filter(Account.group_name != "")
            .distinct()
            .order_by(Account.group_name)
            .all()
        )
        return [r[0] for r in rows]

    def get_all_tags(self) -> List[str]:
        rows = (
            self.db.query(Account.tags)
            .filter(Account.tags != "")
            .all()
        )
        all_tags = set()
        for (tags_str,) in rows:
            all_tags.update(t.strip() for t in tags_str.split(",") if t.strip())
        return sorted(all_tags)
