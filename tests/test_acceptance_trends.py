from __future__ import annotations

import json
from pathlib import Path

from src.runtime.acceptance.trends import update_trends


def test_acceptance_trends_roll_last_7(tmp_path: Path) -> None:
    state = tmp_path / "state"
    for idx in range(9):
        update_trends(state, {"ok": idx % 2 == 0, "results": [{"id": f"AT-{idx}", "status": "pass"}]})

    trend_file = state / "acceptance" / "trends" / "last_7.json"
    trend = json.loads(trend_file.read_text(encoding="utf-8"))
    assert trend["count"] == 7
    assert len(trend["runs"]) == 7
