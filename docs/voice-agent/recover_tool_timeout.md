---
id: recover_tool_timeout
intent: Recover gracefully when a tool call times out without hallucinating facts.
inputs: latest user ask, timed-out tool name, known safe fallback phrasing.
outputs: short acknowledgment plus a clarifying or retry question.
constraints: Never invent unavailable pricing/availability. Keep response to 1-2 sentences.
commands: python3 -m pytest -q tests/test_tool_grounding.py
tests: tests/test_tool_grounding.py::test_tool_timeout_falls_back_without_numbers
---
When a required tool times out, acknowledge quickly, state you're checking, and ask one targeted question that can progress the turn without fabricated data.

Good pattern:
- "Thanks - I’m still checking that now. Do you want me to try a different time window?"

Avoid:
- Any numeric claims that were supposed to come from the timed-out tool.
