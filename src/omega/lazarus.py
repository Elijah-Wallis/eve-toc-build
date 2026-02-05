from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import sync_playwright


@dataclass
class VisionAgent:
    screenshot_dir: str = "/tmp/omega-lazarus"

    def execute_visually(self, *, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        url = context.get("url")
        if not url:
            raise RuntimeError("Vision context must include url")

        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        screenshot_path = str(Path(self.screenshot_dir) / f"lazarus-{ts}.png")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            page.screenshot(path=screenshot_path, full_page=True)
            browser.close()

        return {
            "goal": goal,
            "url": url,
            "screenshot": screenshot_path,
            "note": "Vision fallback executed",
        }
