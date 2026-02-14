# Voice Agent

This folder is the single home for the **Voice Agent** department/agent inside `eve-toc-build`.

## Boundaries
- Scope: voice-call LLM websocket service, Retell protocol contract, interruption/turn orchestration, and its supporting KB/docs.
- Out of scope: legal policy documents (those live under `agents/lawyer/`).

## Layout
- `service/`: the runnable Voice Agent codebase (websocket server, orchestrator, tools, tests).
- `kb/`: Voice Agent knowledge base, playbooks, and history (non-runtime artifacts).

