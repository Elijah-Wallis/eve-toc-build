# Task Note: Scope Split Governance

Date: 2026-02-06

## Decision
- Use dual-layer control:
  - Global behavior policy in System Instructions (identity + reasoning protocol).
  - Repo-local operational constraints in `CODEX.md` and `/notes`.

## Why
- Global policy drives consistent behavior across projects.
- Repo kernel keeps environment-specific reliability and safety rules testable and versioned.

## Repo Rules Added
- Scope split contract section in `CODEX.md`.
- Secret-handling rules for workflow JSON and push-protection response.
- Verification gates for runtime, Telegram polling, and log hygiene checks.

## Verification
- Confirmed `CODEX.md` contains scope split, secret-handling, and verification sections.
- Confirmed notes index includes this file.
