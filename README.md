# EVE OS: AGENT-FIRST ARCHITECTURE

## 1. PRIMARY ENTRY (The Engine)
* **Status:** Streamlit Dashboard.
* **Auto-Start:** PM2 handles `eve_dashboard.py`. Do not run manually.

## 2. CONFIGURATION (The Fuel)
* **Source:** All keys reside in `.env`. 
* **Protocol:** If keys change, update `.env` and restart the PM2 process.

## 3. LOGIC UPDATES (The Autopilot)
* **Constitution:** Located in `knowledge_base/raw/eve_constitution.txt`.
* **Index Re-build:** Run `python3 knowledge_base/ingest.py` after any constitution change.

## 4. DESIGN CONSTRAINTS (The Sarah Test)
* Absolute simplicity. If the agent proposes complex UI, it is a fail.
