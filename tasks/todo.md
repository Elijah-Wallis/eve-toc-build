# OpenClaw Swarm Orchestration — Plan (Draft)

## Objectives
- Deliver a full strategy pack for the OpenClaw swarm architecture (stack nuance, inversion analysis, event-driven map, multi-tree reconstruction).
- Stabilize Codex execution flow to reduce approval prompts without expanding risk.
- Prepare a safe cleanup plan (storage + shell customizations) with user-approved deletions only.
- Set model max output to the provider’s highest supported limit.

## Decisions Needed (from user)
- Preferred model/provider for max output (stay on Claude Sonnet or switch to higher-output model).
- Cleanup scope (safe caches/logs only vs. deeper clean that removes tooling/customizations).
- Scope for “best possible” OpenClaw (local-only vs. hybrid with cloud services).

## Decisions Received (2026-02-04)
- Max output target: `google/gemini-3-flash-preview` on OpenRouter (set to provider max).
- Cleanup scope: safe-only.
- Orchestration scope: hybrid (local + cloud), with migration path to Mac Mini M2.

## Plan
- [ ] Verify Codex config values (`approval_policy`, `sandbox_mode`, active profile) and identify why prompts persist.
- [ ] Draft cleanup syllabus + minimal safe deletion plan with explicit sizes and examples.
- [ ] Produce swarm architecture package (stack nuance, inversion analysis, event-driven map, directory/worktree design).
- [ ] Propose concrete implementation steps + validation checks for OpenClaw swarm build-out.
- [ ] Apply agreed config changes (only after explicit confirmation).

## Proof / Verification (after implementation)
- Approval prompts reduced for non-escalated commands.
- OpenClaw health/cron/agent checks pass with max output limits set.
- Disk space reclaimed from approved cleanup targets.
