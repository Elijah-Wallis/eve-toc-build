#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.env_loader import load_env_file
from src.runtime.registry_defaults import build_registry
from src.runtime.runtime_paths import resolve_generated_dir, resolve_repo_root, state_path
from src.runtime.task_engine import TaskEngine
from src.runtime.telemetry import Telemetry
from src.runtime.telegram_router import TelegramRouter


ROOT = resolve_repo_root()
TRAFFIC_FILE = state_path("runtime", "api_traffic.jsonl")
OUTPUT_ROOT = (resolve_generated_dir() / "mcp_from_traffic").resolve()
MANIFEST_FILE = OUTPUT_ROOT / "manifest.json"
REPORT_FILE = OUTPUT_ROOT / "pipeline_report.json"
VENV_DIR = OUTPUT_ROOT / ".venv"


def run(cmd: List[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, capture_output=True, check=False)


def generate_traffic() -> Dict[str, Any]:
    load_env_file()
    TRAFFIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRAFFIC_FILE.write_text("", encoding="utf-8")

    telemetry = Telemetry(str(state_path("runtime", "telemetry.jsonl")))
    registry = build_registry()
    engine = TaskEngine(registry, telemetry=telemetry)
    router = TelegramRouter()

    commands = ["/status", "/tasks", "/runpack openclaw-apify-ingest", "/runpack openclaw-retell-dispatch", "/runpack openclaw-nurture-run"]
    command_results = {}
    for cmd in commands:
        command_results[cmd] = router.handle(cmd)

    # Process newly enqueued runpack tasks and runtime defaults to force outbound API activity.
    processed = engine.run_once(limit=20)

    # Explicitly enqueue known handlers to guarantee diverse traffic capture.
    engine.enqueue("n8n.trigger", {"workflow": "openclaw-apify-ingest", "data": {}})
    engine.enqueue("n8n.trigger", {"workflow": "openclaw-retell-dispatch", "data": {}})
    engine.enqueue("n8n.trigger", {"workflow": "openclaw-nurture-run", "data": {}})
    engine.enqueue("reports.daily", {})
    processed += engine.run_once(limit=20)

    lines = [line for line in TRAFFIC_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"commands": command_results, "processed": processed, "traffic_lines": len(lines)}


def compile_from_traffic() -> Dict[str, Any]:
    proc = run(
        [
            "python3",
            str(ROOT / "scripts" / "compile_mcp_from_traffic.py"),
            "--traffic-file",
            str(TRAFFIC_FILE),
            "--output-root",
            str(OUTPUT_ROOT),
            "--skills-file",
            str(ROOT / "SKILLS.md"),
            "--manifest-file",
            str(MANIFEST_FILE),
        ]
    )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def verify_generated_tools() -> Dict[str, Any]:
    if not MANIFEST_FILE.exists():
        return {"error": "manifest_missing"}
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    tools = manifest.get("generated_tools", [])
    results = []

    py_bin = shutil.which("python3.12") or shutil.which("python3") or "python3"
    venv_create = run([py_bin, "-m", "venv", str(VENV_DIR)])
    venv_python = VENV_DIR / "bin" / "python"
    pip_proc = run([str(venv_python), "-m", "pip", "install", "mcp"])
    pip_result = {
        "returncode": pip_proc.returncode,
        "stdout": pip_proc.stdout[-2000:],
        "stderr": pip_proc.stderr[-2000:],
        "venv_python": str(venv_python),
        "venv_create_returncode": venv_create.returncode,
    }

    for tool in tools:
        package_dir = _resolve_manifest_path(str(tool["package_dir"]))
        npm_install = run(["npm", "install", "--no-fund", "--no-audit"], cwd=package_dir)
        npm_build = run(["npm", "run", "build"], cwd=package_dir)
        client = run([str(venv_python), "client.py"], cwd=package_dir)
        results.append(
            {
                "tool_name": tool["tool_name"],
                "package_dir": str(package_dir),
                "npm_install": {"returncode": npm_install.returncode, "stderr": npm_install.stderr[-2000:]},
                "npm_build": {"returncode": npm_build.returncode, "stderr": npm_build.stderr[-2000:]},
                "client": {
                    "returncode": client.returncode,
                    "stdout": client.stdout[-4000:],
                    "stderr": client.stderr[-2000:],
                },
            }
        )

    return {"pip_install_mcp": pip_result, "tool_results": results}


def _resolve_manifest_path(value: str) -> Path:
    text = str(value or "")
    if text.startswith("${REPO_ROOT}/"):
        rel = text.replace("${REPO_ROOT}/", "", 1)
        return (ROOT / rel).resolve()
    if text.startswith("${OPENCLAW_STATE_DIR}/"):
        rel = text.replace("${OPENCLAW_STATE_DIR}/", "", 1)
        state_dir = state_path()
        return (state_dir / rel).resolve()
    return Path(text).expanduser().resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run traffic capture -> MCP compile -> verification pipeline.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Run deterministic local smoke path without Supabase-backed traffic.")
    mode.add_argument("--online", action="store_true", help="Run full online path requiring Supabase credentials.")
    return parser.parse_args()


def _supabase_env_ready() -> bool:
    return bool(str(os.environ.get("SUPABASE_URL", "")).strip()) and bool(
        str(os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    )


def _prepare_offline_traffic_file() -> Dict[str, Any]:
    TRAFFIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    seed = {
        "event": "http_traffic",
        "method": "GET",
        "url": "https://example.com/rest/v1/tasks?select=id",
        "path": "/rest/v1/tasks",
        "query": {"select": "id"},
        "request": {"headers": {}, "json": None, "data": None},
    }
    TRAFFIC_FILE.write_text(json.dumps(seed, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"offline_seeded": True, "traffic_lines": 1}


def _compile_for_mode(offline: bool) -> Dict[str, Any]:
    if not offline:
        return compile_from_traffic()
    offline_skills = state_path("generated", "offline_skills.md")
    proc = run(
        [
            "python3",
            str(ROOT / "scripts" / "compile_mcp_from_traffic.py"),
            "--traffic-file",
            str(TRAFFIC_FILE),
            "--output-root",
            str(OUTPUT_ROOT),
            "--skills-file",
            str(offline_skills),
            "--manifest-file",
            str(MANIFEST_FILE),
        ]
    )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "skills_file": str(offline_skills)}


def main() -> int:
    args = parse_args()
    offline = bool(args.offline)
    if not args.offline and not args.online:
        offline = False

    if not offline and not _supabase_env_ready():
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY for --online mode",
                    "hint": "use --offline for deterministic smoke without Supabase",
                },
                ensure_ascii=True,
            )
        )
        return 0

    traffic = _prepare_offline_traffic_file() if offline else generate_traffic()
    compile_result = _compile_for_mode(offline)
    verify_result = verify_generated_tools()
    report = {
        "mode": "offline" if offline else "online",
        "traffic": traffic,
        "compile": compile_result,
        "verify": verify_result,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT_FILE)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
