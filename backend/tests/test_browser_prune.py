"""BrowserManager 僵尸 instance 清理测试

场景: 用户在桌面 Cmd+Q / 强制退出浏览器后, 后端 _instances 字典里的记录
不会自动消失。is_running / get_running_ids / clean_all_caches 必须能识别
死亡进程并自动清理。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from services.browser import BrowserInstance, BrowserManager


# 不存在的 PID, 用于模拟死亡进程探活返回 False
_FAKE_DEAD_PID = 999_999_999


@dataclass
class _AlivePage:
    """page.process_id 返回当前 python pid (一定存活)"""
    process_id: int = 0
    quit_called: bool = False

    def quit(self) -> None:
        self.quit_called = True


@dataclass
class _DeadPage:
    """page.process_id 返回不可能存在的 pid"""
    process_id: int = _FAKE_DEAD_PID
    quit_called: bool = False

    def quit(self) -> None:
        self.quit_called = True


class _BrokenPage:
    """访问 process_id 抛异常 (浏览器接管失败的极端场景)"""

    @property
    def process_id(self) -> int:
        raise RuntimeError("not connected")

    def quit(self) -> None:
        pass


@pytest.fixture
def manager() -> BrowserManager:
    return BrowserManager()


@pytest.fixture
def safe_terminate(monkeypatch):
    """拦截真实的 SIGTERM 调用, 避免误杀 pytest 进程

    返回一个列表, 记录所有被请求 terminate 的 PID。
    """
    terminated: list[int] = []

    def _fake_terminate(pid):
        if pid is None or pid <= 0:
            return False
        terminated.append(pid)
        return True

    monkeypatch.setattr(BrowserManager, "_terminate_pid", staticmethod(_fake_terminate))
    return terminated


@pytest.fixture(autouse=True)
def _reset_global_browser_manager():
    """每个测试开始/结束都清空全局 browser_manager._instances, 避免污染"""
    from services.browser import browser_manager
    browser_manager._instances.clear()
    yield
    browser_manager._instances.clear()


def test_is_running_returns_false_for_zombie_instance(manager: BrowserManager) -> None:
    manager._instances[42] = BrowserInstance(profile_id=42, page=_DeadPage(), data_dir="")
    assert manager.is_running(42) is False
    assert 42 not in manager._instances


def test_is_running_keeps_alive_instance(manager: BrowserManager) -> None:
    page = _AlivePage(process_id=os.getpid())
    manager._instances[7] = BrowserInstance(profile_id=7, page=page, data_dir="")
    assert manager.is_running(7) is True
    assert 7 in manager._instances


def test_prune_dead_instances_removes_only_dead(manager: BrowserManager) -> None:
    alive = _AlivePage(process_id=os.getpid())
    dead = _DeadPage()
    manager._instances[1] = BrowserInstance(profile_id=1, page=alive, data_dir="")
    manager._instances[2] = BrowserInstance(profile_id=2, page=dead, data_dir="")

    pruned = manager.prune_dead_instances()

    assert pruned == [2]
    assert list(manager._instances.keys()) == [1]
    # 死掉的浏览器进程不应触发 quit (避免 CDP socket 阻塞)
    assert dead.quit_called is False
    # 存活 page 不被关闭
    assert alive.quit_called is False


def test_get_running_ids_auto_prunes(manager: BrowserManager) -> None:
    manager._instances[1] = BrowserInstance(
        profile_id=1, page=_AlivePage(process_id=os.getpid()), data_dir=""
    )
    manager._instances[2] = BrowserInstance(profile_id=2, page=_DeadPage(), data_dir="")

    running = manager.get_running_ids()

    assert running == [1]
    assert 2 not in manager._instances


def test_broken_page_treated_as_dead(manager: BrowserManager) -> None:
    """page.process_id 抛异常时按死亡处理, 不能让 instance 永远卡住"""
    manager._instances[100] = BrowserInstance(profile_id=100, page=_BrokenPage(), data_dir="")
    assert manager.is_running(100) is False
    assert 100 not in manager._instances


def test_process_alive_zero_or_negative_pid() -> None:
    assert BrowserManager._process_alive(0) is False
    assert BrowserManager._process_alive(-1) is False
    assert BrowserManager._process_alive(None) is False  # type: ignore[arg-type]


def test_process_alive_current_process() -> None:
    assert BrowserManager._process_alive(os.getpid()) is True


def test_process_alive_nonexistent_pid() -> None:
    # 极大 pid 在 macOS/Linux 一般不存在
    assert BrowserManager._process_alive(999_999_999) is False


def test_prune_does_not_call_quit_on_dead_page(manager: BrowserManager) -> None:
    """死掉的浏览器进程不应触发 page.quit() (避免 CDP socket 阻塞)"""
    dead = _DeadPage()
    manager._instances[1] = BrowserInstance(profile_id=1, page=dead, data_dir="")
    manager.prune_dead_instances()
    assert dead.quit_called is False


def test_force_clear_all_empty(manager: BrowserManager, safe_terminate) -> None:
    result = manager.force_clear_all()
    assert result == {
        "cleared_alive": [],
        "cleared_dead": [],
        "killed_pids": [],
        "total": 0,
    }
    assert safe_terminate == []


def test_force_clear_all_mixed(manager: BrowserManager, safe_terminate) -> None:
    """存活进程: 应触发 SIGTERM (被 mock 拦截) + 清空记录
    死亡进程: 不调 SIGTERM, 仅清空记录
    """
    alive_pid = os.getpid()
    alive = _AlivePage(process_id=alive_pid)
    dead = _DeadPage()
    manager._instances[1] = BrowserInstance(profile_id=1, page=alive, data_dir="")
    manager._instances[2] = BrowserInstance(profile_id=2, page=dead, data_dir="")

    result = manager.force_clear_all()

    assert sorted(result["cleared_alive"]) == [1]
    assert sorted(result["cleared_dead"]) == [2]
    assert result["killed_pids"] == [alive_pid]
    assert result["total"] == 2
    assert manager._instances == {}
    # SIGTERM 仅对存活进程发出
    assert safe_terminate == [alive_pid]
    # 不再调用 page.quit() (新实现已彻底移除)
    assert alive.quit_called is False
    assert dead.quit_called is False


def test_force_clear_all_returns_immediately(manager: BrowserManager, safe_terminate) -> None:
    """SIGTERM 实现下不应有任何阻塞, 即使存活进程数量大"""
    import time as _time

    for i in range(50):
        manager._instances[i] = BrowserInstance(
            profile_id=i, page=_AlivePage(process_id=os.getpid()), data_dir=""
        )

    start = _time.monotonic()
    result = manager.force_clear_all()
    elapsed = _time.monotonic() - start

    assert elapsed < 0.5, f"force_clear_all 应近乎瞬时返回, 实际 {elapsed:.2f}s"
    assert result["total"] == 50
    assert manager._instances == {}


def test_force_clear_all_terminate_failure_still_clears(
    manager: BrowserManager, monkeypatch
) -> None:
    """SIGTERM 调用失败时, 记录仍应被清空 (force 语义保证状态归零)"""
    monkeypatch.setattr(
        BrowserManager,
        "_terminate_pid",
        staticmethod(lambda pid: False),
    )
    manager._instances[1] = BrowserInstance(
        profile_id=1, page=_AlivePage(process_id=os.getpid()), data_dir=""
    )

    result = manager.force_clear_all()

    assert result["cleared_alive"] == [1]
    assert result["killed_pids"] == []  # SIGTERM 失败不计入
    assert manager._instances == {}


# ── Router 端点契约测试 ────────────────────────────────────


@pytest.fixture
def client():
    """构造无认证的 FastAPI TestClient (verify_token 被替换为 noop)"""
    from fastapi.testclient import TestClient

    from app import app
    from deps import verify_token

    app.dependency_overrides[verify_token] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(verify_token, None)


def test_router_prune_dead_returns_empty(client) -> None:
    resp = client.post("/api/v1/browser-profiles/storage/prune-dead")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"pruned_count": 0, "pruned_profile_ids": []}


def test_router_prune_dead_cleans_zombies(client) -> None:
    from services.browser import browser_manager

    browser_manager._instances[42] = BrowserInstance(
        profile_id=42, page=_DeadPage(), data_dir=""
    )
    resp = client.post("/api/v1/browser-profiles/storage/prune-dead")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pruned_count"] == 1
    assert body["pruned_profile_ids"] == [42]
    assert 42 not in browser_manager._instances


def test_router_force_clear_all(client, safe_terminate) -> None:
    from services.browser import browser_manager

    alive_pid = os.getpid()
    browser_manager._instances[1] = BrowserInstance(
        profile_id=1, page=_AlivePage(process_id=alive_pid), data_dir=""
    )
    browser_manager._instances[2] = BrowserInstance(
        profile_id=2, page=_DeadPage(), data_dir=""
    )
    resp = client.post("/api/v1/browser-profiles/storage/force-clear")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert sorted(body["cleared_alive"]) == [1]
    assert sorted(body["cleared_dead"]) == [2]
    assert body["killed_pids"] == [alive_pid]
    assert browser_manager._instances == {}
    assert safe_terminate == [alive_pid]
