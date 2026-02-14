#!/usr/bin/env python3
"""
Build a single Markdown "context bundle" containing the Voice Agent codebase.

Gemini (and other air-gapped reviewers) can't fetch GitHub branches, so this
produces a plain-text file that can be copy/pasted.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]


LANG_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sh": "bash",
    ".rb": "ruby",
    ".txt": "text",
    ".csv": "csv",
}


EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".DS_Store",
}


def _git(cmd: list[str]) -> str | None:
    try:
        out = subprocess.check_output(cmd, cwd=SERVICE_ROOT, stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def _language_for(path: Path) -> str:
    return LANG_BY_SUFFIX.get(path.suffix.lower(), "")


def _should_skip(path: Path, out_path: Path) -> bool:
    if path.name in EXCLUDE_DIR_NAMES:
        return True
    # Never include the generated output in itself.
    try:
        if path.resolve() == out_path.resolve():
            return True
    except Exception:
        pass
    return False


def _iter_files(base: Path, out_path: Path) -> list[Path]:
    files: list[Path] = []
    for p in base.rglob("*"):
        if _should_skip(p, out_path):
            continue
        if any(part in EXCLUDE_DIR_NAMES for part in p.parts):
            continue
        if p.is_dir():
            continue
        files.append(p)
    files.sort(key=lambda x: str(x).lower())
    return files


@dataclass(frozen=True)
class BundleSpec:
    title: str
    include_paths: list[Path]
    out_path: Path


def build_bundle(spec: BundleSpec) -> None:
    branch = _git(["git", "branch", "--show-current"])
    commit = _git(["git", "rev-parse", "HEAD"])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_path = spec.out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {spec.title}")
    lines.append("")
    lines.append("This is a plain-text bundle intended for air-gapped review.")
    lines.append("")
    lines.append("## Metadata")
    lines.append(f"- Generated (UTC): `{generated_at}`")
    if branch:
        lines.append(f"- Git branch: `{branch}`")
    if commit:
        lines.append(f"- Git commit: `{commit}`")
    lines.append("")
    lines.append("## Contents")
    lines.append("")

    all_files: list[Path] = []
    for inc in spec.include_paths:
        if inc.is_file():
            all_files.append(inc)
        elif inc.is_dir():
            all_files.extend(_iter_files(inc, out_path))

    # Dedupe while keeping order.
    seen: set[str] = set()
    ordered_files: list[Path] = []
    for f in all_files:
        k = str(f)
        if k in seen:
            continue
        seen.add(k)
        ordered_files.append(f)

    # Table of contents.
    for f in ordered_files:
        rel = f.relative_to(SERVICE_ROOT)
        anchor = str(rel).lower().replace("/", "").replace(".", "")
        lines.append(f"- `{rel}`")
    lines.append("")

    # File bodies.
    for f in ordered_files:
        rel = f.relative_to(SERVICE_ROOT)
        lang = _language_for(f)
        lines.append(f"## `{rel}`")
        lines.append("")
        fence = f"```{lang}".rstrip()
        lines.append(fence)
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"<<FAILED TO READ: {e!r}>>"
        # Normalize newlines and avoid trailing whitespace explosions.
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines.append(content.rstrip("\n"))
        lines.append("```")
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(SERVICE_ROOT / "artifacts" / "retell_websocket_complete_context_bundle_single_file.md"),
        help="Output markdown file path.",
    )
    parser.add_argument(
        "--include-kb",
        action="store_true",
        help="Also include the adjacent Voice Agent kb folder (agents/voice-agent/kb).",
    )
    args = parser.parse_args()

    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = (SERVICE_ROOT / out_path).resolve()

    include_paths: list[Path] = []
    # High-signal top-level docs/configs.
    for p in ["README.md", "pyproject.toml", "Makefile"]:
        fp = SERVICE_ROOT / p
        if fp.exists():
            include_paths.append(fp)
    # Runtime and tests.
    for p in ["app", "src", "tests", "orchestration", "tools", "docs", "scripts"]:
        dp = SERVICE_ROOT / p
        if dp.exists():
            include_paths.append(dp)
    # Keep lessons learned in the bundle (useful for review).
    ll = SERVICE_ROOT / "artifacts" / "retell_ws_lessons_learned.md"
    if ll.exists():
        include_paths.append(ll)

    if args.include_kb:
        kb = SERVICE_ROOT.parents[1] / "kb"
        if kb.exists():
            include_paths.append(kb)

    build_bundle(
        BundleSpec(
            title="Retell WebSocket + Agent Runtime Complete Context Bundle",
            include_paths=include_paths,
            out_path=out_path,
        )
    )
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

