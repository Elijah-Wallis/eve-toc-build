from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests

from .env_loader import load_env_file
from .runtime_paths import state_path
from .secrets_provider import SecretsProvider
from .telegram_router import TelegramRouter
from .telemetry import Telemetry


class TelegramListener:
    """Long-polling Telegram listener routed into TelegramRouter."""

    def __init__(self) -> None:
        load_env_file()
        self.telemetry = Telemetry(str(state_path("runtime", "telemetry.jsonl")))
        self.router = TelegramRouter()
        self.ingress_owner = os.environ.get("OPENCLAW_TELEGRAM_INGRESS_OWNER", "custom_listener").strip().lower()
        self._can_poll = self.ingress_owner in {"custom_listener", "listener", "custom"}

        secrets = SecretsProvider()
        self.bot_token = (
            secrets.get("OPENCLAW_TELEGRAM_BOT_TOKEN", allow_env_fallback=True)
            or os.environ.get("OPENCLAW_TELEGRAM_BOT_TOKEN")
            or os.environ.get("OPENCLAW_BOT_TOKEN")
        )
        if not self.bot_token and self._can_poll:
            raise RuntimeError("OPENCLAW_TELEGRAM_BOT_TOKEN is required")
        self.base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        self.allowed_user_id = (
            os.environ.get("OPENCLAW_TELEGRAM_USER_ID")
            or os.environ.get("MY_TELEGRAM_ID")
            or os.environ.get("OPENCLAW_TELEGRAM_CHAT_ID")
        )
        self.offset = 0
        self._conflict_count = 0

        if self._can_poll:
            self._ensure_long_poll_mode()
        else:
            self.telemetry.emit(
                "telegram_listener_disabled",
                {"ingress_owner": self.ingress_owner, "reason": "non_custom_owner"},
            )

    def run(self) -> None:
        while True:
            if not self._can_poll:
                time.sleep(30)
                continue
            try:
                updates = self._get_updates()
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409:
                    self._conflict_count += 1
                    self.telemetry.emit(
                        "telegram_getupdates_conflict",
                        {"conflicts": self._conflict_count, "ingress_owner": self.ingress_owner},
                    )
                    self._ensure_long_poll_mode()
                    time.sleep(2)
                    continue
                time.sleep(2)
                continue
            except requests.RequestException as exc:
                self.telemetry.emit("telegram_listener_error", {"error": f"{type(exc).__name__}:{exc}"})
                time.sleep(2)
                continue
            self._conflict_count = 0
            for update in updates:
                self.offset = max(self.offset, update["update_id"] + 1)
                message = update.get("message") or {}
                user_id = str(message.get("from", {}).get("id", ""))
                if self.allowed_user_id and user_id and user_id != self.allowed_user_id:
                    continue
                text = message.get("text")
                if not text:
                    continue
                result = self.router.handle(text)
                self._send_reply(message.get("chat", {}).get("id"), result)
            time.sleep(1)

    def _get_updates(self) -> Any:
        params: Dict[str, Any] = {"timeout": 30, "offset": self.offset}
        resp = requests.get(f"{self.base}/getUpdates", params=params, timeout=40)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def _send_reply(self, chat_id: Any, result: Dict[str, Any]) -> None:
        if not chat_id:
            return
        try:
            requests.post(
                f"{self.base}/sendMessage",
                json={"chat_id": chat_id, "text": str(result)},
                timeout=20,
            )
        except requests.RequestException as exc:
            self.telemetry.emit(
                "telegram_reply_error",
                {"error": f"{type(exc).__name__}:{exc}", "chat_id": str(chat_id)},
            )

    def _ensure_long_poll_mode(self) -> None:
        try:
            info = requests.get(f"{self.base}/getWebhookInfo", timeout=20)
            info.raise_for_status()
            webhook_url = (info.json().get("result") or {}).get("url", "")
            if not webhook_url:
                return
            resp = requests.post(
                f"{self.base}/deleteWebhook",
                json={"drop_pending_updates": False},
                timeout=20,
            )
            resp.raise_for_status()
            self.telemetry.emit("telegram_webhook_deleted", {"status": "ok"})
        except requests.RequestException as exc:
            self.telemetry.emit("telegram_webhook_delete_error", {"error": f"{type(exc).__name__}:{exc}"})


def main() -> int:
    listener = TelegramListener()
    try:
        listener.run()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
