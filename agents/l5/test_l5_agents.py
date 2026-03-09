"""
Comprehensive test suite for all 15 Eve L5 agents.
Tests: import, instantiation, anomaly detection, intelligence derivation,
action emission, structured output compliance, vanity/signal metrics,
and inter-agent messaging.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.l5.base import (
    ActionOutput,
    ConfidenceInterval,
    HeartbeatRecord,
    L5AgentBase,
    OntologyNode,
    OutboxMessage,
)

AGENTS_ROOT = Path(__file__).resolve().parents[1]

AGENT_SPECS: List[Tuple[str, str]] = [
    ("chief-ontology-architect", "ChiefOntologyArchitect"),
    ("chief-financial-officer", "ChiefFinancialOfficer"),
    ("head-revenue-operations", "HeadRevenueOperations"),
    ("head-patient-acquisition", "HeadPatientAcquisition"),
    ("head-clinical-quality", "HeadClinicalQualityAgent"),
    ("chief-iac-architect", "ChiefIaCArchitectAgent"),
    ("head-data-integrity", "HeadDataIntegrityAgent"),
    ("head-legal", "HeadLegalAgent"),
    ("chief-talent-officer", "ChiefTalentOfficerAgent"),
    ("head-patient-experience", "HeadPatientExperienceAgent"),
    ("head-innovation", "HeadInnovationAgent"),
    ("head-efficiency", "HeadEfficiencyAgent"),
    ("head-ethics-risk", "HeadEthicsRiskAgent"),
    ("head-scale-hive-mind", "HeadScaleHiveMindAgent"),
    ("head-unit-economics", "HeadUnitEconomicsAgent"),
]


def _load_agent(slug: str, cls_name: str) -> L5AgentBase:
    fpath = AGENTS_ROOT / slug / "agent_core.py"
    spec = importlib.util.spec_from_file_location(cls_name, fpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = getattr(mod, cls_name)
    return cls()


def test_all_agents_import() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        assert isinstance(agent, L5AgentBase), f"{cls_name} not L5AgentBase"
    print("PASS: test_all_agents_import")


def test_all_agents_have_required_classvars() -> None:
    required_attrs = ["role_id", "display_name", "cadence_seconds", "poll_tables", "vanity_metrics", "signal_metrics"]
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        for attr in required_attrs:
            assert hasattr(agent, attr), f"{cls_name} missing {attr}"
            val = getattr(agent, attr)
            assert val is not None, f"{cls_name}.{attr} is None"
        assert agent.role_id == slug, f"{cls_name}.role_id={agent.role_id} != {slug}"
        assert agent.cadence_seconds >= 10, f"{cls_name} cadence too low: {agent.cadence_seconds}"
        assert len(agent.poll_tables) > 0, f"{cls_name} has no poll_tables"
        assert len(agent.vanity_metrics) > 0, f"{cls_name} has no vanity_metrics"
        assert len(agent.signal_metrics) > 0, f"{cls_name} has no signal_metrics"
    print("PASS: test_all_agents_have_required_classvars")


def test_detect_anomalies_returns_list() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        result = agent.detect_anomalies({})
        assert isinstance(result, list), f"{cls_name}.detect_anomalies returned {type(result)}"
    print("PASS: test_detect_anomalies_returns_list")


def test_derive_intelligence_returns_action_outputs() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        anomalies = agent.detect_anomalies({})
        actions = agent.derive_intelligence(anomalies, {})
        assert isinstance(actions, list), f"{cls_name}.derive_intelligence returned {type(actions)}"
        for act in actions:
            assert isinstance(act, ActionOutput), f"{cls_name}: action is {type(act)}, expected ActionOutput"
    print("PASS: test_derive_intelligence_returns_action_outputs")


def test_action_output_format_compliance() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        anomalies = agent.detect_anomalies({})
        actions = agent.derive_intelligence(anomalies, {})
        for act in actions:
            assert act.action, f"{cls_name}: empty action field"
            assert isinstance(act.projected_roi, (int, float)), f"{cls_name}: projected_roi not numeric"
            assert isinstance(act.roi_ci, ConfidenceInterval), f"{cls_name}: roi_ci not ConfidenceInterval"
            assert act.roi_ci.confidence > 0, f"{cls_name}: roi_ci.confidence <= 0"
            assert act.validation_plan, f"{cls_name}: empty validation_plan"
            assert act.kill_criteria, f"{cls_name}: empty kill_criteria"
    print("PASS: test_action_output_format_compliance")


def test_tick_executes_without_error() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        agent.tick()
        assert agent._tick == 1, f"{cls_name}: tick count != 1 after single tick"
    print("PASS: test_tick_executes_without_error")


def test_clean_and_link_strips_vanity() -> None:
    for slug, cls_name in AGENT_SPECS:
        agent = _load_agent(slug, cls_name)
        if not agent.vanity_metrics:
            continue
        sample_key = agent.vanity_metrics[0]
        test_rows = [{"id": "1", sample_key: 999, "real_signal": 42}]
        cleaned = agent.clean_and_link(test_rows)
        assert len(cleaned) == 1
        assert sample_key not in cleaned[0], f"{cls_name}: vanity metric '{sample_key}' not stripped"
        assert cleaned[0].get("real_signal") == 42
        assert "_linked_agent" in cleaned[0]
    print("PASS: test_clean_and_link_strips_vanity")


def test_ontology_node_model() -> None:
    node = OntologyNode(
        entity="test_entity",
        attributes={"key": "value"},
        causal_relations=[{"source": "A", "target": "B", "weight": 0.9}],
        quantitative_thresholds={"min": 0.0, "max": 1.0},
        statistical_confidence=0.95,
        self_correction_triggers=["threshold_breach"],
        derivative_intelligence_hooks=["hook_1"],
        roi_projection_link="FCF",
    )
    d = node.model_dump()
    assert d["entity"] == "test_entity"
    assert d["statistical_confidence"] == 0.95
    assert len(d["causal_relations"]) == 1
    print("PASS: test_ontology_node_model")


def test_outbox_message_model() -> None:
    msg = OutboxMessage(
        source_agent="test-agent",
        target_agent="*",
        event_type="test_event",
        payload={"data": 123},
    )
    d = msg.model_dump()
    assert d["source_agent"] == "test-agent"
    assert d["target_agent"] == "*"
    assert d["consumed"] is False
    print("PASS: test_outbox_message_model")


def test_readme_files_exist() -> None:
    for slug, _ in AGENT_SPECS:
        readme = AGENTS_ROOT / slug / "README.md"
        assert readme.exists(), f"Missing README.md for {slug}"
        content = readme.read_text()
        assert len(content) > 500, f"README.md for {slug} is too short ({len(content)} chars)"
    print("PASS: test_readme_files_exist")


def main() -> None:
    tests = [
        test_all_agents_import,
        test_all_agents_have_required_classvars,
        test_detect_anomalies_returns_list,
        test_derive_intelligence_returns_action_outputs,
        test_action_output_format_compliance,
        test_tick_executes_without_error,
        test_clean_and_link_strips_vanity,
        test_ontology_node_model,
        test_outbox_message_model,
        test_readme_files_exist,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed:
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
