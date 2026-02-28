from __future__ import annotations

import json
from pathlib import Path


def _load_json(p: Path) -> dict:
    obj = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(obj, dict)
    return obj


def test_sop_json_schema_and_gate_refs() -> None:
    repo = Path(__file__).resolve().parents[2]
    sop_path = repo / "dashboard" / "sop.json"
    checks_path = repo / "dashboard" / "checks.json"
    assert sop_path.exists()
    assert checks_path.exists()

    sop = _load_json(sop_path)
    checks_raw = _load_json(checks_path)

    assert int(sop.get("version") or 0) >= 1
    assert isinstance(sop.get("principles"), list)
    assert isinstance(sop.get("phases"), list)

    checks = checks_raw.get("checks") or []
    assert isinstance(checks, list)
    check_ids = {str(c.get("id") or "") for c in checks if isinstance(c, dict)}
    assert "" not in check_ids

    # All referenced gates must exist in checks.json.
    missing: set[str] = set()
    for phase in sop.get("phases") or []:
        for step in (phase.get("steps") or []) if isinstance(phase, dict) else []:
            for gid in (step.get("gates") or []) if isinstance(step, dict) else []:
                gid_s = str(gid or "")
                if gid_s and gid_s not in check_ids:
                    missing.add(gid_s)
    for g in sop.get("component_guidance") or []:
        cs = (g.get("change_safely") or {}) if isinstance(g, dict) else {}
        for gid in cs.get("gates") or []:
            gid_s = str(gid or "")
            if gid_s and gid_s not in check_ids:
                missing.add(gid_s)

    assert not missing, f"sop.json references unknown check ids: {sorted(missing)}"


def test_sop_laymen_text_is_cpom_safe() -> None:
    repo = Path(__file__).resolve().parents[2]
    sop_path = repo / "dashboard" / "sop.json"
    sop = _load_json(sop_path)

    forbidden = [
        "/api/open",
        "python3 ",
        "bash ",
        "launchctl ",
        "docker ",
        "rg ",
    ]

    def _walk(x: object) -> list[str]:
        out: list[str] = []
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "laymen" and isinstance(v, str):
                    out.append(v)
                else:
                    out.extend(_walk(v))
        elif isinstance(x, list):
            for it in x:
                out.extend(_walk(it))
        return out

    laymen_texts = _walk(sop)
    assert laymen_texts, "expected some laymen text in sop.json"
    hits: list[str] = []
    for s in laymen_texts:
        low = s.lower()
        for f in forbidden:
            if f.lower() in low:
                hits.append(f"{f} in: {s[:120]!r}")
    assert not hits, "laymen SOP text contains technical/raw tokens:\n" + "\n".join(hits)

