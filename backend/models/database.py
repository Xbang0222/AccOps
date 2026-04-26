"""数据库引擎与会话管理"""
import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
    pool_timeout=30,
    connect_args={"options": "-c statement_timeout=30000"},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def run_migrations() -> None:
    """Run Alembic migrations to head.

    迁移失败直接 raise（fast-fail），不再回退到 create_all。
    回退会让 schema 静默漂移，比启动失败更难排查。
    """
    from alembic.config import Config

    from alembic import command

    alembic_ini = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    logger.info("[schema] Alembic migrations applied successfully")


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖项：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
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
