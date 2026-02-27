from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CapabilityGrant:
    token: str
    decision_id: str
    scope: str
    issued_at: float
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class CapabilityTokenStore:
    def __init__(self) -> None:
        self._grants: Dict[str, CapabilityGrant] = {}

    def issue(self, *, decision_id: str, scope: str, ttl_seconds: int) -> CapabilityGrant:
        now = time.time()
        token = f"cap_{secrets.token_urlsafe(24)}"
        grant = CapabilityGrant(
            token=token,
            decision_id=decision_id,
            scope=scope,
            issued_at=now,
            expires_at=now + max(1, int(ttl_seconds)),
        )
        self._grants[token] = grant
        return grant

    def consume(self, token: str) -> Optional[CapabilityGrant]:
        grant = self._grants.get(token)
        if grant is None:
            return None
        if grant.expired:
            self._grants.pop(token, None)
            return None
        return grant
