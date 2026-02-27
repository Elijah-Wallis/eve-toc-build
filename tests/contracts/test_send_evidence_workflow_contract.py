from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / "workflows_n8n" / "openclaw_retell_fn_send_evidence_package.json"


def _nodes_by_name(workflow: dict) -> dict:
    return {str(node.get("name") or ""): node for node in workflow.get("nodes", [])}


def test_send_evidence_workflow_exists_and_has_expected_identity() -> None:
    assert WORKFLOW_PATH.exists(), f"missing workflow file: {WORKFLOW_PATH}"
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert workflow.get("name") == "openclaw_retell_fn_send_evidence_package"

    webhook_nodes = [n for n in workflow.get("nodes", []) if n.get("type") == "n8n-nodes-base.webhook"]
    assert webhook_nodes, "workflow must include a webhook trigger"
    webhook_path = ((webhook_nodes[0].get("parameters") or {}).get("path") or "").strip()
    assert webhook_path == "openclaw-retell-fn-send-evidence-package"


def test_send_evidence_workflow_enforces_guardrails_and_persists_package_event() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    nodes = _nodes_by_name(workflow)

    for required in [
        "Normalize Request",
        "Guardrail OK?",
        "Send Evidence Email",
        "Send Evidence SMS",
        "Prepare Package Event",
        "Insert Package Event",
    ]:
        assert required in nodes, f"missing required node: {required}"

    normalize_code = str((nodes["Normalize Request"].get("parameters") or {}).get("functionCode") or "")
    assert "recipient_email" in normalize_code
    assert "delivery_method" in normalize_code
    assert "artifact_type" in normalize_code
    assert "EMAIL_AND_SMS" in normalize_code

    package_code = str((nodes["Prepare Package Event"].get("parameters") or {}).get("functionCode") or "")
    assert "retell_evidence_package" in package_code
    assert "email_status" in package_code
    assert "sms_status" in package_code
