from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..schemas import Finding

if TYPE_CHECKING:
    from ..daily_review import ReviewContext


def analyze(ctx: ReviewContext) -> List[Finding]:
    findings: List[Finding] = []
    workflows = sorted(Path(ctx.repo_root / "workflows_n8n").glob("*.json"))
    if not workflows:
        return findings

    missing_webhook = []
    for wf in workflows:
        text = wf.read_text(encoding="utf-8", errors="ignore")
        if "webhookId" not in text and "Webhook" in text:
            missing_webhook.append(str(wf.relative_to(ctx.repo_root)))

    if missing_webhook:
        findings.append(
            Finding(
                finding_id="workflow-drift-webhookid",
                title="n8n workflow drift: webhook metadata missing",
                category="workflow_drift",
                severity="medium",
                summary="One or more workflows appear to lack webhook identifiers used for registration/repair checks.",
                evidence=missing_webhook[:10],
                files=missing_webhook[:10],
                suggestion="Reconcile workflow exports and regenerate webhook metadata contract checks.",
            )
        )

    ctx.report_sections["workflow_drift"] = {
        "workflow_count": len(workflows),
        "missing_webhook_count": len(missing_webhook),
        "missing_webhook_examples": missing_webhook[:5],
    }
    return findings
