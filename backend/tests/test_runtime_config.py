"""runtime_config 缓存 + 读写一致性测试。"""
import time
from unittest.mock import patch

import pytest

from services import runtime_config


@pytest.fixture(autouse=True)
def clear_cache():
    """每个测试隔离缓存。"""
    runtime_config.invalidate()
    yield
    runtime_config.invalidate()


def test_get_str_returns_default_when_key_missing(db_session):
    with patch("models.database.get_db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = db_session
        assert runtime_config.get_str("debug_mode") == "false"


def test_get_bool_translates_true_string(db_session):
    from models.orm import Config
    db_session.add(Config(key="debug_mode", value="true"))
    db_session.commit()

    with patch("models.database.get_db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = db_session
        assert runtime_config.get_bool("debug_mode") is True


def test_get_bool_returns_false_for_other_values(db_session):
    from models.orm import Config
    db_session.add(Config(key="headless_mode", value="false"))
    db_session.commit()

    with patch("models.database.get_db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = db_session
        assert runtime_config.get_bool("headless_mode") is False


def test_cache_avoids_repeated_db_queries(db_session):
    """30 秒 TTL 内重复读取应只查一次 DB。"""
    call_count = {"n": 0}

    def fake_read(key: str) -> str:
        call_count["n"] += 1
        return "cached_value"

    with patch("services.runtime_config._read_from_db", side_effect=fake_read):
        runtime_config.get_str("debug_mode")
        runtime_config.get_str("debug_mode")
        runtime_config.get_str("debug_mode")

    assert call_count["n"] == 1


def test_invalidate_clears_specific_key(db_session):
    call_count = {"n": 0}

    def fake_read(key: str) -> str:
        call_count["n"] += 1
        return "v"

    with patch("services.runtime_config._read_from_db", side_effect=fake_read):
        runtime_config.get_str("debug_mode")
        runtime_config.invalidate("debug_mode")
        runtime_config.get_str("debug_mode")

    assert call_count["n"] == 2


def test_invalidate_all_clears_everything(db_session):
    call_count = {"n": 0}

    def fake_read(key: str) -> str:
        call_count["n"] += 1
        return "v"

    with patch("services.runtime_config._read_from_db", side_effect=fake_read):
        runtime_config.get_str("debug_mode")
        runtime_config.get_str("headless_mode")
        runtime_config.invalidate()  # 清空全部
        runtime_config.get_str("debug_mode")
        runtime_config.get_str("headless_mode")

    assert call_count["n"] == 4


def test_set_value_invalidates_cache(db_session):
    from models.orm import Config

    with patch("models.database.get_db_session") as mock_session:
        mock_session.return_value.__enter__.return_value = db_session
        runtime_config.set_value("debug_mode", "true")
        # 写入后立即读应拿到新值（缓存已被刷新）
        assert runtime_config.get_str("debug_mode") == "true"

    row = db_session.query(Config).filter(Config.key == "debug_mode").first()
    assert row is not None
    assert row.value == "true"


def test_cache_expires_after_ttl(db_session):
    """超过 30 秒 TTL 后应重新查询。"""
    call_count = {"n": 0}

    def fake_read(key: str) -> str:
        call_count["n"] += 1
        return "v"

    # 用 monkeypatch time.monotonic 模拟时间流逝
    real_monotonic = time.monotonic
    fake_time = [real_monotonic()]

    with patch("services.runtime_config._read_from_db", side_effect=fake_read), \
         patch("services.runtime_config.time.monotonic", side_effect=lambda: fake_time[0]):
        runtime_config.get_str("debug_mode")
        fake_time[0] += 31  # 跳过 TTL
        runtime_config.get_str("debug_mode")

    assert call_count["n"] == 2
