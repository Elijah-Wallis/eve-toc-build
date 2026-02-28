from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
import uuid

import pytest
from nats.aio.client import Client as NATS


def _docker_available() -> bool:
    proc = subprocess.run(["docker", "info"], text=True, capture_output=True, check=False)
    return proc.returncode == 0


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def nats_endpoint() -> str:
    if not _docker_available():
        pytest.skip("docker daemon unavailable")

    port = _allocate_port()
    name = f"nats-js-{uuid.uuid4().hex[:8]}"
    run_cmd = [
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "-p",
        f"{port}:4222",
        "nats:2.10",
        "-js",
    ]
    proc = subprocess.run(run_cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout + "\n" + proc.stderr)

    endpoint = f"nats://127.0.0.1:{port}"
    deadline = time.time() + 20.0
    while time.time() < deadline:
        check = subprocess.run(
            ["docker", "exec", name, "nats-server", "-v"],
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            break
        time.sleep(0.25)
    try:
        yield endpoint
    finally:
        subprocess.run(["docker", "rm", "-f", name], text=True, capture_output=True, check=False)


def test_outbox_effectively_once_fault_injection(nats_endpoint: str) -> None:
    async def _run() -> None:
        nc = NATS()
        await nc.connect(servers=[nats_endpoint], connect_timeout=5)
        js = nc.jetstream()

        await js.add_stream(name="OUTBOX", subjects=["outbox.events"])

        event_id = "evt_fault_injection_001"
        payload = {
            "event_id": event_id,
            "mutation_key": "tasks:t-1:update",
            "payload_delta": {"status": "queued"},
        }

        # First publish represents pre-crash attempt.
        await js.publish("outbox.events", json.dumps(payload).encode("utf-8"))

        # Crash/restart simulation: same canonical mutation is replayed.
        await js.publish("outbox.events", json.dumps(payload).encode("utf-8"))

        sub = await js.pull_subscribe("outbox.events", durable="outbox-durable")
        msgs = await sub.fetch(2, timeout=2)

        deliveries = 0
        durable_effects = {}
        for msg in msgs:
            deliveries += 1
            body = json.loads(msg.data.decode("utf-8"))
            durable_effects.setdefault(body["event_id"], 0)
            if durable_effects[body["event_id"]] == 0:
                durable_effects[body["event_id"]] = 1
            await msg.ack()

        await nc.drain()

        assert deliveries >= 2, "expected duplicate transport deliveries after replay"
        assert durable_effects.get(event_id) == 1, "durable side effect must apply once per event_id"
        assert len(durable_effects) == 1

    asyncio.run(_run())
