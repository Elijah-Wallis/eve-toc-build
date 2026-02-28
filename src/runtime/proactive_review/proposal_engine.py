from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .redaction import redact_obj
from .schemas import ProposalArtifact, ProposalCandidate


@dataclass
class SelftestResult:
    ran: bool
    result: str
    commands: List[str]
    notes: str


class ProposalEngine:
    def __init__(self, repo_root: Path, tmp_root: Path, run_cmd) -> None:
        self.repo_root = repo_root
        self.tmp_root = tmp_root
        self.run_cmd = run_cmd

    def emit_patch(
        self,
        candidate: ProposalCandidate,
        output_dir: Path,
        base_sha: str,
        proposal_selftest: str,
        offline_mode: bool,
    ) -> ProposalArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        if candidate.proposal_kind == "validate_only":
            selftest = self._run_selftest(self.repo_root, candidate, proposal_selftest, offline_mode)
            changed_files = list(candidate.blast_radius_files)

            markdown_file = output_dir / "proposal.md"
            markdown_file.write_text(self._proposal_markdown(candidate, selftest, changed_files), encoding="utf-8")

            meta_file = output_dir / "meta.json"
            meta_payload: Dict[str, Any] = {
                "proposal_id": candidate.proposal_id,
                "title": candidate.title,
                "category": candidate.category,
                "risk_tier": candidate.risk_tier,
                "proposal_kind": candidate.proposal_kind,
                "execution_commands": candidate.execution_commands,
                "depends_on": candidate.depends_on,
                "base_sha": base_sha,
                "patch_apply_method": "",
                "validation_ids": candidate.validation_ids,
                "rollback_plan": candidate.rollback_plan,
                "blast_radius_files": changed_files,
                "requires_manual_review": candidate.requires_manual_review,
                "selftest_ran": selftest.ran,
                "selftest_result": selftest.result,
                "selftest_commands": selftest.commands,
                "selftest_notes": selftest.notes,
            }
            meta_file.write_text(
                json.dumps(redact_obj(meta_payload), indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )

            return ProposalArtifact(
                proposal_id=candidate.proposal_id,
                proposal_dir=str(output_dir),
                meta_file=str(meta_file),
                markdown_file=str(markdown_file),
                proposal_kind=candidate.proposal_kind,
                execution_commands=list(candidate.execution_commands),
            )

        checkout_dir = self.tmp_root / candidate.proposal_id
        if checkout_dir.exists():
            shutil.rmtree(checkout_dir)

        checkout_mode = str(os.environ.get("OPENCLAW_PROPOSAL_ISOLATION", "worktree")).strip().lower()
        cleanup_cmds: List[Tuple[str, Path | None]] = []

        try:
            if checkout_mode == "clone":
                self._run_or_raise(f"git clone --quiet --no-hardlinks . {checkout_dir}", cwd=self.repo_root)
                self._run_or_raise(f"git -C {checkout_dir} checkout --detach {base_sha}", cwd=self.repo_root)
                cleanup_cmds.append((f"rm -rf {checkout_dir}", self.repo_root))
            else:
                self._run_or_raise(f"git worktree add --detach {checkout_dir} {base_sha}", cwd=self.repo_root)
                cleanup_cmds.append((f"git worktree remove --force {checkout_dir}", self.repo_root))

            self._write_proposal_change(checkout_dir, candidate)

            selftest = self._run_selftest(checkout_dir, candidate, proposal_selftest, offline_mode)

            diff_proc = subprocess.run(
                ["git", "-C", str(checkout_dir), "diff", "--no-color", "--binary", "--full-index"],
                text=True,
                capture_output=True,
                check=False,
            )
            patch_file = output_dir / "change.patch"
            patch_file.write_text(diff_proc.stdout or "", encoding="utf-8")

            changed_files = [line.strip() for line in self._run_or_raise_capture(f"git -C {checkout_dir} diff --name-only").splitlines() if line.strip()]

            markdown_file = output_dir / "proposal.md"
            markdown_file.write_text(self._proposal_markdown(candidate, selftest, changed_files), encoding="utf-8")

            meta_file = output_dir / "meta.json"
            meta_payload: Dict[str, Any] = {
                "proposal_id": candidate.proposal_id,
                "title": candidate.title,
                "category": candidate.category,
                "risk_tier": candidate.risk_tier,
                "proposal_kind": candidate.proposal_kind,
                "execution_commands": candidate.execution_commands,
                "depends_on": candidate.depends_on,
                "base_sha": base_sha,
                "patch_apply_method": "git apply",
                "validation_ids": candidate.validation_ids,
                "rollback_plan": candidate.rollback_plan,
                "blast_radius_files": changed_files or candidate.blast_radius_files,
                "requires_manual_review": candidate.requires_manual_review,
                "selftest_ran": selftest.ran,
                "selftest_result": selftest.result,
                "selftest_commands": selftest.commands,
                "selftest_notes": selftest.notes,
            }
            meta_file.write_text(
                json.dumps(redact_obj(meta_payload), indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )

            apply_script = output_dir / "apply.sh"
            apply_script.write_text(self._apply_script(base_sha), encoding="utf-8")
            apply_script.chmod(0o755)

            return ProposalArtifact(
                proposal_id=candidate.proposal_id,
                proposal_dir=str(output_dir),
                meta_file=str(meta_file),
                markdown_file=str(markdown_file),
                proposal_kind=candidate.proposal_kind,
                execution_commands=list(candidate.execution_commands),
                patch_file=str(patch_file),
                apply_script=str(apply_script),
            )
        finally:
            for cmd, cwd in cleanup_cmds:
                self.run_cmd(cmd, cwd=cwd)
            if checkout_dir.exists():
                shutil.rmtree(checkout_dir, ignore_errors=True)

    def _run_or_raise(self, command: str, cwd: Path) -> None:
        result = self.run_cmd(command, cwd=cwd)
        if result["status"] not in {"pass", "skip"} or result.get("returncode", 1) != 0:
            raise RuntimeError(f"command failed: {command}: {result.get('detail','')}")

    def _run_or_raise_capture(self, command: str) -> str:
        result = self.run_cmd(command, cwd=self.repo_root)
        if result["status"] != "pass" or result.get("returncode", 1) != 0:
            raise RuntimeError(f"command failed: {command}")
        return result.get("stdout", "")

    def _write_proposal_change(self, checkout_dir: Path, candidate: ProposalCandidate) -> None:
        candidate_paths = list(candidate.blast_radius_files) + ["README.md"]
        target: Path | None = None

        for rel in candidate_paths:
            path = checkout_dir / rel
            if path.exists() and path.is_file():
                target = path
                break

        if target is None:
            tracked = subprocess.run(
                ["git", "-C", str(checkout_dir), "ls-files"],
                text=True,
                capture_output=True,
                check=False,
            )
            for rel in tracked.stdout.splitlines():
                path = checkout_dir / rel.strip()
                if path.exists() and path.is_file():
                    target = path
                    break

        if target is None:
            raise RuntimeError("no tracked file available for patch synthesis")

        content = target.read_text(encoding="utf-8", errors="ignore")
        marker = f"\n# proactive-proposal: {candidate.proposal_id}\n"
        if target.suffix.lower() in {".md", ".txt", ".rst"}:
            marker = f"\n<!-- proactive-proposal: {candidate.proposal_id} -->\n"
        if marker not in content:
            target.write_text(content + marker, encoding="utf-8")

    def _run_selftest(
        self,
        checkout_dir: Path,
        candidate: ProposalCandidate,
        proposal_selftest: str,
        offline_mode: bool,
    ) -> SelftestResult:
        if proposal_selftest == "none":
            return SelftestResult(False, "skipped", [], "selftest disabled by profile")
        if proposal_selftest == "tiers_ab" and candidate.risk_tier == "C":
            return SelftestResult(False, "skipped", [], "tier C excluded for tiers_ab")

        commands: List[str] = []
        if candidate.execution_commands:
            commands.extend(candidate.execution_commands)
        elif candidate.validation_ids:
            commands.append(f"python3 scripts/acceptance/run_acceptance.py --ids {','.join(candidate.validation_ids)}")
        if not commands:
            return SelftestResult(False, "skipped", [], "no validation ids for selftest")

        if offline_mode:
            forbidden_tokens = ("AT-018B", "AT-034B", "AT-035B")
            if any(token in ",".join(candidate.validation_ids) for token in forbidden_tokens):
                return SelftestResult(False, "skipped", commands, "network/docker checks skipped in offline mode")

        for cmd in commands:
            result = self.run_cmd(cmd, cwd=checkout_dir)
            if result["status"] != "pass" or result.get("returncode", 1) != 0:
                return SelftestResult(True, "fail", commands, result.get("detail", "selftest failure"))
        return SelftestResult(True, "pass", commands, "all selftests passed")

    def _proposal_markdown(self, candidate: ProposalCandidate, selftest: SelftestResult, changed_files: List[str]) -> str:
        exact_change = "See `change.patch`."
        if candidate.proposal_kind == "validate_only":
            exact_change = "No code patch emitted. Execute the operational validation commands below."

        lines = [
            f"# Proposal: {candidate.title}",
            "",
            "## WHY",
            candidate.why,
            "",
            "## RISK",
            f"Tier: {candidate.risk_tier}",
            f"Blast radius: {len(changed_files)} file(s)",
            "",
            "## EXACT CHANGE",
            exact_change,
            "",
            "## VALIDATION PLAN",
            ", ".join(candidate.validation_ids) if candidate.validation_ids else "None declared",
            "",
        ]

        if candidate.execution_commands:
            lines.extend(
                [
                    "## OPERATIONAL RUNBOOK COMMANDS",
                    *[f"- `{cmd}`" for cmd in candidate.execution_commands],
                    "",
                ]
            )

        lines.extend(
            [
            "## ROLLBACK PLAN",
            candidate.rollback_plan,
            "",
            "## SELFTEST",
            f"ran={selftest.ran} result={selftest.result}",
            f"notes={selftest.notes}",
            "",
            "## CHANGED FILES",
            ]
        )
        lines.extend(f"- {item}" for item in changed_files)
        lines.append("")
        return "\n".join(lines)

    def _apply_script(self, base_sha: str) -> str:
        return f"""#!/usr/bin/env bash
set -euo pipefail
BASE_SHA=\"{base_sha}\"
CURRENT_SHA=$(git rev-parse HEAD)
if [[ \"$CURRENT_SHA\" != \"$BASE_SHA\" ]]; then
  echo \"warning: current HEAD ($CURRENT_SHA) differs from proposal base_sha ($BASE_SHA)\" >&2
fi
git apply --check change.patch || {{
  echo \"git apply --check failed. You may try: git apply --3way change.patch\" >&2
  exit 2
}}
git apply change.patch
"""
