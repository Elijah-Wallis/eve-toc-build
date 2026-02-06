from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from src.runtime.model_router import ModelRouter
from src.runtime.graph_runner import run_graph
from src.runtime.task_engine import TaskEngine
from src.runtime.task_registry import TaskRegistry
from src.runtime.telemetry import Telemetry
from src.runtime.registry_defaults import build_registry
from src.runtime.env_loader import load_env_file


def _json_load(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_registry() -> TaskRegistry:
    return build_registry()


def cmd_tasks(args: argparse.Namespace) -> None:
    telemetry = Telemetry(os.path.expanduser("~/.openclaw-eve/runtime/telemetry.jsonl"))
    registry = _build_registry()
    engine = TaskEngine(registry, telemetry=telemetry)

    if args.tasks_cmd == "enqueue":
        payload = json.loads(args.payload)
        record = engine.enqueue(args.task_type, payload, schedule_for=args.scheduled_for)
        print(json.dumps(record, ensure_ascii=True))
        return

    if args.tasks_cmd == "run_once":
        processed = engine.run_once(limit=args.limit)
        print(json.dumps({"processed": processed}, ensure_ascii=True))
        return

    if args.tasks_cmd == "run_loop":
        engine.run_loop(interval_seconds=args.interval)
        return


def cmd_reports(args: argparse.Namespace) -> None:
    registry = _build_registry()
    handler = registry.get("reports.daily")
    if handler is None:
        raise RuntimeError("reports.daily handler missing")
    output = handler.handler({})
    print(json.dumps(output, ensure_ascii=True))


def cmd_graph(args: argparse.Namespace) -> None:
    data = _json_load(args.graph)
    context = json.loads(args.context)
    thread_name = args.thread_name or "graph"
    result = run_graph(
        data,
        context,
        thread_name,
        os.path.expanduser("~/.openclaw-eve/omega/ledger.jsonl"),
    )
    print(json.dumps(result, ensure_ascii=True))


def cmd_models(_: argparse.Namespace) -> None:
    router = ModelRouter(os.path.expanduser("~/.openclaw-eve/omega/ledger.jsonl"))
    spec, caps = router.pick(provider=os.environ.get("LLM_PROVIDER"))
    print(json.dumps({"model": spec.name, "provider": spec.provider, "caps": caps}, ensure_ascii=True))


def main() -> int:
    load_env_file()
    parser = argparse.ArgumentParser(description="OpenClaw CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tasks = sub.add_parser("tasks")
    tasks_sub = tasks.add_subparsers(dest="tasks_cmd", required=True)
    enqueue = tasks_sub.add_parser("enqueue")
    enqueue.add_argument("task_type")
    enqueue.add_argument("payload")
    enqueue.add_argument("--scheduled-for", default=None)

    run_once = tasks_sub.add_parser("run_once")
    run_once.add_argument("--limit", type=int, default=5)

    run_loop = tasks_sub.add_parser("run_loop")
    run_loop.add_argument("--interval", type=int, default=10)

    reports = sub.add_parser("reports")
    reports.add_argument("--daily", action="store_true", default=True)

    graph = sub.add_parser("graph")
    graph.add_argument("--graph", required=True)
    graph.add_argument("--context", default="{}")
    graph.add_argument("--thread-name", default=None)

    models = sub.add_parser("models")

    args = parser.parse_args()

    if args.cmd == "tasks":
        cmd_tasks(args)
    elif args.cmd == "reports":
        cmd_reports(args)
    elif args.cmd == "graph":
        cmd_graph(args)
    elif args.cmd == "models":
        cmd_models(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
