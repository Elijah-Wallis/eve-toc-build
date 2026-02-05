from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path

from .types import OmegaSkillSpec


@dataclass
class OmegaSkillFactory:
    """Generate an Omega skill file with Lazarus fallback and drift simulation."""

    def generate(self, spec: OmegaSkillSpec) -> Path:
        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"omega_{spec.name}.py"

        code = self._render(spec)
        target.write_text(code, encoding="utf-8")
        return target

    def _render(self, spec: OmegaSkillSpec) -> str:
        description = spec.description or f"Omega skill for {spec.name}"
        return textwrap.dedent(
            f"""
            """{description}"""

            import json
            import sys
            from pathlib import Path
            from typing import Any, Dict

            from pydantic import BaseModel, Field

            ROOT = Path(__file__).resolve().parents[2]
            SRC = ROOT / \"src\"
            if str(SRC) not in sys.path:
                sys.path.insert(0, str(SRC))

            from omega.types import RiskClass, OmegaSkillInput
            from omega.session_vault import SessionVault
            from omega.http_client import OmegaHttpClient
            from omega.validator import OmegaValidator, ValidationError
            from omega.lazarus import VisionAgent
            from omega.ledger import Ledger
            from omega.runtime import OmegaRuntime
            from omega.triad import TriadConsensus


            OPENAPI_PATH = r"{spec.openapi_path}"
            TEST_EVENT_PATH = r"{spec.test_event_path}"
            SESSION_VAULT_PATH = str(Path.home() / ".openclaw-eve" / "session_vault.json")
            LEDGER_PATH = str(Path.home() / ".openclaw-eve" / "omega" / "ledger.jsonl")


            class Input(OmegaSkillInput):
                """Omega skill input: requires both id and name."""
                pass


            def _load_test_event() -> Dict[str, Any]:
                with open(TEST_EVENT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)


            def _format_url(url_template: str, input_data: OmegaSkillInput) -> str:
                return url_template.format(
                    entity_id=input_data.entity_id,
                    entity_name=input_data.entity_name,
                )


            def api_call(input_data: OmegaSkillInput) -> Dict[str, Any]:
                test_event = _load_test_event()
                url = test_event.get("url") or test_event.get("url_template")
                if not url:
                    raise ValidationError("test_event missing url or url_template")

                url = _format_url(url, input_data)
                method = test_event.get("method", "GET")
                headers = test_event.get("headers")
                params = test_event.get("params")
                json_body = test_event.get("json_body")

                vault = SessionVault(SESSION_VAULT_PATH)
                client = OmegaHttpClient(vault)
                return client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json_body=json_body,
                    session_profile=input_data.session_profile,
                )


            def vision_goal(input_data: OmegaSkillInput) -> str:
                return f"Find entity '{{input_data.entity_name}}' visually (id={{input_data.entity_id}})."


            def run(payload: Dict[str, Any]) -> Dict[str, Any]:
                input_data = Input(**payload)

                validator = None
                if RiskClass("{spec.risk_class.value}") in (RiskClass.B, RiskClass.A):
                    validator = OmegaValidator(
                        openapi_path=OPENAPI_PATH,
                        test_event_path=TEST_EVENT_PATH,
                        session_vault_path=SESSION_VAULT_PATH,
                    )

                triad = None
                if RiskClass("{spec.risk_class.value}") == RiskClass.A:
                    def _llm_client(role: str, prompt: str) -> str:
                        raise RuntimeError("Triad LLM client not configured")
                    triad = TriadConsensus(_llm_client)

                runtime = OmegaRuntime(
                    risk_class=RiskClass("{spec.risk_class.value}"),
                    validator=validator,
                    vision_agent=VisionAgent(),
                    ledger=Ledger(LEDGER_PATH),
                    triad=triad,
                )

                return runtime.execute(
                    input_data=input_data,
                    api_call=api_call,
                    vision_goal=vision_goal,
                )
            """
        ).lstrip()
