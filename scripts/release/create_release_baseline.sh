#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}"
cd "$REPO_ROOT"

fail() {
  echo "ERROR: $1" >&2
  exit 2
}

if [ -n "$(git status --porcelain)" ]; then
  fail "worktree is dirty. Commit/stash changes before creating a release baseline."
fi

if ! docker info >/dev/null 2>&1; then
  fail "docker daemon unavailable. Start Docker because baseline gates include docker-backed checks (AT-018B/AT-034B/AT-035B)."
fi

if ! python3 scripts/acceptance/run_acceptance.py --ids AT-001 >/dev/null; then
  fail "acceptance precheck failed (AT-001). Verify Python/runtime deps, then rerun."
fi

branch="release/baseline-$(date +%Y%m%d)"
tag="baseline-$(date +%Y%m%d-%H%M)"
snapshot_dir="${STATE_DIR}/release_snapshots/${tag}"
mkdir -p "$snapshot_dir"

ids="AT-PRO-001,AT-PRO-002,AT-PRO-003,AT-001,AT-002,AT-003,AT-007,AT-009,AT-011,AT-012,AT-013B,AT-018B,AT-021B,AT-024B,AT-034B,AT-035B"

echo "Running baseline suite: $ids"
python3 scripts/acceptance/run_acceptance.py --ids "$ids" | tee "${snapshot_dir}/gates_run.json" >/dev/null

python3 - "$snapshot_dir" "$branch" "$tag" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

snapshot_dir = Path(sys.argv[1])
branch = sys.argv[2]
tag = sys.argv[3]
run_path = snapshot_dir / "gates_run.json"
run = json.loads(run_path.read_text())
ok = bool(run.get("ok"))

summary = {
    "ok": ok,
    "ids": [r.get("id") for r in run.get("results", [])],
    "failed": [r.get("id") for r in run.get("results", []) if r.get("status") == "fail"],
    "skipped": [r.get("id") for r in run.get("results", []) if r.get("status") == "skip"],
}
(snapshot_dir / "acceptance_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

md = [f"# Baseline {tag}", "", f"- branch: `{branch}`", f"- tag: `{tag}`", f"- ok: `{ok}`", ""]
if summary["failed"]:
    md.append("## Failed Gates")
    for item in summary["failed"]:
        md.append(f"- {item}")
else:
    md.append("## Failed Gates")
    md.append("- none")

(snapshot_dir / "acceptance_summary.md").write_text("\n".join(md) + "\n")

sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
current_branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
repo_size = subprocess.check_output(["du", "-sh", ".git"], text=True).split()[0]

info = {
    "sha": sha,
    "branch": current_branch,
    "target_branch": branch,
    "target_tag": tag,
    "repo_git_size": repo_size,
}
(snapshot_dir / "git_info.json").write_text(json.dumps(info, indent=2) + "\n")

if not ok:
    print("BASELINE_FAILED")
    sys.exit(3)

print("BASELINE_OK")
PY

if [ $? -ne 0 ]; then
  fail "baseline suite failed; snapshot preserved at ${snapshot_dir}"
fi

git branch "$branch"
git tag "$tag"

echo "Baseline snapshot saved: ${snapshot_dir}"
echo "Created branch: ${branch}"
echo "Created tag: ${tag}"
