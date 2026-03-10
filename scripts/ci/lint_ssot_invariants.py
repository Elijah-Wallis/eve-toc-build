from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ROOT / "src" / "runtime",
    ROOT / "mcp_servers",
    ROOT / "scripts" / "ops",
    ROOT / "scripts" / "dashboard",
    ROOT / "scripts" / "import_medspa_csv.py",
    ROOT / "openclaw_cli.py",
    ROOT / "telegram_router.py",
]
ALLOWLIST = {
    ROOT / "ontology" / "client.py",
    ROOT / "src" / "runtime" / "secrets_provider.py",
}
ALLOW_SUBTREES = {
    ROOT / "src" / "runtime" / "proactive_review",
}
BANNED_PATTERNS = {
    "/rest/v1/": "raw Supabase REST path detected outside ontology/client.py",
    "from supabase": "direct supabase import detected outside ontology/client.py",
    "supabase.": "direct supabase client usage detected outside ontology/client.py",
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_file():
            files.append(target)
            continue
        for path in target.rglob("*.py"):
            files.append(path)
    return sorted(set(files))


def _allowed(path: Path) -> bool:
    if path in ALLOWLIST:
        return True
    return any(parent == subtree or subtree in path.parents for subtree in ALLOW_SUBTREES for parent in [path.parent])


def main() -> int:
    findings: list[str] = []
    for path in _iter_python_files():
        if _allowed(path):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for needle, reason in BANNED_PATTERNS.items():
                if needle in line:
                    findings.append(f"{path.relative_to(ROOT)}:{lineno}: {reason}")
    if findings:
        sys.stderr.write("SSOT invariant violations found:\n")
        sys.stderr.write("\n".join(findings) + "\n")
        return 1
    print("ssot-invariants-pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
