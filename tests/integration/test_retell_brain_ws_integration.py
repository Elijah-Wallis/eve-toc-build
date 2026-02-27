from __future__ import annotations

import json
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, List, Tuple

import pytest
from websocket import WebSocketConnectionClosedException
from websocket import WebSocketTimeoutException
from websocket import create_connection


ROOT = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    proc = subprocess.run(["docker", "info"], text=True, capture_output=True, check=False)
    return proc.returncode == 0


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_ws_ready(url: str, timeout_seconds: float = 40.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            ws = create_connection(url, timeout=1.0)
            ws.close()
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"retell brain websocket was not ready at {url}")


@pytest.fixture(scope="module")
def ws_endpoint() -> str:
    if not _docker_available():
        pytest.skip("docker daemon unavailable")

    port = _allocate_port()
    name = f"retell-brain-int-{uuid.uuid4().hex[:8]}"
    run_cmd = [
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "-p",
        f"{port}:8099",
        "-v",
        f"{ROOT}:/workspace",
        "-w",
        "/workspace/services/retell-brain-go",
        "golang:latest",
        "go",
        "run",
        "./cmd/server",
    ]
    proc = subprocess.run(run_cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout + "\n" + proc.stderr)

    endpoint = f"ws://127.0.0.1:{port}/ws/test-call"
    try:
        _wait_for_ws_ready(endpoint, timeout_seconds=80.0)
        yield endpoint
    finally:
        subprocess.run(["docker", "rm", "-f", name], text=True, capture_output=True, check=False)


def _collect_messages(
    ws,
    *,
    timeout_seconds: float,
    stop_when: Callable[[dict], bool] | None = None,
) -> List[Tuple[float, dict]]:
    results: List[Tuple[float, dict]] = []
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            raw = ws.recv()
        except WebSocketTimeoutException:
            continue
        except WebSocketConnectionClosedException:
            break
        payload = json.loads(raw)
        stamp = time.time()
        results.append((stamp, payload))
        if stop_when and stop_when(payload):
            break
    return results


def _content_messages(items: List[Tuple[float, dict]]) -> List[Tuple[float, dict]]:
    return [(ts, msg) for ts, msg in items if "content" in msg]


def test_ws_protocol_exact_semantics(ws_endpoint: str) -> None:
    ws = create_connection(ws_endpoint, timeout=1.0)
    ws.settimeout(0.2)
    try:
        # Scenario A: response_id grouping and content_complete final-only.
        ws.send(json.dumps({"auto_reconnect": False}))
        ws.send(json.dumps({"interaction_type": "response_required", "response_id": "R1"}))
        events = _collect_messages(
            ws,
            timeout_seconds=6.0,
            stop_when=lambda payload: payload.get("response_id") == "R1" and payload.get("content_complete") is True,
        )
        content_events = _content_messages(events)
        assert content_events, "expected streamed content for R1"
        assert all(msg.get("response_id") == "R1" for _, msg in content_events)
        final_count = sum(1 for _, msg in content_events if msg.get("content_complete") is True)
        assert final_count == 1
        assert content_events[-1][1].get("content_complete") is True

        # Scenario B: update_only stops outbound streaming quickly without cancel/discard side-effects.
        ws.send(json.dumps({"interaction_type": "response_required", "response_id": "R1B"}))
        first = _collect_messages(
            ws,
            timeout_seconds=3.0,
            stop_when=lambda payload: payload.get("response_id") == "R1B" and "content" in payload,
        )
        assert _content_messages(first), "expected at least one R1B content chunk before update_only"
        ws.send(json.dumps({"interaction_type": "update_only"}))
        post_update = _collect_messages(ws, timeout_seconds=0.9)
        assert not any(msg.get("response_id") == "R1B" and "content" in msg for _, msg in post_update)

        # Scenario C: new response_id supersedes old generation.
        ws.send(json.dumps({"interaction_type": "response_required", "response_id": "R1C"}))
        _ = _collect_messages(
            ws,
            timeout_seconds=2.0,
            stop_when=lambda payload: payload.get("response_id") == "R1C" and "content" in payload,
        )
        switch_at = time.time()
        ws.send(json.dumps({"interaction_type": "response_required", "response_id": "R2"}))
        after_switch = _collect_messages(
            ws,
            timeout_seconds=6.0,
            stop_when=lambda payload: payload.get("response_id") == "R2" and payload.get("content_complete") is True,
        )
        r2_content = [(ts, msg) for ts, msg in _content_messages(after_switch) if msg.get("response_id") == "R2"]
        assert r2_content, "expected streamed content for R2"
        assert r2_content[-1][1].get("content_complete") is True
        stale_r1 = [
            msg
            for ts, msg in _content_messages(after_switch)
            if ts >= switch_at and msg.get("response_id") == "R1C"
        ]
        assert not stale_r1, "R1C output must stop after R2 supersedes"
    finally:
        ws.close()


def test_ws_keepalive_and_timeout_behavior(ws_endpoint: str) -> None:
    ws = create_connection(ws_endpoint, timeout=1.0)
    ws.settimeout(0.25)
    try:
        ws.send(json.dumps({"auto_reconnect": True}))
        ws.send(json.dumps({"interaction_type": "ping_pong"}))

        # Positive: server emits ping_pong cadence.
        events = _collect_messages(ws, timeout_seconds=5.0)
        pings = [(ts, msg) for ts, msg in events if msg.get("interaction_type") == "ping_pong"]
        assert len(pings) >= 2, "expected regular server ping_pong cadence"

        # Negative: if client stops sending ping_pong, stale heartbeat closes connection.
        closed = False
        deadline = time.time() + 8.0
        while time.time() < deadline:
            try:
                ws.recv()
            except WebSocketTimeoutException:
                continue
            except WebSocketConnectionClosedException:
                closed = True
                break
        assert closed, "expected stale heartbeat connection close after ping_pong silence"
    finally:
        try:
            ws.close()
        except Exception:
            pass
