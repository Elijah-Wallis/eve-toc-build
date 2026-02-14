from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

RiskTier = Literal["A", "B", "C"]
RunStatus = Literal["ok", "warning", "error"]


@dataclass
class Finding:
    finding_id: str
    title: str
    category: str
    severity: Literal["low", "medium", "high"]
    summary: str
    evidence: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class ProposalCandidate:
    proposal_id: str
    title: str
    category: str
    why: str
    risk_tier: RiskTier
    impact: float
    effort: float
    risk: float
    confidence: float
    testability: float
    validation_ids: List[str]
    rollback_plan: str
    blast_radius_files: List[str]
    depends_on: List[str] = field(default_factory=list)
    requires_manual_review: bool = False
    quality_label: str = "READY"
    quality_issues: List[str] = field(default_factory=list)
    score_pass1: float = 0.0
    score_pass2: float = 0.0


@dataclass
class ProposalArtifact:
    proposal_id: str
    proposal_dir: str
    patch_file: str
    meta_file: str
    markdown_file: str
    apply_script: str


@dataclass
class CheckRecord:
    name: str
    status: Literal["pass", "fail", "skip", "blocked"]
    detail: str


@dataclass
class Heartbeat:
    agent: str
    run_id: str
    started_at: str
    finished_at: str
    duration_s: float
    status: RunStatus
    repo_commit: str
    dirty_worktree: bool
    gate_summary: List[Dict[str, Any]]
    counts: Dict[str, int]
    proposal_counts_by_tier: Dict[str, int]
    proposal_counts_by_category: Dict[str, int]
    blocked_actions: List[str]
    skipped_checks: List[Dict[str, str]]
    pointers: Dict[str, str]
    notes: List[str] = field(default_factory=list)


@dataclass
class MemoryState:
    last_run_at: Optional[str] = None
    last_head_sha: Optional[str] = None
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    category_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)


@dataclass
class ReviewRunOutput:
    report_markdown: str
    report_json: Dict[str, Any]
    heartbeat: Heartbeat
    proposals: List[ProposalArtifact]


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)
