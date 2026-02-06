from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests

from .env_loader import load_env_file
from .telegram_router import TelegramRouter


class TelegramListener:
    """Simple long-polling Telegram listener routed into TelegramRouter."""

    def __init__(self) -> None:
        load_env_file()
        self.router = TelegramRouter()
        self.bot_token = os.environ.get("OPENCLAW_TELEGRAM_BOT_TOKEN") or os.environ.get("OPENCLAW_BOT_TOKEN")
        if not self.bot_token:
            raise RuntimeError("OPENCLAW_TELEGRAM_BOT_TOKEN or OPENCLAW_BOT_TOKEN is required")
        self.base = f"https://api.telegram.org/bot{self.bot_token}"
        self.allowed_user_id = (
            os.environ.get("OPENCLAW_TELEGRAM_USER_ID")
            or os.environ.get("MY_TELEGRAM_ID")
            or os.environ.get("OPENCLAW_TELEGRAM_CHAT_ID")
        )
        self.offset = 0
        self._ensure_long_poll_mode()

    def run(self) -> None:
        while True:
            try:
                updates = self._get_updates()
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409:
                    # Another getUpdates consumer was active; enforce long-poll mode and retry.
                    self._ensure_long_poll_mode()
                    time.sleep(2)
                    continue
                time.sleep(2)
                continue
            except requests.RequestException:
                time.sleep(2)
                continue
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
        requests.post(
            f"{self.base}/sendMessage",
            json={"chat_id": chat_id, "text": str(result)},
            timeout=20,
        )

    def _ensure_long_poll_mode(self) -> None:
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


def main() -> int:
    listener = TelegramListener()
    try:
        listener.run()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
