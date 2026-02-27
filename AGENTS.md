# EVE / OpenClaw Runtime

## Cursor Cloud specific instructions

### Project overview

This is a multi-component Python/Node.js codebase for AI-powered lead generation and outbound calling (MedSpa/clinic focus). Two main workspaces:

- **Root** (`/workspace`): Runtime engine, Telegram listener, MCP servers, acceptance harness
- **Voice agent** (`agents/voice-agent/service/`): FastAPI WebSocket brain for Retell AI calls (has its own `pyproject.toml`)

### Running tests

**Root-level acceptance gates** (mirrors CI in `.github/workflows/acceptance.yml`):

```
python3 scripts/acceptance/run_acceptance.py --ids AT-REV-001,AT-ING-001,AT-LEDGER-001,AT-SEC-002
```

The acceptance harness auto-bootstraps a venv with dependencies if needed. Many gates are skipped in this repo snapshot because the corresponding test/script files are absent (e.g., `tests/contracts/`, `tests/integration/`). This is by design — the harness gracefully skips missing files.

**Root-level pytest** (tests that exist and pass):

```
python3 -m pytest tests/test_revenueops_gate.py tests/test_postcall_ingestion_completeness.py tests/test_event_chain_gate.py tests/test_secret_hygiene_strict.py tests/test_acceptance_trends.py -q
```

Three test files (`test_telegram_contracts.py`, `test_proactive_execution_profiles.py`, `test_proactive_review_proposal_quality.py`) fail to import due to missing source modules (`src.runtime.config_adapter`, `src.runtime.proactive_review.memory`). Exclude them when running `pytest tests/` directly.

**Voice agent tests** (`agents/voice-agent/service/`):

```
cd agents/voice-agent/service && python3 -m pytest -q
```

Run from `agents/voice-agent/service/`. Nearly all tests pass (158/159). The single failure (`test_dashboard_routes_smoke`) is due to a missing `dashboard/` static files directory. The voice agent Makefile target `make test` also works.

### Lint and security checks

- Secret scan: `bash scripts/security/scan_secrets_strict.sh`
- Repo bloat guard (CI mode): `CI=1 bash scripts/check_repo_bloat.sh`
- `scripts/ci/lint_no_absolute_paths.py` and `scripts/scan_absolute_paths.sh` are referenced by acceptance gates but absent from this repo snapshot

### Known repo snapshot gaps

- Several `tests/contracts/` and `tests/integration/` directories/files referenced by the acceptance harness don't exist; the harness skips them gracefully
- `src/runtime/proactive_review/memory.py` and `src/runtime/config_adapter.py` are missing, causing 3 root-level test files to fail at import
- The `dashboard/` static files directory is absent from `agents/voice-agent/service/`, so `/dashboard/` returns 404 (1 test affected: `test_dashboard_routes_smoke`)

### Services and external dependencies

The full runtime requires Supabase, n8n, Retell AI, Telegram bot token, and an LLM provider key. See `.env.example` for all required environment variables. None of these are needed for running the test suites described above.

### Python version

CI uses Python 3.12 (see `.github/workflows/acceptance.yml`). The VM has Python 3.12.3 pre-installed.
