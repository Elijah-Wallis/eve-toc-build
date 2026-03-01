# Red Team: Custom LLM + WebSocket Voice Agent Edge Cases

This document lists every known and hypothesized failure mode from the previous custom LLM attempt and additional edge cases. Each is mapped to the code or contract that prevents it.

## Past catastrophic failures (must never recur)

1. **Endless loops** — Orchestrator only starts a turn on `response_required` / `reminder_required`; never on `update_only`. Speculative planning computes in background but does not enqueue speech until `response_required`. GateRef epoch/speak_gen ensures only one active turn; writer drops stale segments. **Prevention:** `orchestrator._on_response_required` is the single entry for speech; `transport_ws.socket_writer` gate checks.
2. **Responding to partial audio / streaming chunks too early** — We do not receive raw audio; Retell sends `update_only` (partial transcript) and `response_required` (user finished). We never emit speech on `update_only`. **Prevention:** `_handle_inbound_event` branches: only `InboundResponseRequired`/`InboundReminderRequired` call `_on_response_required`; `InboundUpdateOnly` only updates transcript and may start speculative planning (no outbound speech).
3. **Cutting users off mid-sentence** — We do not speak until Retell sends `response_required`. On `InboundClear` or `turntaking=user_turn` we call `_barge_in_cancel` and stop. **Prevention:** Speech only after `response_required`; Clear and user_turn trigger immediate cancel.
4. **Over-optimized for ultra-low latency at expense of intelligence** — Temperature and timeouts are configurable (0.7–0.9 for natural variation); we do not sacrifice full prompt or reasoning for speed. **Prevention:** Config `vic_*` timeouts and LLM temperature; full V13.3 prompt when `B2B_V133_PROMPT_PATH` set.
5. **Confidently wrong / non-adaptive** — Full V13.3 prompt and temperature 0.7–0.9; directive to reason from overall goal when situation not explicit. **Prevention:** Prompt load from `b2b_workflow.yaml`; no truncation.

## Transport / WebSocket

6. **Stale response chunks for wrong response_id** — Writer checks `msg.response_id == gate_epoch` before sending; drops otherwise. **Prevention:** `socket_writer` gate check and `response_type == "response"` + `response_id` match.
7. **Frame too large / OOM** — Reader drops frames over `max_frame_bytes` and closes with `FRAME_TOO_LARGE`. **Prevention:** `socket_reader` size check.
8. **Bad JSON / schema drift** — Unknown or invalid JSON increments `inbound.bad_schema_total` and we continue (do not tear down session). **Prevention:** `parse_inbound_obj` in try/except; continue on schema error.
9. **Write timeout backpressure** — After `ws_max_consecutive_write_timeouts` we close with `WRITE_TIMEOUT_BACKPRESSURE` to avoid unbounded queue growth. **Prevention:** `socket_writer` consecutive_write_timeouts and `_signal_fatal_and_stop`.
10. **Control plane starved by update_only flood** — Ping/clear evict update_only when queue full. **Prevention:** `socket_reader` evict policies for ping_pong and InboundClear.
11. **Ping/pong missed deadline** — Writer observes delay and increments `keepalive_ping_pong_missed_deadline_total`. **Prevention:** `_send_payload` deadline check for ping_pong.
12. **Speech preempted by control** — Writer uses `get_prefer(_is_control_envelope)` and sends control frames first; speech can be requeued. **Prevention:** `socket_writer` control vs speech plane handling.
13. **Gate change mid-send** — If gate_task completes (epoch/speak_gen changed), we cancel send_task and drop segment. **Prevention:** `asyncio.wait` on send_task, gate_task, control_wait_task; cancel send on gate change.

## Orchestrator / turn handling

14. **Two response_required with same response_id** — Idempotent; we re-apply epoch and re-run turn. **Prevention:** Epoch set atomically; duplicate handling is safe.
15. **response_required N then N+1 before N completed** — We set epoch to N+1, cancel N’s turn, drop queued segments for N via gate. **Prevention:** `_on_response_required` sets gate epoch; writer drops by epoch.
16. **Reminder with no user utterance** — We send empty terminal and return; no speech. **Prevention:** `_on_response_required` reminder branch when `not (last_user or "").strip()`.
17. **Low-signal / repeated noise** — B2B fast-path: empty or no-signal turns get empty terminal, no opener. **Prevention:** `b2b_repeated_low_signal` / `b2b_repeated_empty_or_noise` and low_signal noop branches.
18. **Tool call in flight then interrupt** — Turn handler cancelled; tool result not sent for interrupted epoch. **Prevention:** `_cancel_turn`; gate bump drops stale tool_call_result for old epoch.
19. **SlotState mutated then epoch interrupted** — We roll back slot state from backup when epoch cancelled before terminal. **Prevention:** `_rollback_turn_state_backup` in `_barge_in_cancel` and on new_epoch when no speech sent.
20. **Sensitive capture (medical etc.)** — Safety policy blocks or rewrites; we do not emit unsafe content. **Prevention:** `evaluate_user_text` and dialogue policy.

## Concurrency / production

21. **20 concurrent calls** — Bounded queues (inbound/outbound 256); each session has own orchestrator and gate. **Prevention:** Per-connection state; no shared mutable global.
22. **Cloudflare tunnel connection limits** — Tunnel config and deploy docs: originRequest connectTimeout, keepAliveTimeout, multiple replicas. **Prevention:** `deploy/cloudflare/` README and docker-compose.
23. **LLM timeout / provider failure** — Turn handler has timeouts; on failure we can emit empty or fallback (configurable). **Prevention:** LLM client timeouts; graceful degradation in turn handler.
24. **Retell reconnect** — We send config and update_agent on start; auto_reconnect keeps session alive. **Prevention:** `retell_auto_reconnect` and ping_loop.
25. **Session end while turn in progress** — Shutdown sets gate and closes queues; writer and reader exit; turn task cancelled. **Prevention:** `end_session` cancels turn_task and closes queues.

## Novel / adaptive situations

26. **Situation not in prompt** — Full V13.3 includes goal and “taste”; we use temperature 0.7–0.9 so model can reason. **Prevention:** No over-tightening of prompt; temperature in config.
27. **Manager handoff / conversion goal** — Prompt explicitly includes escalation layering and conversion focus. **Prevention:** V13.3 prompt unchanged.
28. **DNC / compliance** — Prompt has DNC RULE and COMPLIANCE RULE; tools for mark_dnc_compliant. **Prevention:** Prompt + tool wiring.
29. **Missing promo variables** — VARIABLE SAFETY in prompt; placeholders substituted with safe fallbacks in loader. **Prevention:** `b2b_v133_prompt` placeholders and variable_safety in YAML.
30. **Bilingual / Spanish** — BILINGUAL RULE and nuclear_silence_keywords; we do not talk over. **Prevention:** Prompt directives.
31. **Hold / transfer** — HOLD RULE, LONG HOLD HEARTBEAT, TRANSFER RULE in prompt. **Prevention:** V13.3 conversation_flow and core_directives.
32. **Voicemail** — VOICEMAIL RULE; fallback only on explicit voicemail or 25s silence. **Prevention:** Prompt.
33. **False interruption** — We only cancel on Clear or user_turn; we do not cancel on every update_only. **Prevention:** `interrupt_pre_ack_on_agent_turn_enabled` OFF by default; barge_in only on clear/user_turn.
34. **Reasoning leak** — voice_no_reasoning_leak and plain-language mode. **Prevention:** Config and prompt “Never explain your internal reasoning”.
35. **Endless filler** — vic_max_fillers_per_tool and vic_max_reprompts cap fillers and reprompts. **Prevention:** Config and turn handler limits.

## Monitoring and fallback

36. **Custom LLM unhealthy** — Health check and metrics; ops can switch agent back to Retell-hosted LLM via dashboard. **Prevention:** `/healthz`, `/metrics`, and runbook to clear `llm_websocket_url` on agent.
37. **Metrics for debugging** — VIC metrics: stale_segment_dropped_total, barge_in_cancel_latency_ms, keepalive, write timeouts. **Prevention:** Prometheus export and VIC keys in metrics.
38. **Structured logging** — Optional ws_structured_logging for frame-level debugging. **Prevention:** BrainConfig.ws_structured_logging and socket_reader _log.
