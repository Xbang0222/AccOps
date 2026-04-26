"""pytest 全局 fixture 与配置"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.orm import Base


@pytest.fixture
def db_session():
    """提供一个独立的 SQLite 内存数据库 session, 每个测试函数隔离"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
