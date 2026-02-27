from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _get(url: str, timeout_s: float = 2.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "eve-dashboard-smoke"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:  # noqa: S310
        return int(r.status), r.read()


def test_dashboard_spa_routes_serve_shell() -> None:
    repo = Path(__file__).resolve().parents[2]
    server = repo / "scripts" / "dashboard" / "health_server.py"
    assert server.exists()

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(server), "--host", "127.0.0.1", "--port", str(port), "--port-max", str(port), "--quiet"],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base = f"http://127.0.0.1:{port}"

    try:
        # Wait for /api/ping.
        deadline = time.time() + 6.0
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                status, body = _get(base + "/api/ping", timeout_s=1.0)
                if status == 200 and b"ok" in body:
                    last_err = None
                    break
            except Exception as e:  # noqa: BLE001
                last_err = e
            time.sleep(0.15)

        assert last_err is None, f"server never became ready: {last_err}"

        routes = [
            "/",
            "/deck",
            "/sop?audience=laymen",
            "/ux?topic=identity_constraints&audience=laymen",
            "/doc?path=README.md&audience=laymen",
            "/doc?path=openclaw_workspace_template/SOUL.md&audience=laymen",
            "/open?path=Business_Code/&audience=laymen",
        ]
        for r in routes:
            status, body = _get(base + r, timeout_s=2.0)
            assert status == 200, f"{r} returned {status}"
            assert b'id=\"app-root\"' in body or b"id='app-root'" in body or b"id=\"app-root\"" in body, f"{r} missing app shell marker"

        # Symlink policy docs should not produce a hard 404 (even if the target doesn't exist yet).
        status, body = _get(base + "/api/fs?path=openclaw_workspace_template/SOUL.md", timeout_s=2.0)
        assert status == 200
        assert b"\"ok\": true" in body
        assert b"\"kind\": \"file\"" in body
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
