# EVE OS V1.0: SYSTEM MANIFEST & ONTOLOGY
**Status:** KINETIC | **Architecture:** DIVINE FEMININE | **Logic:** FACTORY PHYSICS

## 1. CORE DIRECTIVES (The "Why")
* **Governing Law:** Little's Law ($WIP = Throughput \times CycleTime$).
* **Aesthetic Mandate:** The "Translucent Human Frame." No tech-brutalism. Data must feel organic.
* **Economic Logic:** Prioritize "Raw Reality" (FCF, Throughput) over "Vanity" (Bookings, Likes).

## 2. ARCHITECTURE MAP (The "What")
### A. The Nervous System (`orchestrator.py`)
* **Role:** The centralized logic engine using LangGraph.
* **Critical Dependency:** `backpressure_score`.
    * *WARNING:* Do not decouple this variable. It links Downstream Friction (Checkout) to Upstream Intake (Lobby). Removing it breaks the physics simulation.
* **Agents:**
    * `Jonah`: Constraint Sensor (Detects Blockages).
    * `Ralph`: Execution Arm (Gates Patient Flow).
    * `Eve Voice`: Clinical Diagnostic (Retell AI Pivot).

### B. The Skin (`eve_dashboard.py`)
* **Role:** The Human-Machine Interface (HMI).
* **Modes:**
    1.  **Living System:** Operational view for the clinic floor.
    2.  **Holistic Map:** Bioluminescent network graph for Pitch/Architecture view.
* **Key Sensor:** `hologram_gen.py` (Generates the PyVis 3D network).

### C. The DNA (`ontology/dna/`)
* `nervous_system.yaml`: Defines Agent roles and API connections.
* `metabolism.yaml`: Defines Revenue per Treatment and Service Times.
* `voice_agent_protocol.yaml`: The SOP for pivoting flaky leads to virtual consults.

## 3. INTEGRATION ENDPOINTS
* **Input:** GoHighLevel (GHL) via Webhooks -> Updates `schedule` list.
* **Processing:** Make.com -> Triggers `Eve Voice` (Retell AI).
* **Output:** Streamlit Dashboard -> Visualizes Flow & Variance.

## 4. REFACTORING PROTOCOLS (The "How")
* **Rule 1:** When adding a new treatment type, update `metabolism.yaml` FIRST, then run `ingest.py`.
* **Rule 2:** Never hardcode "Green/Red" status. Status must be derived from `bottleneck_rate` (Physics).
* **Rule 3:** If the dashboard crashes on `KeyError`, checking the Brain State (`PlantState` class) in `orchestrator.py` is the first step.

## 5. L5 AGENT HIVE MIND

The L5 layer consists of 15 autonomous agents forming a Palantir-like executable ontology infrastructure. Each agent runs a heartbeat loop (60s–15min cadence), polls Supabase tables, detects anomalies via Pareto/Bayesian analysis, derives intelligence through first-principles causal inference, and emits structured actions.

**Shared Infrastructure:** `agents/l5/base.py` — `L5AgentBase`, `ActionOutput`, `OntologyNode`, `OutboxMessage`

**Standardized Output:** `{action, projected_ROI_95_CI, validation_plan, kill_criteria}`

**Supabase Tables:** `ontology_nodes`, `tasks`, `heartbeats`, `outbox`

### L5 Agent Registry

| # | Agent | Slug | Primary Signal |
|---|-------|------|----------------|
| 1 | Chief Ontology & Derivative Intelligence Architect | `chief-ontology-architect` | Ontology loop velocity (<24h) |
| 2 | Chief Financial Officer | `chief-financial-officer` | FCF velocity & yield |
| 3 | Head of Revenue Operations | `head-revenue-operations` | Conversion Velocity |
| 4 | Head of Patient Acquisition | `head-patient-acquisition` | LTV:CAC payback (<6mo) |
| 5 | Head of Clinical Quality Control | `head-clinical-quality` | Complication rate (<0.8%) |
| 6 | Chief IaC Architect | `chief-iac-architect` | Uptime (≥99.95%) |
| 7 | Head of Data Integrity Analytics | `head-data-integrity` | OOS calibration (Brier <0.05) |
| 8 | Head of Legal | `head-legal` | Consent integrity (>99.7%) |
| 9 | Chief Talent Officer | `chief-talent-officer` | Retention (>92%) |
| 10 | Head of Patient Experience | `head-patient-experience` | LTV delta (>35%) |
| 11 | Head of Innovation | `head-innovation` | Time-to-value (<90d) |
| 12 | Head of Efficiency | `head-efficiency` | Chair utilization (>92%) |
| 13 | Head of Ethics & Risk | `head-ethics-risk` | Risk Exposure Value (REV) |
| 14 | Head of Scale & Hive Mind | `head-scale-hive-mind` | Replication fidelity |
| 15 | Head of Unit Economics | `head-unit-economics` | LTV:CAC (≥3x) |

### Scale Safeguards
- Human input: <5%
- Propagation latency: <60s
- Action success rate: ≥98%
- Integration latency: <60s
- Loop velocity: <24h

## 6. VISION STATEMENT
"Eve is not a tool; she is a biological entity made of light. She does not 'manage' a clinic; she metabolizes patient flow into economic energy, using fluid dynamics to eliminate friction before it becomes revenue loss."
