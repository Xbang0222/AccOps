"""运行时配置统一抽象 — 取代散落的 _is_debug_mode / _is_headless_mode / routers.settings._get

所有"运行期可调"配置（区别于启动期 env）走这里：
- 单一数据源 KEYS 字典
- 30 秒 TTL 缓存避免高频 SQL 查询
- service 层不再反向 import router
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigKey:
    key: str
    default: str
    type: type  # bool / str


# 单一配置清单（与 routers/settings.py 的 DEFAULTS / Pydantic 模型对齐）
KEYS: dict[str, ConfigKey] = {
    "debug_mode": ConfigKey("debug_mode", "false", bool),
    "headless_mode": ConfigKey("headless_mode", "false", bool),
    "age_verify_enabled": ConfigKey("age_verify_enabled", "false", bool),
    "default_sms_provider_id": ConfigKey("default_sms_provider_id", "", str),
    "card_number": ConfigKey("card_number", "", str),
    "card_expiry": ConfigKey("card_expiry", "", str),
    "card_cvv": ConfigKey("card_cvv", "", str),
    "card_zip": ConfigKey("card_zip", "", str),
    "cliproxy_base_url": ConfigKey("cliproxy_base_url", "", str),
    "cliproxy_api_key": ConfigKey("cliproxy_api_key", "", str),
}

_CACHE_TTL_SECONDS = 30.0
_cache: dict[str, tuple[float, str]] = {}
_cache_lock = threading.Lock()


def _read_from_db(key: str) -> str:
    """从 config 表读取原始字符串，不存在则返回默认值。"""
    from models.database import get_db_session
    from models.orm import Config

    spec = KEYS.get(key)
    default = spec.default if spec else ""
    try:
        with get_db_session() as db:
            row = db.query(Config).filter(Config.key == key).first()
            return row.value if row else default
    except Exception as e:
        logger.warning(f"[runtime_config] 读取 {key} 失败: {e}")
        return default


def _get_cached(key: str) -> str:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    # 锁外读 DB, 避免长时间持锁阻塞其他线程的命中读取。
    # 注: 缓存失效瞬间可能有多个线程同时穿透 (thundering herd),
    # 配置读取频率不高 + DB 查询轻量, 当前可接受;
    # 如未来频繁场景下成为瓶颈, 可改成 per-key lock 收敛并发回源。
    value = _read_from_db(key)

    with _cache_lock:
        # 双重检查: 期间可能有 set_value 或更早的回源已写入更新的值
        existing = _cache.get(key)
        if existing and time.monotonic() - existing[0] < _CACHE_TTL_SECONDS:
            return existing[1]
        _cache[key] = (now, value)
    return value


def get_str(key: str) -> str:
    """获取字符串配置值（带 30 秒缓存）。"""
    return _get_cached(key)


def get_bool(key: str) -> bool:
    """获取布尔配置值（"true" → True，其他 → False）。"""
    return _get_cached(key) == "true"


def set_value(key: str, value: str) -> None:
    """写入配置值, 然后用新值同步刷新缓存条目。

    实现上是 prime cache (写入 DB 后立即 put 新值) 而非 invalidate, 避免后续读穿透 DB。
    若需严格"失效"语义, 改调用 invalidate(key) + 自然过期。
    """
    from models.database import get_db_session
    from models.orm import Config

    with get_db_session() as db:
        row = db.query(Config).filter(Config.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Config(key=key, value=value))

    with _cache_lock:
        _cache[key] = (time.monotonic(), value)


def invalidate(key: str | None = None) -> None:
    """清空缓存（key 为 None 时清空全部，主要用于测试）。"""
    with _cache_lock:
        if key is None:
            _cache.clear()
        else:
            _cache.pop(key, None)
