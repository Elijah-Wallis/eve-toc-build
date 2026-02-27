from __future__ import annotations

from src.runtime.proactive_review.redaction import redact_obj
from src.runtime.proactive_review.redaction import redact_text


def test_redaction_scrubs_secret_like_strings() -> None:
    text = "Authorization: Bearer abcdefghijklmnopqrst"
    assert "Bearer" not in redact_text(text)

    payload = {
        "token": "abcd1234secret",
        "nested": {
            "note": "SUPABASE_SERVICE_ROLE_KEY=supersecretvalue",
            "url": "https://user:pass@example.com/path",
        },
    }
    redacted = redact_obj(payload)
    assert redacted["token"] == "[REDACTED]"
    assert "supersecretvalue" not in redacted["nested"]["note"]
    assert "user:pass" not in redacted["nested"]["url"]
