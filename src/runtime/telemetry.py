from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .immutable_log import ImmutableLogWriter


class Telemetry:
    """Lightweight JSONL telemetry logger."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._default_context: Dict[str, Any] = {}
        self.sample_rate = max(0.0, min(1.0, float(os.environ.get("OPENCLAW_TELEMETRY_SAMPLE_RATE", "1"))))
        self.immutable_enabled = os.environ.get("OPENCLAW_IMMUTABLE_LOGS", "1") != "0"
        self.immutable_strict = os.environ.get("OPENCLAW_IMMUTABLE_STRICT", "0") == "1"
        self._fallback_path = self.path.parent / "telemetry_fallback.jsonl"
        fsync_every = max(1, int(os.environ.get("OPENCLAW_IMMUTABLE_FSYNC_EVERY", "1")))
        self._ledger = ImmutableLogWriter(
            self.path,
            enabled=self.immutable_enabled,
            fsync_every=fsync_every,
        )

    def set_context(self, **kwargs: Any) -> None:
        self._default_context.update({k: v for k, v in kwargs.items() if v is not None})

    def clear_context(self, *keys: str) -> None:
        if not keys:
            self._default_context = {}
            return
        for key in keys:
            self._default_context.pop(key, None)

    def new_correlation_id(self, prefix: str = "corr") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:16]}"

    def emit(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        body = dict(payload or {})
        if self.sample_rate <= 0:
            return
        correlation_id = body.get("correlation_id") or self._default_context.get("correlation_id")
        if not correlation_id:
            correlation_id = self.new_correlation_id()
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **self._default_context,
            **body,
            "correlation_id": correlation_id,
        }
        try:
            signed = self._ledger.append(record)
            if not self.immutable_enabled:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(signed, ensure_ascii=True) + "\n")
        except Exception as exc:  # noqa: BLE001
            if self.immutable_strict:
                raise
            fallback = dict(record)
            fallback["immutable_write_error"] = f"{type(exc).__name__}:{exc}"
            with self._fallback_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(fallback, ensure_ascii=True) + "\n")
            print(
                f"[telemetry] immutable write failed; wrote fallback event: {type(exc).__name__}",
                file=sys.stderr,
            )
