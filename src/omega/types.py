from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RiskClass(str, Enum):
    C = "C"  # Civilian
    B = "B"  # Industrial
    A = "A"  # Sovereign


class OmegaSkillInput(BaseModel):
    """Input contract for Omega skills.

    Lazarus Interface Parity requires both the ID (API path) and a
    descriptive name (Vision fallback).
    """

    entity_id: str = Field(..., description="Primary identifier for API path")
    entity_name: str = Field(..., description="Human-readable name for Vision fallback")
    force_drift: bool = Field(False, description="Simulate API drift to test Lazarus")
    session_profile: str = Field("default", description="SessionVault profile")
    context: Dict[str, Any] = Field(default_factory=dict, description="Extra context for Vision")


class OmegaSkillSpec(BaseModel):
    """Skill specification used by the factory."""

    name: str
    risk_class: RiskClass
    openapi_path: str
    test_event_path: str
    output_dir: str
    description: Optional[str] = None
