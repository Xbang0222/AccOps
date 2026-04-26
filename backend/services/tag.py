"""标签服务 - 用户自定义标签 CRUD"""
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.orm import Tag, account_tags_table


class TagService:
    """标签业务逻辑"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_dict(tag: Tag, accounts_count: int = 0) -> dict:
        return {
            "id": tag.id,
            "name": tag.name,
            "sort_order": tag.sort_order or 0,
            "accounts_count": accounts_count,
            "created_at": tag.created_at.isoformat() if tag.created_at else None,
            "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
        }

    def list_all(self) -> list[dict]:
        # 一次性算出每个标签关联的账号数（避免 N+1）
        count_rows = (
            self.db.query(
                account_tags_table.c.tag_id,
                func.count(account_tags_table.c.account_id).label("cnt"),
            )
            .group_by(account_tags_table.c.tag_id)
            .all()
        )
        count_map: dict[int, int] = {row.tag_id: row.cnt for row in count_rows}

        rows = (
            self.db.query(Tag)
            .order_by(Tag.sort_order.asc(), Tag.name.asc())
            .all()
        )
        return [self._to_dict(t, count_map.get(t.id, 0)) for t in rows]

    def get_by_id(self, tag_id: int) -> dict | None:
        tag = self.db.get(Tag, tag_id)
        return self._to_dict(tag) if tag else None

    def create(self, name: str) -> int:
        name = (name or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")
        tag = Tag(name=name)
        self.db.add(tag)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"标签 '{name}' 已存在") from None
        self.db.refresh(tag)
        return tag.id

    def update(self, tag_id: int, name: str) -> bool:
        name = (name or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")
        tag = self.db.get(Tag, tag_id)
        if not tag:
            return False
        tag.name = name
        tag.updated_at = datetime.now(UTC)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"标签 '{name}' 已存在") from None
        return True

    def delete(self, tag_id: int) -> bool:
        tag = self.db.get(Tag, tag_id)
        if not tag:
            return False
        self.db.delete(tag)
        self.db.commit()
        return True
