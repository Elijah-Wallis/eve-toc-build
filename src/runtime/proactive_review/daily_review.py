from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
from zoneinfo import ZoneInfo

from src.runtime.runtime_paths import resolve_proposals_dir
from src.runtime.runtime_paths import resolve_repo_root
from src.runtime.runtime_paths import resolve_reports_dir
from src.runtime.runtime_paths import resolve_state_dir
from src.runtime.revenueops.gate_rev_001 import run_gate as run_revenueops_gate

from . import analyzers
from .memory import ProactiveMemory
from .proposal_engine import ProposalEngine
from .redaction import env_presence
from .redaction import redact_obj
from .repo_indexer import RepoIndexer
from .schemas import CheckRecord
from .schemas import Finding
from .schemas import Heartbeat
from .schemas import ProposalArtifact
from .schemas import ProposalCandidate

AGENT_NAME = "Elijah_EveBot"
CHICAGO_TZ = ZoneInfo("America/Chicago")
MAX_TOP_PROPOSALS = {"fast": 10, "deep": 20}
DEFAULT_SELFTEST = {"fast": "none", "deep": "tiers_ab"}

BLOCKED_GIT_PATTERNS = [
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgh\s+pr\s+create\b"),
    re.compile(r"\bgit\s+pull\s+--rebase\b"),
    re.compile(r"\bgit\s+merge\b"),
]

OFFLINE_BLOCK_PREFIX = {"curl", "wget", "gh"}
OFFLINE_BLOCK_SUBSTRINGS = [
    "npm install",
    "pip install",
    "pip3 install",
    "python -m pip install",
    "python3 -m pip install",
]


class ReviewContext:
    def __init__(self, repo_root: Path, mode: str, profile: str) -> None:
        self.repo_root = repo_root
        self.mode = mode
        self.profile = profile
        self.blocked_actions: List[str] = []
        self.skipped_checks: List[Dict[str, str]] = []
        self.report_sections: Dict[str, Any] = {}
        self.snapshot = RepoIndexer(repo_root).build_snapshot()

    def add_skipped(self, name: str, reason: str) -> None:
        self.skipped_checks.append({"check": name, "reason": reason})

    def _block(self, command: str, reason: str) -> Dict[str, Any]:
        msg = f"blocked: {reason}: {command}"
        self.blocked_actions.append(msg)
        return {
            "status": "blocked",
            "command": command,
            "reason": reason,
            "detail": msg,
            "stdout": "",
            "stderr": "",
            "returncode": 126,
        }

    def _is_offline_network_command(self, command: str) -> str | None:
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        lowered = command.lower()
        if not tokens:
            return None
        if tokens[0] in OFFLINE_BLOCK_PREFIX:
            return f"offline network command blocked: {tokens[0]}"
        for piece in OFFLINE_BLOCK_SUBSTRINGS:
            if piece in lowered:
                return f"offline network install command blocked: {piece}"
        if "http://" in lowered or "https://" in lowered:
            if tokens[0] in {"git", "python", "python3"} and "clone" in tokens and self.repo_root.as_posix() in command:
                return None
            if tokens[0] not in {"git", "python", "python3", "ruff", "pytest", "du", "sed", "rg", "bash", "sh", "ls", "cat"}:
                return "offline external URL egress blocked"
        return None

    def run_cmd(self, command: str, cwd: Path | None = None, timeout: int = 180) -> Dict[str, Any]:
        for pattern in BLOCKED_GIT_PATTERNS:
            if pattern.search(command):
                return self._block(command, "forbidden git remote mutation")

        if self.mode == "offline":
            reason = self._is_offline_network_command(command)
            if reason:
                return self._block(command, reason)

        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd or self.repo_root),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        detail = (proc.stdout + "\n" + proc.stderr).strip()
        if len(detail) > 6000:
            detail = detail[:6000] + "...(truncated)"
        return {
            "status": "pass" if proc.returncode == 0 else "fail",
            "command": command,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "detail": detail,
            "returncode": proc.returncode,
        }


def _slugify(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return out or "proposal"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _risk_tier_for_finding(finding: Finding) -> str:
    if finding.category in {
        "security_hygiene",
        "gate_coverage",
        "identity_firewall",
        "retell_protocol",
        "outbox_semantics",
    }:
        return "C"
    if finding.severity == "high":
        return "B"
    return "A"


def _validation_ids_for_category(category: str) -> List[str]:
    mapping: Dict[str, List[str]] = {
        "repo_hygiene": ["AT-013B"],
        "security_hygiene": ["AT-011", "AT-013B"],
        "gate_coverage": ["AT-001", "AT-002", "AT-003", "AT-007", "AT-009", "AT-011", "AT-012"],
        "architecture_drift": ["AT-021A"],
        "performance_heuristics": ["AT-021B"],
        "docs_drift": ["AT-009"],
        "code_quality": ["AT-009"],
    }
    return mapping.get(category, ["AT-009"])


def _score_pass1(candidate: ProposalCandidate) -> float:
    return (
        candidate.impact * 0.40
        + candidate.confidence * 0.20
        + candidate.testability * 0.20
        - candidate.effort * 0.10
        - candidate.risk * 0.10
    )


def _rank_with_dependencies(candidates: List[ProposalCandidate], limit: int) -> tuple[list[ProposalCandidate], list[ProposalCandidate]]:
    ordered = sorted(candidates, key=lambda item: item.score_pass2, reverse=True)
    by_id = {item.proposal_id: item for item in ordered}
    selected: List[ProposalCandidate] = []
    seen: set[str] = set()

    def add_with_deps(item: ProposalCandidate) -> None:
        for dep_id in item.depends_on:
            dep = by_id.get(dep_id)
            if dep and dep.proposal_id not in seen:
                add_with_deps(dep)
        if item.proposal_id not in seen and len(selected) < limit:
            selected.append(item)
            seen.add(item.proposal_id)

    for item in ordered:
        if len(selected) >= limit:
            break
        add_with_deps(item)

    backlog = [item for item in ordered if item.proposal_id not in seen]
    return selected, backlog


def _bundle_recommendations(top: List[ProposalCandidate]) -> List[Dict[str, Any]]:
    bundles: Dict[str, Dict[str, Any]] = {}
    for item in top:
        key = item.category
        bucket = bundles.setdefault(key, {"bundle": key, "proposal_ids": [], "apply_order": []})
        bucket["proposal_ids"].append(item.proposal_id)
    for bucket in bundles.values():
        ordered = [proposal_id for proposal_id in bucket["proposal_ids"]]
        bucket["apply_order"] = ordered
    return list(bundles.values())


def _build_candidates(findings: List[Finding], memory: ProactiveMemory) -> List[ProposalCandidate]:
    output: List[ProposalCandidate] = []
    for idx, finding in enumerate(findings, start=1):
        proposal_id = f"proposal-{idx:03d}-{_slugify(finding.finding_id)}"
        severity_impact = {"low": 1.5, "medium": 2.5, "high": 3.5}
        risk_val = {"A": 1.2, "B": 2.0, "C": 3.0}
        effort_val = {"low": 1.5, "medium": 2.5, "high": 3.0}
        tier = _risk_tier_for_finding(finding)
        candidate = ProposalCandidate(
            proposal_id=proposal_id,
            title=finding.title,
            category=finding.category,
            why=finding.summary,
            risk_tier=tier,
            impact=severity_impact.get(finding.severity, 2.0),
            effort=effort_val.get(finding.severity, 2.0),
            risk=risk_val.get(tier, 2.0),
            confidence=2.4 if finding.evidence else 1.8,
            testability=2.8 if finding.files else 2.0,
            validation_ids=_validation_ids_for_category(finding.category),
            rollback_plan="Revert by applying inverse patch (`git apply -R change.patch`) or resetting changed files.",
            blast_radius_files=finding.files,
            depends_on=[],
            requires_manual_review=(tier == "C"),
        )
        candidate.score_pass1 = _score_pass1(candidate)
        evidence_hash = _sha(json.dumps(asdict(finding), sort_keys=True))
        candidate.score_pass2 = memory.adjust_score(candidate, evidence_hash)
        if not candidate.validation_ids:
            candidate.score_pass2 -= 2.0
        if not candidate.rollback_plan.strip():
            candidate.score_pass2 -= 1.0
        if not candidate.blast_radius_files:
            candidate.score_pass2 -= 0.5
        output.append(candidate)
    return output


def _render_markdown_report(
    run_id: str,
    report_date: str,
    ctx: ReviewContext,
    findings: List[Finding],
    top: List[ProposalCandidate],
    backlog: List[ProposalCandidate],
    bundles: List[Dict[str, Any]],
    deferred: List[str],
    pre_head: str,
    post_head: str,
) -> str:
    lines: List[str] = []
    lines.append(f"# Elijah_EveBot Morning Update ({report_date})")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- findings: `{len(findings)}`")
    lines.append(f"- top proposals: `{len(top)}`")
    lines.append(f"- blocked actions: `{len(ctx.blocked_actions)}`")
    lines.append(f"- skipped checks: `{len(ctx.skipped_checks)}`")
    lines.append("")

    lines.append("## Repo Delta Snapshot")
    lines.append(f"- pre_head: `{pre_head}`")
    lines.append(f"- post_head: `{post_head}`")
    delta = ctx.report_sections.get("repo_delta", {})
    lines.append(f"- dirty_lines: `{delta.get('dirty_lines', 0)}`")
    recent = delta.get("recent_commits", [])[:5]
    if recent:
        lines.append("- recent commits:")
        for item in recent:
            lines.append(f"  - `{item.get('sha','')[:8]}` {item.get('subject','')}")
    lines.append("")

    lines.append("## RevenueOps Gate")
    rev_gate = ctx.report_sections.get("revenueops_gate", {})
    if rev_gate:
        lines.append(f"- status: `{'PASS' if rev_gate.get('ok') else 'FAIL'}`")
        for metric_key, item in (rev_gate.get("detail") or {}).items():
            lines.append(
                f"- {metric_key}: value={item.get('value')} min={item.get('minimum')} pass={item.get('pass')}"
            )
    else:
        lines.append("- no revenueops gate data")
    lines.append("")

    lines.append("## Risk Signals")
    if findings:
        for finding in findings[:10]:
            lines.append(f"- [{finding.severity}] {finding.title}: {finding.summary}")
    else:
        lines.append("- No high-confidence risk findings in this run.")
    lines.append("")

    lines.append("## Top Proposals")
    if top:
        for idx, proposal in enumerate(top, start=1):
            lines.append(
                f"{idx}. `{proposal.proposal_id}` ({proposal.risk_tier}/{proposal.category}) "
                f"score={proposal.score_pass2:.2f} - {proposal.title}"
            )
            lines.append(f"   - validation: {', '.join(proposal.validation_ids) if proposal.validation_ids else 'none'}")
            lines.append(f"   - rollback: {proposal.rollback_plan}")
    else:
        lines.append("- No proposals generated.")
    lines.append("")

    lines.append("## Backlog Proposals")
    if backlog:
        for proposal in backlog[:20]:
            lines.append(f"- `{proposal.proposal_id}` ({proposal.category}) score={proposal.score_pass2:.2f}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Bundle Recommendations + Dependency Apply Order")
    if bundles:
        for bundle in bundles:
            lines.append(f"- bundle `{bundle['bundle']}`: {', '.join(bundle['apply_order'])}")
    else:
        lines.append("- No dependency bundles identified.")
    lines.append("")

    lines.append("## Deferred / Parked")
    if deferred:
        for item in deferred:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## What I Need From You")
    if any(item.risk_tier == "C" for item in top):
        lines.append("- Review Tier C proposals manually before applying patches.")
    else:
        lines.append("- Confirm priority order for top proposals.")
    lines.append("")

    lines.append("## Blocked Actions + Skipped Checks")
    if ctx.blocked_actions:
        lines.append("- blocked actions:")
        for item in ctx.blocked_actions:
            lines.append(f"  - {item}")
    else:
        lines.append("- blocked actions: none")
    if ctx.skipped_checks:
        lines.append("- skipped checks:")
        for item in ctx.skipped_checks:
            lines.append(f"  - {item['check']}: {item['reason']}")
    else:
        lines.append("- skipped checks: none")
    lines.append("")

    return "\n".join(lines)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_obj(payload), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_obj(text), encoding="utf-8")


def _copy_or_link_latest(latest_path: Path, target_path: Path) -> None:
    if latest_path.exists() or latest_path.is_symlink():
        if latest_path.is_dir() and not latest_path.is_symlink():
            shutil.rmtree(latest_path)
        else:
            latest_path.unlink()
    try:
        latest_path.symlink_to(target_path, target_is_directory=target_path.is_dir())
    except OSError:
        if target_path.is_dir():
            shutil.copytree(target_path, latest_path)
        else:
            shutil.copy2(target_path, latest_path)


def _cleanup_tmp_worktrees(tmp_root: Path, max_age_hours: int = 24) -> None:
    tmp_root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - (max_age_hours * 3600)
    for child in tmp_root.iterdir():
        try:
            if child.stat().st_mtime < cutoff:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        except FileNotFoundError:
            continue


def _git_worktree_prune(repo_root: Path) -> None:
    subprocess.run(["git", "worktree", "prune"], cwd=str(repo_root), check=False, capture_output=True, text=True)


def _proposal_counts(proposals: Sequence[ProposalCandidate]) -> tuple[Dict[str, int], Dict[str, int]]:
    tiers: Dict[str, int] = {"A": 0, "B": 0, "C": 0}
    categories: Dict[str, int] = {}
    for item in proposals:
        tiers[item.risk_tier] = tiers.get(item.risk_tier, 0) + 1
        categories[item.category] = categories.get(item.category, 0) + 1
    return tiers, categories


def _save_heartbeat(path: Path, heartbeat: Heartbeat) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact_obj(asdict(heartbeat)), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _run_feedback(args: argparse.Namespace) -> int:
    state_dir = resolve_state_dir()
    memory_path = state_dir / "proactive_review" / "memory.json"
    memory = ProactiveMemory(memory_path)
    outcome = memory.record_feedback_cli(
        proposal_id=args.proposal_id,
        decision=args.decision,
        notes=args.notes,
        category=args.category,
    )
    print(json.dumps(redact_obj(outcome), indent=2, ensure_ascii=True))
    return 0


def _run_review(args: argparse.Namespace) -> int:
    started = datetime.now(timezone.utc)
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    state_dir = resolve_state_dir()
    heartbeat_path = state_dir / "heartbeat" / "elijah_evebot_heartbeat.json"

    try:
        repo_root = resolve_repo_root()
        reports_root = resolve_reports_dir()
        proposals_root = resolve_proposals_dir()
    except RuntimeError as exc:
        fallback_reports = state_dir / "reports" / "daily"
        date_label = datetime.now(CHICAGO_TZ).date().isoformat()
        error_md = fallback_reports / f"{date_label}_report.md"
        error_json = fallback_reports / f"{date_label}_report.json"
        _write_text(error_md, f"# Elijah_EveBot Morning Update ({date_label})\n\n- error: {exc}\n")
        _write_json(error_json, {"status": "error", "error": str(exc), "run_id": run_id})
        finished = datetime.now(timezone.utc)
        heartbeat = Heartbeat(
            agent=AGENT_NAME,
            run_id=run_id,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_s=max(0.0, (finished - started).total_seconds()),
            status="error",
            repo_commit="",
            dirty_worktree=False,
            gate_summary=[],
            counts={"findings": 0, "proposals_generated": 0, "patches_emitted": 0},
            proposal_counts_by_tier={"A": 0, "B": 0, "C": 0},
            proposal_counts_by_category={},
            blocked_actions=[],
            skipped_checks=[{"check": "artifact_policy", "reason": str(exc)}],
            pointers={
                "report_markdown": str(error_md),
                "report_json": str(error_json),
                "proposals_dir": "",
            },
            notes=["artifact path policy violation"],
        )
        _save_heartbeat(heartbeat_path, heartbeat)
        return 2

    lock_file = state_dir / "locks" / "elijah_evebot.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_file.open("a+")

    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            finished = datetime.now(timezone.utc)
            heartbeat = Heartbeat(
                agent=AGENT_NAME,
                run_id=run_id,
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
                duration_s=max(0.0, (finished - started).total_seconds()),
                status="warning",
                repo_commit="",
                dirty_worktree=False,
                gate_summary=[],
                counts={"findings": 0, "proposals_generated": 0, "patches_emitted": 0},
                proposal_counts_by_tier={"A": 0, "B": 0, "C": 0},
                proposal_counts_by_category={},
                blocked_actions=[],
                skipped_checks=[{"check": "run_lock", "reason": "skipped_run_lock_held"}],
                pointers={"report_markdown": "", "report_json": "", "proposals_dir": ""},
                notes=["lock already held; skipped run"],
            )
            _save_heartbeat(heartbeat_path, heartbeat)
            return 0

        ctx = ReviewContext(repo_root=repo_root, mode=args.mode, profile=args.profile)

        tmp_root = state_dir / "tmp_worktrees"
        _cleanup_tmp_worktrees(tmp_root)
        _git_worktree_prune(repo_root)

        pre_head = ctx.snapshot.head_sha
        pre_status = RepoIndexer.status_signature(ctx.snapshot.dirty_status)

        mode_profile = args.profile
        analyzer_set = analyzers.ANALYZERS_DEEP if mode_profile == "deep" else analyzers.ANALYZERS_FAST

        findings: List[Finding] = []
        deferred: List[str] = []

        for analyzer_mod in analyzer_set:
            try:
                module_findings = analyzer_mod.analyze(ctx)
                findings.extend(module_findings)
            except Exception as exc:  # pragma: no cover - defensive path
                deferred.append(f"{analyzer_mod.__name__}: {exc}")
                ctx.add_skipped(analyzer_mod.__name__, "analyzer_exception")

        env_keys = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "N8N_API_BASE", "N8N_API_KEY"]
        env_status = env_presence(env_keys, dict(os.environ))
        if args.mode == "online" and any(value == "missing" for value in env_status.values()):
            missing = [key for key, value in env_status.items() if value == "missing"]
            ctx.add_skipped("online_checks", f"missing env: {', '.join(missing)}")

        try:
            revenueops_gate = run_revenueops_gate()
        except Exception as exc:  # noqa: BLE001
            revenueops_gate = {
                "gate": "AT-REV-001",
                "ok": False,
                "detail": {},
                "failed_metrics": [],
                "error": str(exc),
            }
        ctx.report_sections["revenueops_gate"] = revenueops_gate

        feedback_path = state_dir / "proposals" / "feedback.json"
        memory = ProactiveMemory(state_dir / "proactive_review" / "memory.json")
        memory_applied = memory.ingest_feedback_file(feedback_path)

        candidates = _build_candidates(findings, memory)
        top, backlog = _rank_with_dependencies(candidates, MAX_TOP_PROPOSALS[mode_profile])
        bundles = _bundle_recommendations(top)

        proposal_selftest = args.proposal_selftest or DEFAULT_SELFTEST[mode_profile]

        today = datetime.now(CHICAGO_TZ).date().isoformat()
        reports_daily = reports_root / "daily"
        proposals_today = proposals_root / today
        proposals_today.mkdir(parents=True, exist_ok=True)

        emitted: List[ProposalArtifact] = []
        if not args.heartbeat_only:
            engine = ProposalEngine(repo_root=repo_root, tmp_root=tmp_root / run_id, run_cmd=ctx.run_cmd)
            for item in top:
                item_dir = proposals_today / _slugify(item.proposal_id)
                artifact = engine.emit_patch(
                    candidate=item,
                    output_dir=item_dir,
                    base_sha=pre_head,
                    proposal_selftest=proposal_selftest,
                    offline_mode=(args.mode == "offline"),
                )
                emitted.append(artifact)

        post_snapshot = RepoIndexer(repo_root).build_snapshot()
        post_head = post_snapshot.head_sha
        post_status = RepoIndexer.status_signature(post_snapshot.dirty_status)

        run_status = "ok"
        notes: List[str] = []
        if post_head != pre_head or post_status != pre_status:
            run_status = "warning"
            notes.append(f"repo modified during run; proposals based on base_sha={pre_head}")

        if ctx.blocked_actions and run_status == "ok":
            run_status = "warning"

        report_json: Dict[str, Any] = {
            "agent": AGENT_NAME,
            "run_id": run_id,
            "mode": args.mode,
            "profile": args.profile,
            "proposal_selftest": proposal_selftest,
            "repo_commit": pre_head,
            "repo": {
                "pre_head": pre_head,
                "post_head": post_head,
                "dirty_worktree_pre": bool(ctx.snapshot.dirty_status.strip()),
                "dirty_worktree_post": bool(post_snapshot.dirty_status.strip()),
            },
            "counts": {
                "findings": len(findings),
                "proposals_generated": len(top) + len(backlog),
                "patches_emitted": len(emitted),
            },
            "findings": [asdict(item) for item in findings],
            "top_proposals": [asdict(item) for item in top],
            "backlog_proposals": [asdict(item) for item in backlog],
            "bundle_recommendations": bundles,
            "blocked_actions": ctx.blocked_actions,
            "skipped_checks": ctx.skipped_checks,
            "deferred": deferred,
            "feedback_applied": memory_applied,
            "analyzer_sections": ctx.report_sections,
            "revenueops_gate": revenueops_gate,
            "env_presence": env_status,
            "notes": notes,
        }

        report_md = _render_markdown_report(
            run_id=run_id,
            report_date=today,
            ctx=ctx,
            findings=findings,
            top=top,
            backlog=backlog,
            bundles=bundles,
            deferred=deferred,
            pre_head=pre_head,
            post_head=post_head,
        )

        report_md_path = reports_daily / f"{today}_report.md"
        report_json_path = reports_daily / f"{today}_report.json"
        _write_text(report_md_path, report_md)
        _write_json(report_json_path, report_json)

        latest_md = reports_daily / "LATEST_REPORT.md"
        latest_json = reports_daily / "LATEST_REPORT.json"
        _write_text(latest_md, report_md)
        _write_json(latest_json, report_json)

        latest_proposals = proposals_root / "LATEST"
        _copy_or_link_latest(latest_proposals, proposals_today)

        tier_counts, category_counts = _proposal_counts(top + backlog)

        memory.mark_run(pre_head)
        memory.save()

        finished = datetime.now(timezone.utc)
        heartbeat = Heartbeat(
            agent=AGENT_NAME,
            run_id=run_id,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_s=max(0.0, (finished - started).total_seconds()),
            status=run_status,
            repo_commit=pre_head,
            dirty_worktree=bool(ctx.snapshot.dirty_status.strip()),
            gate_summary=[asdict(CheckRecord(name="offline_profile", status="pass", detail=f"profile={args.profile}"))],
            counts={
                "findings": len(findings),
                "proposals_generated": len(top) + len(backlog),
                "patches_emitted": len(emitted),
            },
            proposal_counts_by_tier=tier_counts,
            proposal_counts_by_category=category_counts,
            blocked_actions=ctx.blocked_actions,
            skipped_checks=ctx.skipped_checks,
            pointers={
                "report_markdown": str(report_md_path),
                "report_json": str(report_json_path),
                "latest_report_markdown": str(latest_md),
                "latest_report_json": str(latest_json),
                "proposals_dir": str(proposals_today),
                "latest_proposals": str(latest_proposals),
            },
            notes=notes,
        )
        _save_heartbeat(heartbeat_path, heartbeat)

        return 0
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_handle.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Elijah_EveBot proactive daily review loop")
    subparsers = parser.add_subparsers(dest="subcommand")

    feedback = subparsers.add_parser("feedback", help="record proposal feedback")
    feedback.add_argument("--proposal-id", required=True)
    feedback.add_argument("--decision", required=True, choices=["accepted", "rejected", "deferred"])
    feedback.add_argument("--notes", default="")
    feedback.add_argument("--category", default="manual")

    parser.add_argument("--mode", choices=["offline", "online"], default="offline")
    parser.add_argument("--profile", choices=["fast", "deep"], default="fast")
    parser.add_argument("--once", action="store_true", help="run once and exit")
    parser.add_argument("--heartbeat-only", action="store_true")
    parser.add_argument("--proposal-selftest", choices=["none", "tiers_ab", "all"], default="")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.subcommand == "feedback":
        return _run_feedback(args)

    return _run_review(args)


if __name__ == "__main__":
    raise SystemExit(main())
