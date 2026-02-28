from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Deque, Optional, TypeVar

from .telemetry import Telemetry


T = TypeVar("T")


class RuntimeGuard:
    """Step-level runtime envelope for retries/backoff and crash-budget tracking."""

    def __init__(self, telemetry: Optional[Telemetry] = None) -> None:
        self.telemetry = telemetry
        self.enabled = os.environ.get("OPENCLAW_RUNTIME_STABILITY_ENVELOPE", "1") != "0"
        self.max_retries = max(0, int(os.environ.get("OPENCLAW_STEP_MAX_RETRIES", "2")))
        self.backoff_ms = max(10, int(os.environ.get("OPENCLAW_STEP_BACKOFF_MS", "250")))
        self.fatal_budget_per_hour = max(1, int(os.environ.get("OPENCLAW_FATAL_ERROR_BUDGET_PER_HOUR", "50")))
        self._failures: Deque[datetime] = deque()

    def run_step(self, step: str, fn: Callable[[], T], default: Optional[T] = None) -> Optional[T]:
        if not self.enabled:
            return fn()
        for attempt in range(self.max_retries + 1):
            try:
                result = fn()
                if attempt > 0:
                    self._emit(
                        "runtime_step_recovered",
                        {"step": step, "attempt": attempt + 1, "max_retries": self.max_retries},
                    )
                return result
            except Exception as exc:  # noqa: BLE001
                self._record_failure()
                self._emit(
                    "runtime_step_error",
                    {
                        "step": step,
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "error": f"{type(exc).__name__}:{exc}",
                    },
                )
                if attempt >= self.max_retries:
                    break
                backoff = min(15000, self.backoff_ms * (2**attempt))
                time.sleep(backoff / 1000.0)
        self._emit(
            "runtime_step_dropped",
            {
                "step": step,
                "window_failures": self._window_failures(),
                "fatal_budget_per_hour": self.fatal_budget_per_hour,
            },
        )
        return default

    def _record_failure(self) -> None:
        now = datetime.now(timezone.utc)
        self._failures.append(now)
        cutoff = now - timedelta(hours=1)
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
        if self._window_failures() > self.fatal_budget_per_hour:
            self._emit(
                "runtime_error_budget_exceeded",
                {
                    "window_failures": self._window_failures(),
                    "fatal_budget_per_hour": self.fatal_budget_per_hour,
                },
            )

    def _window_failures(self) -> int:
        return len(self._failures)

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self.telemetry:
            self.telemetry.emit(event, payload)
