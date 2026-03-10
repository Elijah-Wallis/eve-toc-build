---
id: chief_ontology_derivative_intelligence_architect
intent: Run the L5 ontology architect heartbeat loop and emit a strict action envelope for ontology drift, propagation latency, and causal integrity gaps.
inputs: Supabase runtime tables, ontology node payloads, task backlog, outbox backlog, heartbeat freshness, and optional revalidation payload.
outputs: Strict JSON object with action, projected_ROI_95_CI, validation_plan, and kill_criteria.
constraints: Enforce executable hypergraph nodes only; reject vanity metrics; keep heartbeat cadence between 60s and 15m; preserve under-60s propagation and under-24h ontology loop velocity.
commands: python3 agents/chief-ontology-derivative-intelligence-architect/agent_core.py
tests: python3 -m pytest -q tests/agents/test_chief_ontology_derivative_intelligence_architect.py
---
Use this skill when the system needs an ontology-native operator that polls Supabase, normalizes causal node payloads, identifies Pareto-breaking inefficiencies, runs a least-action counterfactual, and publishes a hive-safe action envelope through the outbox.

The skill is designed for autonomous loops, staged revalidation, and cross-agent consumption. It always operates on executable node payloads and refuses to promote narrative-only output.
