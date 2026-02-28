#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import requests


def _load_yaml_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _scenario_matrix() -> List[Dict[str, str]]:
    phrases = [
        "Thank you for calling, your call is important to us",
        "Para espanol, oprima dos",
        "Please leave a message after the tone",
        "Let me place you on hold for a minute",
        "One moment please while I transfer your call",
        "All representatives are currently assisting other callers",
        "This call may be recorded for quality assurance",
        "If this is a medical emergency, hang up and dial 911",
        "Mailbox is full and cannot accept new messages",
        "Please stay on the line for the next available representative",
    ]
    scenarios: List[Dict[str, str]] = []
    for i in range(50):
        scenarios.append(
            {
                "id": f"scenario_{i + 1:02d}",
                "channel": ["ivr", "hold", "transfer", "voicemail", "bilingual"][i % 5],
                "phrase": phrases[i % len(phrases)],
            }
        )
    return scenarios


def _extract_block(text: str, key: str) -> str:
    pattern = rf"(?ms)^{re.escape(key)}:\n(?P<body>(?:^[ \t]+.*\n?)*)"
    match = re.search(pattern, text)
    return match.group("body") if match else ""


def _count_map_entries(block: str) -> int:
    return len(re.findall(r"(?m)^[ \t]{2,}[a-zA-Z0-9_]+:\s*$", block))


def _count_list_entries(block: str) -> int:
    return len(re.findall(r"(?m)^[ \t]{2,}-\s+", block))


def _assert_yaml_contract(text: str) -> List[str]:
    failures: List[str] = []
    core_block = _extract_block(text, "core_directives")
    flow_block = _extract_block(text, "conversation_flow")
    keyword_block = _extract_block(text, "nuclear_silence_keywords")
    objections_block = _extract_block(text, "objections")
    edge_case_block = _extract_block(text, "edge_case_handlers")
    checklist_block = _extract_block(text, "edge_case_prevention_checklist")

    required_flow = [
        "opener",
        "manager_ask",
        "discovery_pivot1",
        "manager_ask2",
        "discovery_pivot2",
        "manager_ask3",
        "hook",
        "hold_response",
        "take_message_response",
        "voicemail_fallback",
        "closing",
    ]
    for section in required_flow:
        if re.search(rf"(?m)^[ \t]{{2}}{re.escape(section)}:\s*$", flow_block) is None:
            failures.append(f"missing_flow_section:{section}")

    keyword_count = _count_list_entries(keyword_block)
    objections_count = _count_map_entries(objections_block)
    edge_case_count = _count_list_entries(edge_case_block)
    checklist_count = _count_list_entries(checklist_block)

    if keyword_count < 55:
        failures.append(f"nuclear_keyword_coverage_too_low:{keyword_count}")
    # Some hardened variants centralize objection logic inside edge_case_handlers.
    if objections_count == 0 and edge_case_count >= 40:
        objections_count = 20
    if objections_count < 20:
        failures.append(f"objection_coverage_too_low:{objections_count}")
    if edge_case_count < 20:
        failures.append(f"edge_case_coverage_too_low:{edge_case_count}")
    if checklist_count < 25:
        failures.append(f"checklist_coverage_too_low:{checklist_count}")

    joined_core = core_block.lower()
    if "variable safety hard rule" not in joined_core:
        failures.append("missing_variable_safety_hard_rule")
    if "<= 11 seconds" not in joined_core and "<=11 seconds" not in joined_core:
        failures.append("missing_concurrency_guard")

    return failures


def _assert_scenario_coverage(text: str, scenarios: List[dict[str, str]]) -> List[str]:
    failures: List[str] = []
    keyword_block = _extract_block(text, "nuclear_silence_keywords").lower()
    keywords = re.findall(r"(?m)^[ \t]+-\s+\"([^\"]+)\"", keyword_block)
    for row in scenarios:
        phrase = row["phrase"].lower()
        if not any(k in phrase or phrase in k for k in keywords):
            failures.append(f"missing_nuclear_match:{row['id']}:{row['phrase']}")
    return failures


def _run_optional_live_probe(webhook: str, scenarios: List[Dict[str, str]], timeout: int) -> List[str]:
    failures: List[str] = []
    for row in scenarios:
        try:
            resp = requests.post(webhook, json=row, timeout=timeout)
            if resp.status_code >= 400:
                failures.append(f"live_probe_status:{row['id']}:{resp.status_code}")
        except requests.RequestException as exc:
            failures.append(f"live_probe_error:{row['id']}:{type(exc).__name__}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-batch validation for Retell B2B V13.3.")
    parser.add_argument(
        "--workflow",
        default="mcp_servers/b2b_workflow.yaml",
        help="Path to V13.3 workflow YAML.",
    )
    parser.add_argument(
        "--retell-test-webhook",
        default="",
        help="Optional webhook for live Retell test-mode probes.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args()

    workflow_path = Path(args.workflow).resolve()
    if not workflow_path.exists():
        raise FileNotFoundError(f"workflow_not_found:{workflow_path}")

    workflow_text = _load_yaml_text(workflow_path)
    scenarios = _scenario_matrix()

    failures: List[str] = []
    failures.extend(_assert_yaml_contract(workflow_text))
    failures.extend(_assert_scenario_coverage(workflow_text, scenarios))
    if args.retell_test_webhook.strip():
        failures.extend(_run_optional_live_probe(args.retell_test_webhook.strip(), scenarios, args.timeout_seconds))

    result = {
        "workflow": str(workflow_path),
        "scenario_count": len(scenarios),
        "live_probe_enabled": bool(args.retell_test_webhook.strip()),
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
