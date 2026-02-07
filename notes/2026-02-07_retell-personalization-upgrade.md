# Retell B2B Personalization Upgrade (2026-02-07)

## Agent / LLM
- Agent: `agent_5d6f2744acfc79e26ddce13af2`
- LLM: `llm_6c9f14b95d2b0379552a31221935`

## Knowledge Base
- Created and attached: `knowledge_base_9937ed8adf6aab4f`
- Name: `MedSpa B2B TX Knowledge Base`
- Source file: `Business_Code/retell_kb_medspa_b2b.md`
- LLM `kb_config`: `top_k=5`, `filter_score=0.45`

## Retell Tool Pack Added
- `get_lead_context` -> `POST /webhook/openclaw-retell-fn-context-brief`
- `recommend_offer_angle` -> `POST /webhook/openclaw-retell-fn-offer-angle`
- `log_call_insight` -> `POST /webhook/openclaw-retell-fn-log-insight`
- `set_follow_up_plan` -> `POST /webhook/openclaw-retell-fn-set-followup`
- `mark_do_not_call` -> `POST /webhook/openclaw-retell-fn-mark-dnc`

Existing tools preserved:
- `end_call`
- `calculate_dynamic_loss`

## N8N Workflows Deployed
- `openclaw_retell_fn_context_brief` (`3mZbSznKRMfUvmqI`) active
- `openclaw_retell_fn_offer_angle` (`2ehfW4Sl5qHPYVKf`) active
- `openclaw_retell_fn_log_insight` (`SSWGGI9ak13PC5kj`) active
- `openclaw_retell_fn_set_followup` (`cE5PXyf5AAn6bCHy`) active
- `openclaw_retell_fn_mark_dnc` (`qn7qDAAwpzNkqMbV`) active

## Runtime Hardening Included
- N8N MCP entry normalized on LLM:
  - URL: `https://elijah-wallis.app.n8n.cloud/mcp-server/http`
  - Authorization header set with bearer MCP token
- Dispatch workflow dynamic vars expanded for personalization:
  - `business_name`, `city`, `state`, `website`, `category`,
  - `rating`, `reviews_count`, `touch_count`, `lead_id`, `source`

## Repro Scripts
- `scripts/deploy_retell_personalization_workflows.py`
- `scripts/configure_retell_b2b_agent.py`
- `scripts/patch_workflows_for_campaign_filters.py`
