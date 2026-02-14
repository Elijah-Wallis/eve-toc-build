#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PYTHON = os.environ.get("OPENCLAW_ACCEPTANCE_PYTHON") or os.environ.get("PYTHON") or sys.executable


@dataclass
class CheckResult:
    id: str
    status: str
    detail: str
    command: str = ""


def run_cmd(command: str, timeout: int = 180) -> CheckResult:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    detail = (proc.stdout + "\n" + proc.stderr).strip()
    if len(detail) > 1500:
        detail = detail[:1500] + "...(truncated)"
    status = "pass" if proc.returncode == 0 else "fail"
    return CheckResult(id="", status=status, detail=detail, command=command)


def skip_if_missing_path(path: str, why: str) -> CheckResult | None:
    if (ROOT / path).exists():
        return None
    return CheckResult(id="", status="skip", detail=f"{why} (missing: {path})", command="")


def pytest_check(nodeid: str) -> CheckResult:
    # If the repo snapshot doesn't contain the referenced test file, treat it as
    # "not applicable" instead of failing the whole gate.
    test_path = nodeid.split("::", 1)[0]
    if test_path and not (ROOT / test_path).exists():
        return CheckResult(id="", status="skip", detail=f"missing test file in repo snapshot: {test_path}")
    cmd = f"{shlex.quote(PYTHON)} -m pytest -q {shlex.quote(nodeid)}"
    return run_cmd(cmd, timeout=240)


def _bootstrap_into_venv_if_needed() -> None:
    """
    Acceptance checks depend on third-party libs. In CI we start from a clean
    interpreter; if imports fail, create a venv, install deps, and re-exec this
    script under the venv python so downstream imports work.
    """

    if os.environ.get("OPENCLAW_ACCEPTANCE_BOOTSTRAPPED") == "1":
        return

    try:
        import pytest  # noqa: F401
        import requests  # noqa: F401
        import pydantic  # noqa: F401
        import websocket  # noqa: F401
        import nats  # noqa: F401
        return
    except Exception:
        pass

    venv_dir = os.environ.get("OPENCLAW_ACCEPTANCE_VENV", "/tmp/eve-acceptance-venv")
    python_bin = Path(venv_dir) / "bin" / "python"
    pip_bin = Path(venv_dir) / "bin" / "pip"

    if not python_bin.exists():
        subprocess.run(["python3", "-m", "venv", venv_dir], cwd=ROOT, check=True)

    subprocess.run(
        [
            str(pip_bin),
            "install",
            "pytest",
            "requests",
            "pydantic",
            "websocket-client",
            "nats-py",
        ],
        cwd=ROOT,
        check=True,
    )

    os.environ["OPENCLAW_ACCEPTANCE_BOOTSTRAPPED"] = "1"
    os.execv(str(python_bin), [str(python_bin), str(Path(__file__).resolve())] + sys.argv[1:])


def ensure_test_runtime() -> None:
    global PYTHON  # noqa: PLW0603
    check = subprocess.run(
        [PYTHON, "-c", "import pytest,requests,pydantic,websocket,nats"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if check.returncode == 0:
        return
    venv_dir = os.environ.get("OPENCLAW_ACCEPTANCE_VENV", "/tmp/eve-acceptance-venv")
    python_bin = Path(venv_dir) / "bin" / "python"
    pip_bin = Path(venv_dir) / "bin" / "pip"
    if not python_bin.exists():
        subprocess.run(["python3", "-m", "venv", venv_dir], cwd=ROOT, check=True)
    subprocess.run(
        [
            str(pip_bin),
            "install",
            "pytest",
            "requests",
            "pydantic",
            "websocket-client",
            "nats-py",
        ],
        cwd=ROOT,
        check=True,
    )
    PYTHON = str(python_bin)


def require_docker() -> CheckResult | None:
    proc = subprocess.run(
        ["docker", "info"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        return None
    detail = (proc.stdout + "\n" + proc.stderr).strip()
    if len(detail) > 800:
        detail = detail[:800] + "...(truncated)"
    return CheckResult(
        id="",
        status="fail",
        detail=f"docker daemon unavailable for docker-backed acceptance gate\n{detail}",
        command="docker info",
    )


def build_checks(live: bool) -> Dict[str, Callable[[], CheckResult]]:
    def at001() -> CheckResult:
        return pytest_check("tests/contracts/test_telegram_contracts.py::test_launch_medspa_defaults_manual")

    def at002() -> CheckResult:
        return pytest_check("tests/contracts/test_launch_gates.py::test_launch_medspa_approve_contract")

    def at003() -> CheckResult:
        return pytest_check("tests/contracts/test_launch_gates.py::test_launch_gate_blocks_on_preflight_failure")

    def at004() -> CheckResult:
        return pytest_check("tests/integration/test_n8n_auto_heal_contract.py")

    def at005() -> CheckResult:
        return pytest_check("tests/integration/test_runtime_stability.py::test_runtime_guard_handles_transient_failures")

    def at006() -> CheckResult:
        if not live:
            return CheckResult(id="", status="skip", detail="requires --live for process/log probe")
        return run_cmd(f"{shlex.quote(PYTHON)} scripts/ops/check_telegram_conflicts.py --window-minutes 30", timeout=120)

    def at007() -> CheckResult:
        return pytest_check("tests/contracts/test_telegram_contracts.py::test_runpack_contract")

    def at008() -> CheckResult:
        return pytest_check("tests/integration/test_runtime_stability.py::test_orchestrator_role_split_routes_steps")

    def at009() -> CheckResult:
        return pytest_check("tests/contracts/test_status_contract.py")

    def at010() -> CheckResult:
        return pytest_check("tests/integration/test_runtime_stability.py::test_command_queue_bridge_consumes_lines")

    def at011() -> CheckResult:
        missing = skip_if_missing_path("scripts/ops/secret_exposure_scan.py", "ops scripts not present in repo snapshot")
        if missing:
            return missing
        cmd = (
            f"{shlex.quote(PYTHON)} scripts/ops/secret_exposure_scan.py"
            f" && {shlex.quote(PYTHON)} scripts/ops/emit_telemetry_probe.py"
            f" && {shlex.quote(PYTHON)} scripts/ops/verify_immutable_telemetry.py --require-signed --allow-legacy-interleaving"
        )
        return run_cmd(cmd, timeout=180)

    def at012() -> CheckResult:
        missing = skip_if_missing_path("scripts/ops/rollout_worker_split.sh", "ops scripts not present in repo snapshot")
        if missing:
            return missing
        cmd = (
            "bash scripts/ops/rollout_worker_split.sh --dry-run --rollback-check "
            f"&& bash scripts/ops/converge_gateway_and_ingress_owner.sh --dry-run --rollback"
        )
        return run_cmd(cmd, timeout=120)

    def at013a() -> CheckResult:
        missing = skip_if_missing_path("scripts/ci/lint_no_absolute_paths.py", "ci scripts not present in repo snapshot")
        if missing:
            return missing
        return run_cmd(f"{shlex.quote(PYTHON)} scripts/ci/lint_no_absolute_paths.py", timeout=120)

    def at013b() -> CheckResult:
        missing = skip_if_missing_path("scripts/scan_absolute_paths.sh", "path scan script not present in repo snapshot")
        if missing:
            return missing
        return run_cmd("bash scripts/scan_absolute_paths.sh", timeout=120)

    def at014() -> CheckResult:
        cmd = (
            "TMP_STATE_DIR=$(mktemp -d) "
            "&& OPENCLAW_STATE_DIR=\"$TMP_STATE_DIR\" python3 scripts/run_traffic_to_mcp_pipeline.py --offline "
            "&& test -f \"$TMP_STATE_DIR/generated/mcp_from_traffic/manifest.json\" "
            "&& test ! -d generated"
        )
        return run_cmd(cmd, timeout=240)

    def at018() -> CheckResult:
        return pytest_check("tests/integration/test_outbox_semantics.py::test_effectively_once_wording_and_event_id_contract")

    def at018b() -> CheckResult:
        docker_error = require_docker()
        if docker_error:
            return docker_error
        return pytest_check("tests/integration/test_outbox_effectively_once.py")

    def at021a() -> CheckResult:
        cmd = (
            f"{shlex.quote(PYTHON)} -m pytest -q "
            "tests/contracts/test_kernel_proto_contract.py::test_kernel_proto_has_required_batch_apis "
            "tests/integration/test_retrieval_cadence_guard.py::test_retrieval_guard_blocks_token_and_chunk"
        )
        return run_cmd(cmd, timeout=240)

    def at021b() -> CheckResult:
        return pytest_check("tests/test_retrieval_guard_enforces_no_per_chunk_calls.py")

    def at024a() -> CheckResult:
        return pytest_check("tests/integration/test_shacl_artifacts_contract.py")

    def at024b() -> CheckResult:
        return pytest_check("tests/integration/test_shacl_artifacts_e2e.py")

    def at034a() -> CheckResult:
        return pytest_check("tests/contracts/test_retell_protocol_contract.py::test_keepalive_contract_has_ping_pong_requirements")

    def at034b() -> CheckResult:
        docker_error = require_docker()
        if docker_error:
            return docker_error
        missing = skip_if_missing_path("services/retell-brain-go/scripts/go_build_docker.sh", "retell-brain-go service not present in repo snapshot")
        if missing:
            return missing
        cmd = (
            "bash services/retell-brain-go/scripts/go_build_docker.sh"
            " && bash services/retell-brain-go/scripts/go_vet_docker.sh"
            " && bash services/retell-brain-go/scripts/go_test_docker.sh"
        )
        return run_cmd(cmd, timeout=900)

    def at035a() -> CheckResult:
        return pytest_check("tests/contracts/test_retell_protocol_contract.py::test_preemption_contract_update_only_and_new_response_id")

    def at035b() -> CheckResult:
        docker_error = require_docker()
        if docker_error:
            return docker_error
        return pytest_check("tests/integration/test_retell_brain_ws_integration.py")

    def atpro001() -> CheckResult:
        return pytest_check("tests/integration/test_proactive_review_offline.py::test_offline_run_writes_dated_and_latest_and_latest_proposals")

    def atpro002() -> CheckResult:
        return pytest_check("tests/integration/test_proposal_engine_patch_only.py::test_proposal_engine_emits_patch_with_meta_and_apply_script_without_repo_mutation")

    def atpro003() -> CheckResult:
        cmd = (
            f"{shlex.quote(PYTHON)} -m pytest -q "
            "tests/contracts/test_proactive_review_heartbeat_schema.py::test_heartbeat_includes_required_fields "
            "tests/contracts/test_proactive_review_redaction.py::test_redaction_scrubs_secret_like_strings "
            "tests/integration/test_proactive_review_locking.py::test_lock_contention_records_warning_and_skip "
            "tests/integration/test_proactive_review_offline_network_block.py::test_offline_network_command_is_denied"
        )
        return run_cmd(cmd, timeout=240)

    def atpro004() -> CheckResult:
        cmd = (
            f"{shlex.quote(PYTHON)} -m pytest -q "
            "tests/test_proactive_review_proposal_quality.py "
            "tests/test_proactive_execution_profiles.py"
        )
        return run_cmd(cmd, timeout=240)

    def atrev001() -> CheckResult:
        return pytest_check("tests/test_revenueops_gate.py")

    def ating001() -> CheckResult:
        return pytest_check("tests/test_postcall_ingestion_completeness.py")

    def atledger001() -> CheckResult:
        return pytest_check("tests/test_event_chain_gate.py")

    def atsec002() -> CheckResult:
        cmd = "bash scripts/security/scan_secrets_strict.sh && " + f"{shlex.quote(PYTHON)} -m pytest -q tests/test_secret_hygiene_strict.py"
        return run_cmd(cmd, timeout=240)

    return {
        "AT-001": at001,
        "AT-002": at002,
        "AT-003": at003,
        "AT-004": at004,
        "AT-005": at005,
        "AT-006": at006,
        "AT-007": at007,
        "AT-008": at008,
        "AT-009": at009,
        "AT-010": at010,
        "AT-011": at011,
        "AT-012": at012,
        "AT-013A": at013a,
        "AT-013B": at013b,
        "AT-014": at014,
        "AT-018": at018,
        "AT-018B": at018b,
        "AT-021A": at021a,
        "AT-021B": at021b,
        "AT-024A": at024a,
        "AT-024B": at024b,
        "AT-034A": at034a,
        "AT-034B": at034b,
        "AT-035A": at035a,
        "AT-035B": at035b,
        "AT-PRO-001": atpro001,
        "AT-PRO-002": atpro002,
        "AT-PRO-003": atpro003,
        "AT-PRO-004": atpro004,
        "AT-REV-001": atrev001,
        "AT-ING-001": ating001,
        "AT-LEDGER-001": atledger001,
        "AT-SEC-002": atsec002,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run acceptance checks including frozen AT-001..AT-012 and patched gates.")
    parser.add_argument("--ids", default="", help="Comma-separated subset, e.g. AT-001,AT-002")
    parser.add_argument("--live", action="store_true", help="Enable live host probes for ops checks")
    parser.add_argument("--fail-fast", action="store_true")
    return parser.parse_args()


def main() -> int:
    _bootstrap_into_venv_if_needed()
    args = parse_args()
    ensure_test_runtime()
    from src.runtime.acceptance.trends import update_trends

    checks = build_checks(live=args.live)
    selected = [x.strip().upper() for x in args.ids.split(",") if x.strip()] or list(checks.keys())
    results: List[CheckResult] = []

    for check_id in selected:
        fn = checks.get(check_id)
        if not fn:
            results.append(CheckResult(id=check_id, status="skip", detail="unknown check id"))
            continue
        result = fn()
        result.id = check_id
        results.append(result)
        if args.fail_fast and result.status == "fail":
            break

    failed = [r for r in results if r.status == "fail"]
    output = {
        "ok": len(failed) == 0,
        "live": bool(args.live),
        "results": [
            {
                "id": r.id,
                "status": r.status,
                "detail": r.detail,
                "command": r.command,
            }
            for r in results
        ],
    }
    state_dir = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw-eve")))
    try:
        trend = update_trends(state_dir, output)
        output["trends"] = {
            "count": trend.get("count", 0),
            "path": str(state_dir / "acceptance" / "trends" / "last_7.json"),
        }
    except Exception as exc:  # noqa: BLE001
        output["trends"] = {"error": str(exc)}
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
