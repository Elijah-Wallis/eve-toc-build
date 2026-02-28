from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_SCRIPT = ROOT / "scripts" / "configure_retell_b2b_agent.py"


def test_retell_config_defaults_to_v133_prompt_and_supports_explicit_version_flag() -> None:
    text = CONFIG_SCRIPT.read_text(encoding="utf-8")
    assert "DEFAULT_PROMPT_VERSION = \"v13.3\"" in text
    assert "mcp_servers/b2b_workflow.yaml" in text
    assert "--prompt-version" in text
    assert "choices=[\"v5\", \"v6\", \"v13.3\"]" in text
