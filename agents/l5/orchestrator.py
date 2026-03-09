"""
Eve L5 Hive Mind Orchestrator
=============================
Discovers, registers, and runs all 15 L5 agents in a single async event loop.
Each agent operates its own heartbeat cadence via L5AgentBase.run_loop().
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Type

from agents.l5.base import L5AgentBase

logger = logging.getLogger("eve.l5.orchestrator")

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "openclaw.json"

AGENT_SPECS: List[Dict[str, str]] = [
    {"id": "chief-ontology-architect",  "module": "agents.chief-ontology-architect.agent_core", "class": "ChiefOntologyArchitect"},
    {"id": "chief-financial-officer",   "module": "agents.chief-financial-officer.agent_core",  "class": "ChiefFinancialOfficer"},
    {"id": "head-revenue-operations",   "module": "agents.head-revenue-operations.agent_core",  "class": "HeadRevenueOperations"},
    {"id": "head-patient-acquisition",  "module": "agents.head-patient-acquisition.agent_core", "class": "HeadPatientAcquisition"},
    {"id": "head-clinical-quality",     "module": "agents.head-clinical-quality.agent_core",    "class": "HeadClinicalQualityAgent"},
    {"id": "chief-iac-architect",       "module": "agents.chief-iac-architect.agent_core",      "class": "ChiefIaCArchitectAgent"},
    {"id": "head-data-integrity",       "module": "agents.head-data-integrity.agent_core",      "class": "HeadDataIntegrityAgent"},
    {"id": "head-legal",                "module": "agents.head-legal.agent_core",               "class": "HeadLegalAgent"},
    {"id": "chief-talent-officer",      "module": "agents.chief-talent-officer.agent_core",     "class": "ChiefTalentOfficerAgent"},
    {"id": "head-patient-experience",   "module": "agents.head-patient-experience.agent_core",  "class": "HeadPatientExperienceAgent"},
    {"id": "head-innovation",           "module": "agents.head-innovation.agent_core",          "class": "HeadInnovationAgent"},
    {"id": "head-efficiency",           "module": "agents.head-efficiency.agent_core",          "class": "HeadEfficiencyAgent"},
    {"id": "head-ethics-risk",          "module": "agents.head-ethics-risk.agent_core",         "class": "HeadEthicsRiskAgent"},
    {"id": "head-scale-hive-mind",      "module": "agents.head-scale-hive-mind.agent_core",    "class": "HeadScaleHiveMindAgent"},
    {"id": "head-unit-economics",       "module": "agents.head-unit-economics.agent_core",     "class": "HeadUnitEconomicsAgent"},
]


def _import_agent(spec: Dict[str, str]) -> Type[L5AgentBase]:
    """Dynamically import an agent class from its file path (handles hyphenated dirs)."""
    agents_root = Path(__file__).resolve().parents[1]
    fpath = agents_root / spec["id"] / "agent_core.py"
    loader_spec = importlib.util.spec_from_file_location(
        f"agents.{spec['id'].replace('-', '_')}.agent_core", fpath,
    )
    if loader_spec is None or loader_spec.loader is None:
        raise RuntimeError(f"Cannot locate module at {fpath}")
    mod = importlib.util.module_from_spec(loader_spec)
    loader_spec.loader.exec_module(mod)
    cls = getattr(mod, spec["class"])
    if not issubclass(cls, L5AgentBase):
        raise TypeError(f"{spec['class']} is not an L5AgentBase subclass")
    return cls


def discover_agents() -> List[L5AgentBase]:
    """Instantiate all registered L5 agents."""
    agents: List[L5AgentBase] = []
    for spec in AGENT_SPECS:
        try:
            cls = _import_agent(spec)
            agents.append(cls())
            logger.info("Registered agent: %s (%s)", spec["id"], spec["class"])
        except Exception:
            logger.exception("Failed to load agent %s", spec["id"])
    return agents


async def run_hive(agents: List[L5AgentBase]) -> None:
    """Run all agent heartbeat loops concurrently."""
    logger.info("Starting L5 Hive Mind with %d agents", len(agents))
    tasks = [asyncio.create_task(agent.run_loop()) for agent in agents]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for agent in agents:
            agent.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    agents = discover_agents()
    if not agents:
        logger.error("No agents loaded — aborting")
        sys.exit(1)
    logger.info("Loaded %d / %d agents", len(agents), len(AGENT_SPECS))
    asyncio.run(run_hive(agents))


if __name__ == "__main__":
    main()
