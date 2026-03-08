# EVE L5_Medspa_IaC Blindspot Analysis

## 1. Spec ambiguity blindspots

Risk:

- natural-language briefs may omit licensing, timezone, or service-level constraints

Failure mode:

- generator emits valid artifacts that are strategically wrong

Mitigation:

- Thermo_Triage blocks hard-system generation on missing minimum viable data
- specs should be promoted from natural language -> normalized JSON before production use

## 2. Governance theater

Risk:

- “governance” exists only as documentation, not enforced artifact contracts

Failure mode:

- generated platforms look complete but do not emit immutable telemetry or review hooks

Mitigation:

- keep telemetry + Elijah_EveBot requirements inside generated governance manifests
- require acceptance commands in every generated bundle

## 3. Prompt drift across voice surfaces

Risk:

- hand-edited voice prompts diverge from generated configs

Failure mode:

- V13.3 Emotional Resilience Inverter and red-team guards become inconsistent by client

Mitigation:

- treat generated voice YAML as canonical
- gate downstream manual edits behind diff review

## 4. Workflow drift and webhook fragility

Risk:

- generated n8n workflows mutate webhook structure or lose stable identifiers

Failure mode:

- deployment succeeds on paper but webhooks silently drift out of registration

Mitigation:

- preserve stable webhook identities in generated workflow metadata
- run existing webhook lifecycle/contract checks before promotion

## 5. SHACL mismatch blindspots

Risk:

- ontology extension and SQL projection encode different field assumptions

Failure mode:

- runtime ingest passes one layer and fails another

Mitigation:

- generate SHACL and SQL from the same normalized spec object
- carry machine-actionable failure codes into quarantine/report paths

## 6. Optimization overfitting

Risk:

- solver rewards interventions that look good mathematically but ignore real operator pain

Failure mode:

- Pareto frontier is numerically elegant but operationally unusable

Mitigation:

- keep least-action and friction penalties explicit
- require operator review of selected interventions before live promotion

## 7. Multi-client contamination

Risk:

- artifacts or prompts leak assumptions from one Medspa into another

Failure mode:

- compliance, branding, or routing errors cross client boundaries

Mitigation:

- isolate tenant deltas in per-client specs
- avoid manual copy-forward of generated artifacts
- include client ids in all generated bundles and deployment identifiers

## 8. Complexity creep in the compiler itself

Risk:

- platform generator becomes another sprawling manual system

Failure mode:

- teams maintain compiler templates and generated outputs separately

Mitigation:

- keep one declarative source-of-truth
- enforce generated-file boundaries
- measure complexity reduction as a first-class optimization metric

## 9. Simulator confidence inflation

Risk:

- forecast outputs may be interpreted as guaranteed outcomes

Failure mode:

- rollout decisions over-trust prototype math

Mitigation:

- label simulator output as scenario planning
- require empirical post-launch telemetry to update priors

## 10. Human/operator adoption friction

Risk:

- generator produces too many artifacts for operators to trust or review quickly

Failure mode:

- platform layer is ignored, and manual assembly returns

Mitigation:

- keep least-action summary in CLI output
- emit concise manifest + sandbox snapshot first
- expand to full bundle only when the triage gate passes
