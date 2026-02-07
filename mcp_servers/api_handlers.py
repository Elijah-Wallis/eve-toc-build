"""
Deprecated module retained only as a quarantine shim.

This file previously contained placeholder webhook URLs and ad-hoc handlers.
It is intentionally non-operational to prevent accidental runtime usage.
"""

from __future__ import annotations


class EveConnector:  # pragma: no cover
    def __init__(self) -> None:
        raise RuntimeError(
            "mcp_servers.api_handlers is quarantined. Use mcp_servers/{retell_mcp,twilio_mcp,intelligence_mcp} instead."
        )
