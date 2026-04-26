"""自动化共享类型与步骤追踪。"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class CancelledError(Exception):
    """Raised when an automation operation is cancelled by the user."""


class CancellationToken:
    """Thread-safe cancellation token for aborting automation operations."""

    def __init__(self):
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def check(self):
        """Raise CancelledError if cancelled."""
        if self._cancelled.is_set():
            raise CancelledError("操作已被用户取消")


@dataclass
class StepLog:
    step_num: int
    name: str
    status: str
    message: str
    timestamp: str
    duration_ms: int = 0

    def to_dict(self):
        data = {
            "step": self.step_num,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.duration_ms:
            data["duration_ms"] = self.duration_ms
        return data


@dataclass
class AutomationResult:
    success: bool
    message: str
    step: str = ""
    steps: list = field(default_factory=list)
    duration_ms: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        data = {
            "success": self.success,
            "message": self.message,
            "step": self.step,
            "steps": self.steps,
            "duration_ms": self.duration_ms,
        }
        if self.extra:
            data["extra"] = self.extra
        return data


class StepTracker:
    """自动化步骤追踪器。"""

    def __init__(self, task_name: str, on_step: Callable = None):
        self.task_name = task_name
        self.on_step = on_step
        self.steps: list[StepLog] = []
        self._step_counter = 0
        self._start_time = time.time()
        self._step_start = 0.0

    def step(self, name: str, status: str, message: str = ""):
        self._step_counter += 1
        now = datetime.now(UTC).isoformat()
        duration = int((time.time() - self._step_start) * 1000) if self._step_start else 0
        self._step_start = time.time()

        log = StepLog(
            step_num=self._step_counter,
            name=name,
            status=status,
            message=message,
            timestamp=now,
            duration_ms=duration,
        )
        self.steps.append(log)

        icon = {"ok": "✓", "fail": "✗", "skip": "⊘", "info": "ℹ"}.get(status, "?")
        logger.info("[%s] %s Step %s: %s - %s", self.task_name, icon, self._step_counter, name, message)

        if self.on_step:
            try:
                data = log.to_dict()
                data["type"] = "step"
                data["status"] = "running" if status == "info" else status
                self.on_step(data)
            except Exception:
                pass

    def result(self, success: bool, message: str, step: str = "done", extra: dict = None) -> AutomationResult:
        total_ms = int((time.time() - self._start_time) * 1000)
        logger.info("[%s] %s %s (%sms)", self.task_name, "[OK]" if success else "[FAIL]", message, total_ms)

        result = AutomationResult(
            success=success,
            message=message,
            step=step,
            steps=[step_log.to_dict() for step_log in self.steps],
            duration_ms=total_ms,
            extra=extra or {},
        )

        if self.on_step:
            try:
                self.on_step({
                    "type": "result",
                    "success": success,
                    "message": message,
                    "step": step,
                    "duration_ms": total_ms,
                })
            except Exception:
                pass

        return result


@dataclass
class FamilyDiscoverResult:
    success: bool
    has_group: bool = False
    role: str = ""
    members: list = field(default_factory=list)
    member_count: int = 0
    message: str = ""
    cookies_expired: bool = False
    subscription_status: str = ""
    subscription_expiry: str = ""

    def to_dict(self):
        data = {
            "success": self.success,
            "has_group": self.has_group,
            "role": self.role,
            "members": self.members,
            "member_count": self.member_count,
            "message": self.message,
            "subscription_status": self.subscription_status,
        }
        if self.cookies_expired:
            data["cookies_expired"] = True
        return data
