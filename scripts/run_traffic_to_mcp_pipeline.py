#!/usr/bin/env python3
from __future__ import annotations

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
from src.runtime.task_engine import TaskEngine
from src.runtime.telemetry import Telemetry
from src.runtime.telegram_router import TelegramRouter


TRAFFIC_FILE = Path(os.path.expanduser("~/.openclaw-eve/runtime/api_traffic.jsonl"))
OUTPUT_ROOT = ROOT / "generated" / "mcp_from_traffic"
MANIFEST_FILE = OUTPUT_ROOT / "manifest.json"
REPORT_FILE = OUTPUT_ROOT / "pipeline_report.json"
VENV_DIR = OUTPUT_ROOT / ".venv"


def run(cmd: List[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, capture_output=True, check=False)


def generate_traffic() -> Dict[str, Any]:
    load_env_file()
    TRAFFIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRAFFIC_FILE.write_text("", encoding="utf-8")

    telemetry = Telemetry(os.path.expanduser("~/.openclaw-eve/runtime/telemetry.jsonl"))
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
        package_dir = Path(tool["package_dir"])
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


def main() -> int:
    traffic = generate_traffic()
    compile_result = compile_from_traffic()
    verify_result = verify_generated_tools()
    report = {
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
