from __future__ import annotations

import re
from pathlib import Path
from typing import Union

from .types import Skill

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_REQUIRED_FIELDS = {"id", "intent", "inputs", "outputs", "constraints", "commands", "tests"}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    raw = m.group(1)
    body = text[m.end():]
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields, body


def load_skill_file(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    parsed = _parse_frontmatter(text)
    if parsed is None:
        raise ValueError(f"invalid skill file (no frontmatter): {path}")
    fields, body = parsed
    missing = _REQUIRED_FIELDS - set(fields)
    if missing:
        raise ValueError(f"missing required fields {missing} in {path}")
    return Skill(
        id=fields["id"],
        intent=fields["intent"],
        inputs=fields["inputs"],
        outputs=fields["outputs"],
        constraints=fields["constraints"],
        commands=fields["commands"],
        tests=fields["tests"],
        body=body.strip(),
        source_path=str(path),
    )


def load_skills(directory: Union[str, Path]) -> list[Skill]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return []
    skills: list[Skill] = []
    for p in sorted(root.glob("*.md")):
        try:
            skills.append(load_skill_file(p))
        except Exception:
            continue
    return skills


def validate_skills(skills: list[Skill]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for s in skills:
        if not s.id:
            errors.append(f"skill at {s.source_path} has empty id")
        elif s.id in seen_ids:
            errors.append(f"duplicate skill id: {s.id}")
        else:
            seen_ids.add(s.id)
        if not s.intent:
            errors.append(f"skill {s.id} has empty intent")
        if not s.body:
            errors.append(f"skill {s.id} has empty body")
    return errors
