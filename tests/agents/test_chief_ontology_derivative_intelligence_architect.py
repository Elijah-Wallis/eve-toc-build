from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.runtime.registry_defaults import build_registry


def _load_agent_module():
    target = (
        Path(__file__).resolve().parents[2]
        / "agents"
        / "chief-ontology-derivative-intelligence-architect"
        / "agent_core.py"
    )
    spec = importlib.util.spec_from_file_location("chief_ontology_agent_core", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeSession:
    def __init__(self, responders: Dict[Tuple[str, str], List[FakeResponse]]) -> None:
        self.responders = responders
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        table = url.split("/rest/v1/", 1)[1]
        key = (method.lower(), table)
        self.calls.append((method.lower(), table, kwargs))
        queue = self.responders.get(key)
        if queue:
            return queue.pop(0)
        return FakeResponse(201 if method.lower() == "post" else 200, [])


class FakeTelemetry:
    def __init__(self) -> None:
        self.events: List[Tuple[str, Dict[str, Any]]] = []

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append((event, payload))


def test_run_once_emits_strict_output_and_schedules_revalidation(monkeypatch, tmp_path) -> None:
    module = _load_agent_module()
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    responders = {
        ("get", "ontology_nodes"): [FakeResponse(404, {"message": "missing"})],
        (
            "get",
            "tasks",
        ): [
            FakeResponse(
                200,
                [
                    {"id": f"task-{idx}", "type": "graph.run", "status": "queued", "payload_json": {}, "scheduled_for": "2026-03-09T00:00:00+00:00", "created_at": "2026-03-09T00:00:00+00:00"}
                    for idx in range(10)
                ],
            )
        ],
        ("get", "heartbeats"): [FakeResponse(404, {"message": "missing"})],
        ("get", "canonical_outbox"): [FakeResponse(200, [])],
        ("post", "ontology_nodes"): [FakeResponse(404, {"message": "missing"}) for _ in range(4)],
        ("post", "canonical_outbox"): [FakeResponse(201, [])],
        ("post", "heartbeats"): [FakeResponse(404, {"message": "missing"})],
        ("post", "tasks"): [FakeResponse(201, [])],
    }
    agent = module.ChiefOntologyDerivativeIntelligenceArchitectAgent(
        supabase_url="https://example.supabase.co",
        supabase_key="service-key",
        session=FakeSession(responders),
        telemetry=FakeTelemetry(),
    )

    result = agent.run_once({})

    assert set(result) == {"action", "projected_ROI_95_CI", "validation_plan", "kill_criteria"}
    assert result["action"]["type"] == "ontology.rebalance_loop_velocity"
    assert result["action"]["priority"] == "p0"
    assert result["projected_ROI_95_CI"]["expected"] > 0
    heartbeat_file = tmp_path / "runtime" / "heartbeats" / "chief-ontology-derivative-intelligence-architect.json"
    assert heartbeat_file.exists()
    task_posts = [call for call in agent.session.calls if call[0] == "post" and call[1] == "tasks"]
    assert len(task_posts) == 1


def test_low_confidence_rare_edges_trigger_clinical_quality_gate(monkeypatch, tmp_path) -> None:
    module = _load_agent_module()
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    responders = {
        (
            "get",
            "ontology_nodes",
        ): [
            FakeResponse(
                200,
                [
                    {
                        "id": "node-1",
                        "entity": "injectable_protocol_path",
                        "attributes": {"rare_edge": True, "causal_prediction_error": 0.07},
                        "causal_relations": [{"source": "protocol", "target": "action_success_rate", "weight": 0.8, "confidence": 0.95}],
                        "quantitative_thresholds": {"statistical_confidence_min": 0.98},
                        "statistical_confidence": 0.7,
                        "self_correction_triggers": ["statistical_confidence < 0.98"],
                        "derivative_intelligence_hooks": {"hook": "clinical_review"},
                        "updated_at": "2026-03-09T00:00:00+00:00",
                        "confidence": 0.7,
                    }
                ],
            )
        ],
        ("get", "tasks"): [FakeResponse(200, [])],
        ("get", "heartbeats"): [FakeResponse(200, [])],
        ("get", "canonical_outbox"): [FakeResponse(200, [])],
        ("post", "ontology_nodes"): [FakeResponse(201, []) for _ in range(4)],
        ("post", "canonical_outbox"): [FakeResponse(201, [])],
        ("post", "heartbeats"): [FakeResponse(201, [])],
        ("post", "tasks"): [FakeResponse(201, [])],
    }
    agent = module.ChiefOntologyDerivativeIntelligenceArchitectAgent(
        supabase_url="https://example.supabase.co",
        supabase_key="service-key",
        session=FakeSession(responders),
        telemetry=FakeTelemetry(),
    )

    result = agent.run_once({})

    assert result["action"]["type"] == "ontology.request_clinical_quality_gate"
    assert result["action"]["payload"]["mode"] == "clinical_quality_gate"


def test_runtime_registry_contains_ontology_handler() -> None:
    registry = build_registry()
    assert registry.get("ontology.chief.run") is not None
