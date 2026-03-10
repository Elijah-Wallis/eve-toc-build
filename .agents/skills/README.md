# .agents/skills

Utility scripts that can be called by the agent/runtime. Root-level entrypoints remain as thin loaders for compatibility.

## Self-Improvement

`omega_factory.py` no longer generates new code paths directly.
Safe self-improvement in this repo must route through the existing proposal system.
Use `src.runtime.proactive_review.daily_review` to emit governed proposals and `scripts/apply_proposal.sh` to apply approved changes.

## n8n

Webhook trigger utility: `trigger_n8n_workflow.py`.
