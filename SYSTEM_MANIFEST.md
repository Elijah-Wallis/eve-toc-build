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

## 5. VISION STATEMENT
"Eve is not a tool; she is a biological entity made of light. She does not 'manage' a clinic; she metabolizes patient flow into economic energy, using fluid dynamics to eliminate friction before it becomes revenue loss."
