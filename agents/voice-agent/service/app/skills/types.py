from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Skill:
    id: str
    intent: str
    inputs: str
    outputs: str
    constraints: str
    commands: str
    tests: str
    body: str
    source_path: str


@dataclass
class ScoredSkill:
    skill: Skill
    score: float
