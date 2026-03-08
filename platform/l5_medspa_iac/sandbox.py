from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict

from .generator import generate_platform_bundle
from .generator import write_generation_result


def build_sandbox_snapshot(source: str | Dict[str, Any], output_dir: str | Path) -> Dict[str, Any]:
    result = generate_platform_bundle(source)
    written = write_generation_result(result, output_dir)
    summary = {
        "client_id": result.spec.client_id,
        "medspa_name": result.spec.medspa_name,
        "thermo_triage": result.optimization.triage.to_dict(),
        "forecast": result.optimization.forecast,
        "bottlenecks": result.optimization.bottlenecks,
        "selected_interventions": [item.to_dict() for item in result.optimization.selected_interventions],
        "written_files": [str(path) for path in written],
    }
    snapshot_path = Path(output_dir) / f"generated/{result.spec.slug}/sandbox_snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
