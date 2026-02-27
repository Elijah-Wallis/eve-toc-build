#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.config_adapter import resolve_telemetry_path
from src.runtime.env_loader import load_env_file
from src.runtime.telemetry import Telemetry


def main() -> int:
    load_env_file()
    path = resolve_telemetry_path()
    telemetry = Telemetry(str(path))
    probe_id = f"probe-{int(datetime.now(timezone.utc).timestamp())}"
    telemetry.emit("immutable_probe", {"status": "ok", "probe_id": probe_id})
    print(json.dumps({"ok": True, "probe_id": probe_id, "telemetry_file": str(path)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
