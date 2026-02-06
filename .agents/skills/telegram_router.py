from __future__ import annotations

from src.runtime.telegram_router import TelegramRouter


def handle_message(text: str):
    router = TelegramRouter()
    return router.handle(text)
