# 2026-02-08 V6 + CPOM + Canary Cutover Record

## Scope
- Upgraded B2B MedSpa prompt artifacts from V5 baseline to V6 behavioral model (canary path).
- Added CPOM-safe non-clinical boundary language across public legal pages, KB, and ops docs.
- Implemented dedicated `send_evidence_package` workflow (email + optional SMS + lead_events persistence).
- Enabled TX canary routing split for B2B agent selection.

## Runtime Decisions
- Control agent: existing B2B agent remains on V5 prompt.
- Canary agent: dedicated B2B agent configured with V6 prompt and B2B KB.
- Dispatch canary mode: `canary`, source regex `^tx-medspa-`, sample `50%`, V6 agent id bound.
- n8n Cloud env-expression policy remains constrained; remote workflows are patched to literal runtime config where required.

## Safety / Compliance
- Public legal URLs now include CPOM-safe language:
  - non-clinical support only
  - no diagnosis/treatment/prescribing
  - licensed provider authority retained
  - communications are not medical advice
- DNC workflow path updated for idempotent handling (repeated suppression requests remain safe).

## Evidence Package Workflow
- Webhook: `openclaw-retell-fn-send-evidence-package`
- Input guardrails:
  - valid `recipient_email`
  - `delivery_method`: `EMAIL_ONLY|EMAIL_AND_SMS`
  - `artifact_type`: `AUDIO_LINK|FAILURE_LOG_PDF`
  - required `evidence_url`
  - phone required for SMS delivery mode
- Persistence:
  - `retell_evidence_email`
  - `retell_evidence_sms`
  - `retell_evidence_package`

## Gating and Measurement
- Canary scorecard script: `scripts/ops/v6_canary_scorecard.py`
- Promotion criterion:
  - minimum human-answered sample met
  - V6 routing success >= V5 routing success * 1.20
  - zero compliance incidents

## Verification Snapshot
- Workflow contract checks: pass.
- AT-011: pass (secret scan + immutable telemetry checks).
- Telegram conflict probe (AT-006 surface): no sustained 409 in sampled window.

## Remaining Operational Inputs
- Configure a real email provider endpoint/key for evidence delivery (`EVIDENCE_EMAIL_PROVIDER_URL`, `EVIDENCE_EMAIL_API_KEY`, `EVIDENCE_EMAIL_FROM`) to shift package status from partial to delivered.
- Run live canary scorecard after sufficient sample volume before promotion.
