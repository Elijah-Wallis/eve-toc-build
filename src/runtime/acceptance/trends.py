from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


def update_trends(state_dir: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    history_dir = state_dir / "acceptance" / "history"
    trends_dir = state_dir / "acceptance" / "trends"
    history_dir.mkdir(parents=True, exist_ok=True)
    trends_dir.mkdir(parents=True, exist_ok=True)

    history_file = history_dir / f"{now}-{uuid4().hex[:8]}.json"
    history_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    files = sorted(history_dir.glob("*.json"))[-7:]
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in files]

    trend = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs,
        "count": len(runs),
    }
    out = trends_dir / "last_7.json"
    out.write_text(json.dumps(trend, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return trend
