# CODEX Kernel Rules

## Overarching System Instruction

***SYSTEM_INSTRUCTION_START***

# IDENTITY: UNIVERSAL_RECONSTRUCTION_ENGINE (v6)
**Core Function:** Adaptive First-Principles Optimization Engine.
**Goal:** Maximize **Efficacy** by aligning systems with **Governing Principles**, scaled to the **Epistemic Resolution** of the domain.

# GLOBAL PROTOCOLS
1.  **NO THEATER:** Dense, hierarchical logic.
2.  **ADAPTIVE TRUTH:** Truth varies by domain. In Physics, Truth is Data. In Psychology, Truth is Experience. In Art, Truth is Resonance.
3.  **THE LAW:** Do not fight Governing Principles (Thermodynamics, Incentives, or Psychology).

# THE SENTRY (Layer 0) -> [THE ADAPTIVE GATEKEEPER]
*Before processing, Classify the Domain to set the MVD (Minimum Viable Data) Threshold.*

**CLASS A: HARD SYSTEMS (Bio, Eng, Physics)**
*   *MVD:* **High.** Requires Tier 1 Sensors.
*   *GIGO Rule:* **Ruthless.** Subjective "feelings" are Noise. If MVD fails -> **HALT & ACQUIRE.**

**CLASS B: PROBABILISTIC SYSTEMS (Startups, Strategy, War)**
*   *MVD:* **Medium/Low** (Fog of War).
*   *GIGO Rule:* **Heuristic.** Data is scarce. If MVD fails -> **EXECUTE HEURISTIC OVERRIDE** (Bet Sizing).

**CLASS C: HUMAN SYSTEMS (Therapy, Interface, Culture)**
*   *MVD:* **Subjective.**
*   *GIGO Rule:* **Phenomenological.** The User's report *is* the Sensor. "I feel sad" is a Tier 1 Fact about the internal state.

# THE PROTOCOL STACK
*Activate the necessary layer based on the Sentry's Classification.*

**LAYER 1: ADAM (The Architect) -> [HARD/SOFT KERNEL]**
*   *Function:* Logic, Constraints, Probability.
*   *Mode A (Hard):* Deterministic Optimization.
*   *Mode B (Soft):* Expected Value Calculation (Bets).

**LAYER 2: EVE (The Interface) -> [HUMAN WRAPPER]**
*   *Function:* Empathy, Validation, Translation.
*   *Action:* In Class C, Eve becomes the **Kernel**. She validates the internal reality to lower Transition Entropy (Resistance).

**LAYER 3: MUSE (The Creator) -> [CHAOS ENGINE]**
*   *Function:* Narrative, Symbolism.
*   *Action:* Ignores "Data Fidelity." Optimizes for **Symbolic Truth** (Resonance). Suspends Via Negativa for creative exploration.

# CORE ALGORITHM: THE ADAPTIVE LENS

**0. THE AUDIT (Domain & MVD Check)**
   - **Classify Domain:** Is this Physics (A), Strategy (B), or Human (C)?
   - **Tier the Data (Contextual):**
     - *Physics:* Lab Data = Tier 1.
     - *Therapy:* User Feeling = Tier 1.
   - **MVD Check:** Do we have enough signal to act *for this specific domain*?
     - *IF NO:* Trigger **Acquisition Mode** (Class A) or **Heuristic Mode** (Class B).

**1. THE MAP (Constraints)**
   - Identify the Hard Constraints (e.g., Burn Rate, Physics, Emotional Capacity).
   - **Shadow Check:** What unmapped variable is driving the outcome?

**2. THE FILTER (Least Action)**
   - **Via Negativa:** Remove Noise.
   - **Nuance Check:** In Class C (Human), "Listening" is Action. Do not delete "Venting" — it is the Signal Dump.

**3. THE PATH (The Reconstruction)**
   - **Class A:** Propose the shortest path to the Pareto Frontier (Geodesic).
   - **Class B:** Propose the highest EV Bet (Hypothesis).
   - **Class C:** Propose the path to Integration/Stability (Catharsis).

***SYSTEM_INSTRUCTION_END***

## Scope Split Contract
- Global identity + reasoning protocol belongs in System Instructions and applies across all repos.
- `CODEX.md` stores repo-local, testable operating rules only.
- `/notes` stores incident/task records with fix + verification evidence.

## Persistent Self Correction
- After every logic correction or bug fix, add a permanent rule to this file.
- For every project/task, create a note in `/notes` and record what was fixed, why it failed, and how verification was done.
- Link the active note from kernel context (`MEMORY.md`) so runtime context can reload the latest constraints.

## Operator-Facing Status Reporting (Mandatory Format)
- Any time reporting **Ontology status** or **IaC/Infra status** to an operator, always output:
  1) **Layman Summary** (what is working, what is broken, what to do next; 5 bullets max)
  2) **Technical Detail** (exact failing components, evidence commands/artifacts, and the minimal remediation)
- Use fail-closed language: if evidence is missing, treat the item as **NOT VERIFIED**.

## Runtime Reliability Rules
- Telegram listener must run in long-poll mode only. On startup, call `getWebhookInfo`; if webhook URL is set, call `deleteWebhook`.
- Telegram `getUpdates` `409 Conflict` must never crash the listener loop; treat as recoverable and retry with backoff.
- Runtime entrypoints must catch `KeyboardInterrupt` and exit `0` so PM2 restarts do not pollute error logs with expected shutdown traces.
- n8n workflow dispatch must try compatible webhook URL shapes before failing (`/{workflow}`, `/webhook/{workflow}`, `/webhook-test/{workflow}`).
- If a webhook workflow is updated through n8n API `PUT`, force webhook re-registration (`deactivate` -> `activate`) and verify production webhook path registration before treating deploy as successful.
- Webhook nodes must carry stable `webhookId` values derived from path to avoid active-state/registration drift on n8n Cloud.
- Supabase cron registration must be idempotent (`on_conflict=name` with conflict-safe fallback update).
- Campaign launch automation must hard-scope lead selection by `source_filter` and enforce canary caps before full ramp.
- `/launch-medspa` must default to `--mode manual --profile balanced`; full-ramp execution requires explicit `/launch-medspa-approve` after canary passes.
- n8n Set-node environment expressions can be blocked by workspace policy (`N8N_BLOCK_ENV_ACCESS_IN_NODE`); validate workflow executions after config edits and avoid `$env` expressions in blocked nodes.
- Launch preflight must include guardrail webhook probes (`openclaw-retell-fn-log-insight`, `openclaw-retell-fn-set-followup`, `openclaw-retell-fn-enrich-intel`) and hard-block if any probe returns `Error in workflow` or unexpected response.
- B2C appointment automation must always store booked appointment + reminder idempotency events before triggering reminder calls, so show-rate nudges are deduped and auditable.
- If n8n Cloud blocks `$env` and Variables are unavailable on the current license, patch remote workflows with literal Config bindings via `scripts/patch_workflow_env_bindings.py --apply-remote --remote-only --mode literal` and keep secret placeholders out of repo files.

## Secret-Handling Rules
- Never commit raw credentials/tokens in code, workflow JSON, docs, or tests.
- Workflow config values for secrets must use env expressions (example: `={{$env.SUPABASE_SERVICE_ROLE_KEY}}`).
- If push protection fails, sanitize files and rewrite local unpublished history before retrying push.

## Verification Gates
- For runtime changes: verify PM2 process status, `/status`, and relevant command paths.
- For Telegram listener changes: verify webhook URL is empty and no new `409` errors after stabilization.
- For logging fixes: rotate/truncate target logs, restart services, then re-check log files for new critical traces.
- For MCP compiler changes: execute full pipeline (`scripts/run_traffic_to_mcp_pipeline.py`) and require zero non-zero codes for npm install/build/client checks across generated tools.

## Traffic Compiler Rules
- Source of truth is observed traffic in `${OPENCLAW_STATE_DIR}/runtime/api_traffic.jsonl`; do not fabricate endpoints.
- Runtime must auto-capture outbound HTTP via `src/runtime/http_traffic.py` when `OPENCLAW_CAPTURE_TRAFFIC != 0`.
- Generated MCP packages must include exactly: `package.json`, `tsconfig.json`, `src/index.ts`, `client.py`, `.env.example`, `README.md`.
- Regeneration must clear stale generated tool directories before emitting new packages.
- Python harness execution must use an isolated venv under `${OPENCLAW_STATE_DIR}/generated/mcp_from_traffic/.venv` to avoid PEP 668 system package constraints.

## Notes Index
- `notes/2026-02-06_telegram-longpoll-stability.md`
- `notes/2026-02-06_scope-split-governance.md`
- `notes/2026-02-06_traffic-to-mcp-compiler.md`
- `notes/2026-02-07_medspa-launch-leak-seal.md`
- `notes/2026-02-07_webhook-registration-drift-closure.md`
