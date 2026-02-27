from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .schemas import MemoryState, ProposalCandidate


class ProactiveMemory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = MemoryState()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.state = MemoryState(
            last_run_at=payload.get("last_run_at"),
            last_head_sha=payload.get("last_head_sha"),
            outcomes=payload.get("outcomes", []),
            category_stats=payload.get("category_stats", {}),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "last_run_at": self.state.last_run_at,
                    "last_head_sha": self.state.last_head_sha,
                    "outcomes": self.state.outcomes,
                    "category_stats": self.state.category_stats,
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def mark_run(self, head_sha: str) -> None:
        self.state.last_head_sha = head_sha
        self.state.last_run_at = datetime.now(timezone.utc).isoformat()

    def ingest_feedback_file(self, feedback_path: Path) -> List[Dict[str, Any]]:
        if not feedback_path.exists():
            return []
        payload = json.loads(feedback_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            payload = [payload]
        applied: List[Dict[str, Any]] = []
        for item in payload:
            proposal_id = str(item.get("proposal_id", "")).strip()
            decision = str(item.get("decision", "")).strip().lower()
            if not proposal_id or decision not in {"accepted", "rejected", "deferred"}:
                continue
            outcome = {
                "proposal_id": proposal_id,
                "decision": decision,
                "notes": str(item.get("notes", "")),
                "category": str(item.get("category", "unknown")),
                "evidence_hash": str(item.get("evidence_hash", "")),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            self.record_outcome(outcome)
            applied.append(outcome)
        if applied:
            archived = feedback_path.with_suffix(feedback_path.suffix + ".processed")
            feedback_path.rename(archived)
        return applied

    def record_outcome(self, outcome: Dict[str, Any]) -> None:
        self.state.outcomes.append(outcome)
        category = str(outcome.get("category", "unknown"))
        decision = str(outcome.get("decision", "deferred"))
        stats = self.state.category_stats.setdefault(category, {"accepted": 0, "rejected": 0, "deferred": 0})
        stats[decision] = int(stats.get(decision, 0)) + 1

    def record_feedback_cli(self, proposal_id: str, decision: str, notes: str, category: str = "manual") -> Dict[str, Any]:
        item = {
            "proposal_id": proposal_id,
            "decision": decision,
            "notes": notes,
            "category": category,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "evidence_hash": "",
        }
        self.record_outcome(item)
        self.save()
        return item

    def adjust_score(self, proposal: ProposalCandidate, evidence_hash: str) -> float:
        score = proposal.score_pass1
        category_stats = self.state.category_stats.get(proposal.category, {})
        accepted = int(category_stats.get("accepted", 0))
        rejected = int(category_stats.get("rejected", 0))
        score += min(accepted * 0.15, 1.5)
        score -= min(rejected * 0.1, 1.0)

        for outcome in reversed(self.state.outcomes):
            if outcome.get("proposal_id") != proposal.proposal_id:
                continue
            if outcome.get("decision") == "rejected" and outcome.get("evidence_hash") == evidence_hash:
                score -= 5.0
            break
        return score
