"""数据库引擎与会话管理"""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def run_migrations() -> None:
    """Run Alembic migrations to head.

    Falls back to Base.metadata.create_all() if migrations fail
    (e.g. first-time setup without a database).
    """
    try:
        from alembic.config import Config
        from alembic import command

        alembic_ini = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
        alembic_cfg = Config(alembic_ini)
        command.upgrade(alembic_cfg, "head")
        logger.info("[schema] Alembic migrations applied successfully")
    except Exception as e:
        logger.warning(f"[schema] Alembic migration failed ({e}), falling back to create_all")
        from models.orm import Base
        Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI 依赖项：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Context manager for database sessions outside of request context (background tasks).

    Automatically commits on success, rolls back on exception, and always closes.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_account_fields(account_id: int, **fields):
    """Generic single-account field updater for background tasks.

    Opens a session, queries the account, sets the given fields, and commits.
    Automatically sets updated_at to now.
    """
    from models.orm import Account
    with get_db_session() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            for key, value in fields.items():
                setattr(account, key, value)
            account.updated_at = datetime.now(timezone.utc)
