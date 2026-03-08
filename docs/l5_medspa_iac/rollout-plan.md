# EVE L5_Medspa_IaC Rollout Plan

## Phase 0 - Prototype hardening

Goal: prove the compiler and sandbox logic are stable.

- add contract tests for parser, triage, optimizer, and artifact generation
- generate one or two canonical Medspa bundles from real operator briefs
- compare generated SQL/workflow/voice outputs against current hand-authored assets
- wire generated manifests into acceptance and proactive review reporting

## Phase 1 - Assisted generation

Goal: keep humans in the loop while replacing manual copy/paste system assembly.

- operators author or paste a declarative spec
- generator emits draft artifacts into an output directory
- Elijah_EveBot reviews diffs, gaps, and governance risks
- humans selectively promote generated files into:
  - `ontology/`
  - `supabase/`
  - `workflows_n8n/`
  - `agents/voice-agent/service/orchestration/`

Success criteria:

- generation time under 60 seconds
- all required artifacts emitted
- no acceptance regressions on unchanged runtime paths

## Phase 2 - Controlled multi-client packaging

Goal: support multiple Medspa clients without prompt/workflow drift.

- store one spec per client under `platform/l5_medspa_iac/specs/`
- create per-client generated bundles under state or artifact directories
- keep shared base templates versioned, with client deltas encoded in specs only
- add tenant-aware SQL naming and routing isolation
- create version pinning for:
  - ontology schema version
  - voice prompt version
  - workflow schema version
  - governance policy version

Success criteria:

- at least 3 client bundles generated from the same compiler
- zero manual edits required inside generated outputs before first-pass review
- route-specific acceptance gates scoped by client id

## Phase 3 - Promotion to runtime-backed provisioning

Goal: let the platform layer write into live infra with review gates.

- add approval-required promotion commands
- create dry-run and apply modes
- connect generated SHACL and governance manifests to runtime validation
- integrate generated workflow identifiers with webhook lifecycle management
- emit launch profiles that honor manual/canary/full-ramp control already in repo

Success criteria:

- generated workflow artifacts preserve stable `webhookId`
- generated deployment packs pass secret-leak and workflow-contract guards
- generated launch profiles remain blocked until preflight passes

## Phase 4 - Fleet scaling

Goal: run the platform as a multi-client compiler rather than a single-client project helper.

- batch-generate client bundles from CRM or intake queue
- score bundle risk using entropy, leverage, compliance density, and artifact drift
- schedule Elijah_EveBot review loops by risk tier
- use Pareto analysis to identify shared templates worth upstreaming
- build a client capability matrix for:
  - service-line coverage
  - compliance burden
  - voice complexity
  - workflow complexity
  - simulator fidelity

## Scaling architecture

### Shared base layer

- global ontology primitives
- shared voice guardrails
- shared workflow contracts
- shared telemetry/governance policy

### Tenant delta layer

- service catalog
- personas
- compliance constraints
- branding
- KPI targets
- location-specific routing

### Generated deployment layer

- tenant SQL
- tenant workflow pack
- tenant voice config
- tenant digital-twin forecast bundle
- tenant IaC scaffolding

## Recommended promotion gates

1. spec validation gate
2. thermo triage gate
3. generator contract gate
4. workflow contract + secret hygiene gate
5. simulator consistency gate
6. immutable telemetry gate
7. Elijah_EveBot review gate
8. human approval gate for production promotion
