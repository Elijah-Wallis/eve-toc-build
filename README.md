# EVE system — eve-toc-build (monorepo)

Single repository for the EVE/OpenClaw ecosystem: runtime, legal/policies, demos, and review tooling. Former standalone repos are consolidated here with history preserved (via `git subtree`).

## Table of contents

| Path | Description |
|------|--------------|
| **/** (root) | Core EVE/OpenClaw runtime — orchestrator, Telegram ingress, Supabase, n8n workflows |
| [policies/](policies/) | Legal policies, Retell WS Brain, terms/privacy, orchestration (from **eve-legal-policies**) |
| [demos/digital-twin/](demos/digital-twin/) | Digital Twin demonstration — KPI diagnostic, ontology demo (from **digital-twin-demonstration**) |
| [reviews/toc-build/](reviews/toc-build/) | Retell WS Brain review/eval tooling, public handoff (from **eve-toc-build-review**) |
| [docs/](docs/) | Cross-cutting documentation |

**Archived repos:** The standalone GitHub repos `eve-legal-policies`, `digital-twin-demonstration`, and `eve-toc-build-review` are now archived; their contents live in this monorepo under the paths above.

---

## Core (runtime)

This repo hosts the EVE/OpenClaw runtime loop, Telegram command ingress, Supabase-backed task durability, and n8n workflow dispatch.

## Runtime ownership
- Gateway owner: `launchd` (`ai.openclaw.eve`).
- Runtime/Telegram owners: `pm2` (`openclaw-runtime`, `openclaw-telegram`, optional `openclaw-worker`).
- Telegram ingress owner: custom listener (`src/runtime/telegram_listener.py`).

## Health dashboard (10 second glance)
- Run:
  - Fastest (from anywhere): `eve` (or `eve-dashboard`)
  - If the repo moves: `EVE_TOC_BUILD_REPO=/path/to/eve-toc-build eve`
  - One command (from repo root): `bash ${REPO_ROOT}/scripts/dashboard/run_dashboard.sh`
  - Or from repo root: `python3 scripts/dashboard/health_server.py --open --quiet`
- Open:
  - `http://127.0.0.1:7331`

## Telegram EveBot commands
- `/evebot_run`
- `/evebot_status`
- `/evebot_deep`
- `/evebot_heartbeat_now`
- `/evebot_digest`
- Weekly deep prerequisite:
  - `bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh --with-weekly-deep`

## Key validation commands
1. Contract suite:
   - `bash scripts/acceptance/run_contract_suite.sh`
2. Full acceptance harness:
   - `python3 scripts/acceptance/run_acceptance.py --ids AT-001,AT-002,AT-003,AT-007,AT-009`
3. Patched production gates:
   - `python3 scripts/acceptance/run_acceptance.py --ids AT-013A,AT-018,AT-021A,AT-024A,AT-034A,AT-035A`
4. Hardening verification gates:
   - `python3 scripts/acceptance/run_acceptance.py --ids AT-013B,AT-018B,AT-021B,AT-024B,AT-034B,AT-035B`
5. Ops Baseline deterministic gates:
   - `python3 scripts/acceptance/run_acceptance.py --ids AT-PRO-004,AT-REV-001,AT-ING-001,AT-LEDGER-001,AT-SEC-002`
6. Release baseline snapshot script:
   - `bash scripts/release/create_release_baseline.sh`
5. Telegram conflict check:
   - `python3 scripts/ops/check_telegram_conflicts.py --window-minutes 30`
6. Runtime SLO check:
   - `python3 scripts/ops/runtime_slo_check.py --window-minutes 60`
7. Immutable telemetry chain verification:
   - `python3 scripts/ops/emit_telemetry_probe.py`
   - `python3 scripts/ops/verify_immutable_telemetry.py --require-signed --allow-legacy-interleaving`
   - `bash scripts/ops/run_data_integrity_protocol.sh tx-medspa-2026-02-07`
8. Config validation:
   - `python3 scripts/validate_runtime_config.py`
9. Transcript sync (Retell -> Supabase transcript tables):
   - `python3 scripts/ops/sync_call_transcripts.py --campaign-tag tx-medspa-2026-02-07 --print-table`
10. V6 canary scorecard:
   - `python3 scripts/ops/v6_canary_scorecard.py --hours 24 --source-regex '^tx-medspa-' --min-human-answered 40`

## Retell B2B Prompt Rollout
- Enable V6 on B2B agent:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v6`
- Roll back to V5:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v5`
- Configure B2B with websocket + bidirectional settings:
  - `python3 scripts/configure_retell_b2b_agent.py --agent-id \"$RETELL_AGENT_B2B_ID\" --prompt-version v6 --websocket-url \"$RETELL_LLM_WEBSOCKET_URL\" --bidirectional-mode on`
- Configure B2C tools/KB + websocket settings:
  - `python3 scripts/configure_retell_b2c_agent.py --agent-id \"$RETELL_AGENT_B2C_ID\" --websocket-url \"$RETELL_LLM_WEBSOCKET_URL\" --bidirectional-mode on`

## Security and workflow guards
- Secret exposure scan:
  - `python3 scripts/ops/secret_exposure_scan.py`
- Workflow contract check:
  - `python3 scripts/ci/check_workflow_contracts.py`
- Workflow secret policy check:
  - `python3 scripts/guard_workflow_secret_leaks.py --check-remote`
- Repo-wide absolute path boundary scan (tracked files):
  - `bash scripts/scan_absolute_paths.sh`

## Elijah_EveBot proactive loop (patch-only)
- Run once (offline, fast):
  - `python3 -m src.runtime.proactive_review.daily_review --mode offline --profile fast --once`
- Run once (offline, deep):
  - `python3 -m src.runtime.proactive_review.daily_review --mode offline --profile deep --once`
- Heartbeat-only sweep:
  - `python3 -m src.runtime.proactive_review.daily_review --mode offline --heartbeat-only`
- Record feedback:
  - `python3 -m src.runtime.proactive_review.daily_review feedback --proposal-id proposal-001 --decision accepted --notes "ship this"`
- Install launchd schedule:
  - `bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh`
  - `bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh --with-weekly-deep`
  - `bash ${REPO_ROOT}/scripts/install_elijah_evebot_launchd.sh --with-heartbeat-hourly`
- Uninstall launchd schedule:
  - `bash ${REPO_ROOT}/scripts/uninstall_elijah_evebot_launchd.sh`
- Verify launchd jobs:
  - `bash ${REPO_ROOT}/scripts/verify_elijah_evebot_launchd.sh`
- Force-run daily launchd job:
  - `launchctl kickstart -k "gui/$(id -u)/com.openclaw.elijah_evebot_daily"`
- Prove scheduler execution and artifact freshness:
  - `bash ${REPO_ROOT}/scripts/prove_elijah_evebot_launchd_run.sh`
- Open morning report + latest proposals:
  - `bash ${REPO_ROOT}/scripts/open_morning_report.sh`
- Apply one proposal manually:
  - `code_patch` proposals include `change.patch`:
    - `bash ${REPO_ROOT}/scripts/apply_proposal.sh <proposal_dir>`
  - `validate_only` proposals do not include a patch; they include `meta.json.execution_commands`:
    - `bash ${REPO_ROOT}/scripts/apply_proposal.sh <proposal_dir>` (prints runbook commands, exits 0)
    - `bash ${REPO_ROOT}/scripts/apply_proposal.sh --run <proposal_dir>` (executes commands)
- Proactive acceptance gates:
  - `python3 scripts/acceptance/run_acceptance.py --ids AT-PRO-001,AT-PRO-002,AT-PRO-003,AT-PRO-004`
- Acceptance trends location:
  - `${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}/acceptance/trends/last_7.json`

## Notes
- n8n secret policy: workflows must not contain literal tokens. Use env/vars bindings (e.g. `={{$env.KEY}}` / `={{$vars.KEY}}`) and keep `OPENCLAW_N8N_BINDING_MODE` set to `env` (or `vars`).
- Runtime stability envelope is controlled with:
  - `OPENCLAW_RUNTIME_STABILITY_ENVELOPE`
  - `OPENCLAW_STEP_MAX_RETRIES`
  - `OPENCLAW_STEP_BACKOFF_MS`
  - `OPENCLAW_FATAL_ERROR_BUDGET_PER_HOUR`
- Immutable telemetry ledger is controlled with:
  - `OPENCLAW_IMMUTABLE_LOGS`
  - `OPENCLAW_IMMUTABLE_STRICT`
  - `OPENCLAW_IMMUTABLE_FSYNC_EVERY`
- Transcript tables are defined in:
  - `supabase/upgrade_transcripts.sql` (existing DBs)
  - `supabase/schema.sql` (fresh bootstrap)
- Supabase-first outbox + SHACL artifact upgrade:
  - `supabase/upgrade_outbox_and_shacl.sql`
- Absolute-home-path lint:
  - `python3 scripts/ci/lint_no_absolute_paths.py`
- Docker-backed verification prerequisites:
  - Docker daemon running for `AT-018B`, `AT-034B`, `AT-035B`

## World-Class Ops Context (Path + Dependency Truth)
- Canonical path runbook:
  - `Business_Code/world_class_ops_path_context.md`
- Deterministic preflight check:
  - `bash scripts/ops/worldclass_preflight.sh`

This preflight encodes the common failure points and checks:
- Env source and required key presence (`${OPENCLAW_STATE_DIR%/*}/.openclaw_env`)
- Cloudflare token presence (`${OPENCLAW_STATE_DIR}/cloudflare.env`)
- Supabase transcript schema availability (`call_transcripts` with `recording_url`)
- Websocket hostname DNS resolvability
- Local gateway health (`127.0.0.1:19001`)
