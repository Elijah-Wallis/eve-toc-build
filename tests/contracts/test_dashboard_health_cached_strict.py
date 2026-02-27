from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _get_json(url: str, timeout_s: float = 2.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "eve-dashboard-strict-cached"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout_s) as r:  # noqa: S310
        raw = r.read()
    obj = json.loads(raw)
    assert isinstance(obj, dict)
    return obj


def test_health_cached_strict_never_runs_checks() -> None:
    repo = Path(__file__).resolve().parents[2]
    server = repo / "scripts" / "dashboard" / "health_server.py"
    assert server.exists()

    port = _free_port()
    with tempfile.TemporaryDirectory() as td:
        state_dir = Path(td)
        env = os.environ.copy()
        env["OPENCLAW_STATE_DIR"] = str(state_dir)

        proc = subprocess.Popen(
            [sys.executable, str(server), "--host", "127.0.0.1", "--port", str(port), "--port-max", str(port), "--quiet"],
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )

        base = f"http://127.0.0.1:{port}"
        try:
            # Wait for /api/ping.
            deadline = time.time() + 6.0
            last_err: Exception | None = None
            while time.time() < deadline:
                try:
                    obj = _get_json(base + "/api/ping", timeout_s=1.0)
                    if obj.get("ok") is True:
                        last_err = None
                        break
                except Exception as e:  # noqa: BLE001
                    last_err = e
                time.sleep(0.15)
            assert last_err is None, f"server never became ready: {last_err}"

            # Strict cached mode must return quickly and must not write a last-run snapshot.
            obj = _get_json(base + "/api/health?cached=1&strict=1&bundle=", timeout_s=2.0)
            assert obj.get("error") == "no_cached_snapshot"

            # _dashboard_state_dir() may be created by _load_cached(), but strict mode must not write a snapshot.
            last = state_dir / "dashboard" / "health_last_fast.json"
            assert not last.exists(), f"strict cached should not create {last}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
