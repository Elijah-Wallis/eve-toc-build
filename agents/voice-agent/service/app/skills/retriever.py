from __future__ import annotations

from .types import Skill, ScoredSkill


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in text.replace("_", " ").split() if w}


def retrieve_skills(
    query: str,
    skills: list[Skill],
    *,
    max_items: int = 3,
) -> list[ScoredSkill]:
    if not skills or max_items <= 0:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    scored: list[ScoredSkill] = []
    for skill in skills:
        skill_tokens = _tokenize(f"{skill.intent} {skill.body}")
        overlap = len(query_tokens & skill_tokens)
        if overlap > 0:
            scored.append(ScoredSkill(skill=skill, score=overlap))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:max_items]


def render_skills_for_prompt(hits: list[ScoredSkill]) -> str:
    if not hits:
        return ""
    parts: list[str] = []
    for i, hit in enumerate(hits, 1):
        parts.append(
            f"Skill {i}: {hit.skill.id}\n"
            f"Intent: {hit.skill.intent}\n"
            f"{hit.skill.body}"
        )
    return "\n\n".join(parts)
