# Protocol Omega v4.0

This subsystem implements the Pragmatic Skill Generation Workflow.

## Files

- `src/omega/*` — core runtime (triage, session vault, validator, lazarus, triad, ledger)
- `.agents/skills/omega_factory.py` — CLI entrypoint for skill generation
- `omega_factory.py` — root loader for compatibility

## SessionVault

Store runtime auth in a dynamic file (Playwright storage_state.json or bearer token):

```json
{
  "version": 1,
  "profiles": {
    "default": {
      "storage_state_path": "/path/to/storage_state.json",
      "bearer_token": "..."
    }
  }
}
```

Default path used by generated skills:

```
~/.openclaw-eve/session_vault.json
```

## Validator input (test_event.json)

Example:

```json
{
  "method": "GET",
  "url_template": "https://api.example.com/users/{entity_id}",
  "headers": {"Accept": "application/json"},
  "params": {"include": "profile"},
  "json_body": null,
  "session_profile": "default",
  "expected_response_shape": {
    "id": "int",
    "name": "str",
    "profile": {
      "email": "str"
    }
  }
}
```

## Generate a skill

```bash
python omega_factory.py \
  --name invoice_pull \
  --risk B \
  --openapi /path/to/openapi.yaml \
  --test-event /path/to/test_event.json \
  --output-dir /Users/elijah/Developer/eve-toc-build/.agents/skills/generated
```

## Lazarus test (force_drift)

Send payload with `force_drift: true` to simulate API failure and trigger Vision fallback.

## Daily Audit (Class A)

```bash
python omega_audit.py --ledger ~/.openclaw-eve/omega/ledger.jsonl
```

## Risk Class A

Class A requires Triad consensus. Configure a real LLM client in the generated skill
before use; the default stub raises an error.
