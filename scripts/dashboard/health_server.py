#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import html
import os
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT / "dashboard"
CHECKS_PATH = DASHBOARD_DIR / "checks.json"
SYSTEM_MAP_PATH = DASHBOARD_DIR / "system_map.json"
# Changes whenever this file changes; used by eve-dashboard to restart stale servers.
SERVER_BUILD = str(int(Path(__file__).stat().st_mtime))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _truncate(s: str, limit: int = 7000) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 20] + "\n...<truncated>...\n"


def _run_shell(command: str, timeout_s: int, cwd: Path) -> Tuple[Optional[int], str]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            text=True,
            env=os.environ.copy(),
        )
        return proc.returncode, _truncate(proc.stdout or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\nTIMEOUT\n"
        return 124, _truncate(out)
    except Exception as e:
        return 125, _truncate(f"ERROR: {type(e).__name__}: {e}\n")


def _run_python(rel_path: str, timeout_s: int, cwd: Path) -> Tuple[Optional[int], str]:
    # Use the host python; scripts should be stdlib-only (or repo-internal imports).
    cmd = f"python3 {rel_path}"
    return _run_shell(cmd, timeout_s=timeout_s, cwd=cwd)


def _extract_json_ok(output: str) -> Optional[bool]:
    # Expect a single JSON object. If the output contains extra lines, this returns None.
    try:
        obj = json.loads(output)
        ok = obj.get("ok")
        if isinstance(ok, bool):
            return ok
        return None
    except Exception:
        return None


def _extract_json(output: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(output)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _state_dir() -> Path:
    base = Path(os.environ.get("OPENCLAW_STATE_DIR") or (Path.home() / ".openclaw-eve"))
    return base


def _dashboard_state_dir() -> Path:
    p = _state_dir() / "dashboard"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _suggest_paths(rel: str, limit: int = 12) -> List[str]:
    needle = Path(rel or "").name.strip().lower()
    if not needle:
        return []
    out: List[str] = []
    try:
        for root, dirs, files in os.walk(str(ROOT)):
            # Prune noisy directories quickly.
            dirs[:] = [d for d in dirs if d not in {".git", ".pytest_cache", "__pycache__", "node_modules"}]
            for name in dirs + files:
                if needle in name.lower():
                    p = Path(root) / name
                    try:
                        out.append(str(p.relative_to(ROOT)))
                    except Exception:
                        continue
                    if len(out) >= limit:
                        return out
    except Exception:
        return []
    return out


def _error_page(title: str, message: str, *, details: str = "", actions: Optional[List[Tuple[str, str]]] = None) -> bytes:
    actions = actions or []
    actions_html = "".join(f"<a href='{html.escape(href)}'>{html.escape(label)}</a>" for label, href in actions)
    details_html = f"<pre class='mono pre'>{html.escape(details)}</pre>" if details else ""
    doc = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="/app.css" />
    <link rel="stylesheet" href="/ux.css" />
  </head>
  <body>
    <div class="bg"></div>
    <main class="wrap">
      <section class="panel">
        <div class="panel-title">{html.escape(title)}</div>
        <div class="panel-body">
          <div class="ux-lede">{html.escape(message)}</div>
          <div class="ux-actions">
            <a href="/">Back to Dashboard</a>
            <a href="/deck">Pitch Deck</a>
            {actions_html}
          </div>
          {details_html}
        </div>
      </section>
    </main>
  </body>
</html>
"""
    return doc.encode("utf-8")


def _pretty_href_for_open(href: str) -> str:
    """
    Transform /api/open?path=... into a human-friendly page:
    - directories -> /open?path=...
    - files       -> /doc?path=...
    Leave non-/api/open hrefs unchanged.
    """
    try:
        if not href.startswith("/api/open"):
            return href
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        rel = unquote((qs.get("path", [""])[0] or "").strip())
        if rel == "":
            return "/open?path="
        target = _safe_join(ROOT, rel)
        if target and target.exists() and target.is_dir():
            return "/open?path=" + quote(rel)
        return "/doc?path=" + quote(rel)
    except Exception:
        return href


def _bundle_key(bundle: Optional[str], deep: bool) -> str:
    if bundle and bundle.strip():
        return bundle.strip().lower()
    return "fast" if not deep else "deep"


def _state_paths(bundle_key: str) -> Dict[str, Path]:
    root = _dashboard_state_dir()
    return {
        "last": root / f"health_last_{bundle_key}.json",
        "green": root / f"health_green_{bundle_key}.json",
    }


def _git(cmd: List[str], timeout_s: int = 2) -> str:
    try:
        proc = subprocess.run(
            ["git", *cmd],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        out = (proc.stdout or "").strip()
        return out
    except Exception:
        return ""


def _git_dirty() -> bool:
    try:
        proc = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        if proc.returncode != 0:
            return True
        proc2 = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        return proc2.returncode != 0
    except Exception:
        return False


def _git_info(last_green_head: Optional[str] = None) -> Dict[str, Any]:
    head = _git(["rev-parse", "HEAD"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = _git_dirty()
    diffstat = ""
    if last_green_head and head and last_green_head != head:
        diffstat = _git(["diff", "--stat", f"{last_green_head}..{head}"], timeout_s=6)
    return {
        "head": head or None,
        "branch": branch or None,
        "dirty": bool(dirty),
        "last_green_head": last_green_head or None,
        "diffstat": diffstat or "",
    }


@dataclass(frozen=True)
class CheckDef:
    id: str
    group: str
    name: str
    purpose: Dict[str, str]
    how_to_fix: Dict[str, str]
    kind: str
    command: str
    timeout_s: int
    default: bool
    expect_json_ok: bool
    host_only: bool
    bundles: Tuple[str, ...]


def _load_checks() -> List[CheckDef]:
    raw = _read_json(CHECKS_PATH)
    items = raw.get("checks") or []
    out: List[CheckDef] = []
    for c in items:
        bundles_raw = c.get("bundles") or []
        bundles: List[str] = []
        if isinstance(bundles_raw, list):
            bundles = [str(x).strip().lower() for x in bundles_raw if str(x).strip()]
        out.append(
            CheckDef(
                id=str(c.get("id") or ""),
                group=str(c.get("group") or "Other"),
                name=str(c.get("name") or c.get("id") or "check"),
                purpose=c.get("purpose") or {"laymen": "", "technical": ""},
                how_to_fix=c.get("how_to_fix") or {"laymen": "", "technical": ""},
                kind=str(c.get("kind") or "shell"),
                command=str(c.get("command") or ""),
                timeout_s=int(c.get("timeout_s") or 10),
                default=bool(c.get("default", True)),
                expect_json_ok=bool(c.get("expect_json_ok", False)),
                host_only=bool(c.get("host_only", False)),
                bundles=tuple(bundles),
            )
        )
    return out


def run_checks(deep: bool, bundle: Optional[str]) -> Dict[str, Any]:
    start = _now_ms()
    defs = _load_checks()

    bundle_norm = (bundle or "").strip().lower()
    # Special: "full" means deep run with all checks.
    if bundle_norm == "full":
        bundle_norm = ""
        deep = True

    results: List[Dict[str, Any]] = []
    for d in defs:
        if not deep and not d.default:
            continue
        if deep and bundle_norm and not d.default and bundle_norm not in d.bundles:
            continue

        if d.host_only and os.uname().sysname.lower() != "darwin":
            # Mark as unknown (not applicable).
            results.append(
                {
                    "id": d.id,
                    "group": d.group,
                    "name": d.name,
                    "purpose": d.purpose,
                    "how_to_fix": d.how_to_fix,
                    "kind": d.kind,
                    "command": d.command,
                    "timeout_s": d.timeout_s,
                    "ok": None,
                    "duration_ms": 0,
                    "output": "N/A: host_only check on non-macOS",
                }
            )
            continue

        c_start = _now_ms()
        if d.kind == "shell":
            code, output = _run_shell(d.command, timeout_s=d.timeout_s, cwd=ROOT)
        elif d.kind == "python":
            code, output = _run_python(d.command, timeout_s=d.timeout_s, cwd=ROOT)
        else:
            code, output = 2, f"Unknown kind: {d.kind}"
        c_end = _now_ms()

        ok: Optional[bool]
        parsed: Optional[Dict[str, Any]] = None
        if d.expect_json_ok:
            ok = _extract_json_ok(output)
            parsed = _extract_json(output)
            if ok is None:
                ok = False if code not in (0, None) else None
        else:
            ok = True if code == 0 else False

        results.append(
            {
                "id": d.id,
                "group": d.group,
                "name": d.name,
                "purpose": d.purpose,
                "how_to_fix": d.how_to_fix,
                "kind": d.kind,
                "command": d.command,
                "timeout_s": d.timeout_s,
                "ok": ok,
                "duration_ms": c_end - c_start,
                "output": output,
                "parsed": parsed,
            }
        )

    pass_count = sum(1 for r in results if r.get("ok") is True)
    fail_count = sum(1 for r in results if r.get("ok") is False)
    total_count = len(results)
    summary_ok: Optional[bool]
    if total_count == 0:
        summary_ok = None
    else:
        summary_ok = fail_count == 0

    end = _now_ms()
    bundle_key = _bundle_key(bundle_norm, deep=deep)
    paths = _state_paths(bundle_key)
    last_green_head = None
    if paths["green"].exists():
        try:
            last_green = json.loads(paths["green"].read_text(encoding="utf-8"))
            last_green_head = (last_green.get("summary") or {}).get("git_head")
        except Exception:
            last_green_head = None

    payload = {
        "summary": {
            "ok": summary_ok,
            "deep": deep,
            "bundle": bundle_key,
            "generated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            "duration_ms": end - start,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "total_count": total_count,
            "git_head": _git(["rev-parse", "HEAD"]) or None,
            "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]) or None,
            "git_dirty": _git_dirty(),
        },
        "checks": results,
    }

    # Persist last run and last-green snapshot.
    try:
        paths["last"].write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        if summary_ok is True:
            paths["green"].write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    # Attach git delta info (small, for the UI).
    payload["git"] = _git_info(last_green_head=last_green_head)
    return payload


def _load_cached(bundle_key: str) -> Optional[Dict[str, Any]]:
    paths = _state_paths(bundle_key)
    if not paths["last"].exists():
        return None
    try:
        return json.loads(paths["last"].read_text(encoding="utf-8"))
    except Exception:
        return None


def compute_delta(bundle: Optional[str]) -> Dict[str, Any]:
    bundle_norm = (bundle or "").strip().lower()
    if bundle_norm == "full":
        bundle_norm = "deep"
    if not bundle_norm:
        bundle_norm = "fast"

    paths = _state_paths(bundle_norm)
    last = _load_cached(bundle_norm) or {}
    green: Dict[str, Any] = {}
    if paths["green"].exists():
        try:
            green = json.loads(paths["green"].read_text(encoding="utf-8"))
        except Exception:
            green = {}

    last_ok = ((last.get("summary") or {}).get("ok"))
    last_run_at = (last.get("summary") or {}).get("generated_at_iso")
    green_head = (green.get("summary") or {}).get("git_head")

    # Check deltas: compare last green -> last (cached).
    def _status_map(payload: Dict[str, Any]) -> Dict[str, Optional[bool]]:
        out: Dict[str, Optional[bool]] = {}
        for c in payload.get("checks") or []:
            out[str(c.get("id") or "")] = c.get("ok")
        return out

    last_map = _status_map(last)
    green_map = _status_map(green)
    flipped_to_fail = sorted([k for k, v in last_map.items() if v is False and green_map.get(k) is True])
    flipped_to_pass = sorted([k for k, v in last_map.items() if v is True and green_map.get(k) is False])
    failing_now = sorted([k for k, v in last_map.items() if v is False])

    git = _git_info(last_green_head=green_head)

    return {
        "bundle": bundle_norm,
        "run_ready": {
            "ok": True if last_ok is True else False if last_ok is False else None,
            "last_run_at": last_run_at,
        },
        "git": git,
        "check_deltas": {
            "flipped_to_fail": flipped_to_fail,
            "flipped_to_pass": flipped_to_pass,
            "failing_now": failing_now,
        },
    }


def repo_overview() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if SYSTEM_MAP_PATH.exists():
        payload.update(_read_json(SYSTEM_MAP_PATH))
    else:
        payload["system_map"] = []
        payload["repo_tour"] = []

    # Add a small computed index for "basically everything in the repo" at a glance:
    top = []
    for p in sorted(ROOT.iterdir(), key=lambda x: x.name.lower()):
        if p.name in {".git", ".pytest_cache", "__pycache__", ".DS_Store"}:
            continue
        kind = "dir" if p.is_dir() else "file"
        top.append({"name": p.name, "kind": kind})
    payload["top_level"] = top

    # Footprint stats (quick intuition, good for pitch-deck mode).
    def _count(glob: str) -> int:
        return len(list(ROOT.glob(glob)))

    payload["stats"] = {
        "workflows_n8n_json": len(list((ROOT / "workflows_n8n").glob("*.json"))) if (ROOT / "workflows_n8n").exists() else 0,
        "runtime_py": len(list((ROOT / "src" / "runtime").rglob("*.py"))) if (ROOT / "src" / "runtime").exists() else 0,
        "contracts_py": len(list((ROOT / "tests" / "contracts").glob("*.py"))) if (ROOT / "tests" / "contracts").exists() else 0,
        "scripts_total": len(list((ROOT / "scripts").rglob("*"))) if (ROOT / "scripts").exists() else 0,
        "services_dirs": len([p for p in (ROOT / "services").iterdir() if p.is_dir()]) if (ROOT / "services").exists() else 0,
        "mcp_servers_dirs": len([p for p in (ROOT / "mcp_servers").iterdir() if p.is_dir()]) if (ROOT / "mcp_servers").exists() else 0,
        "business_docs_md": len(list((ROOT / "Business_Code").rglob("*.md"))) if (ROOT / "Business_Code").exists() else 0,
        "notes_md": len(list((ROOT / "notes").rglob("*.md"))) if (ROOT / "notes").exists() else 0,
    }
    return payload


def _safe_join(base: Path, rel: str) -> Optional[Path]:
    """
    Prevent path traversal while still allowing reading symlink files that live *inside*
    the repo tree (even if their targets resolve elsewhere). This keeps /api/open useful
    for canonical policy symlinks.
    """
    try:
        base_abs = str(base.absolute())
        joined = Path(os.path.normpath(str((base / rel).absolute())))
        common = os.path.commonpath([base_abs, str(joined)])
        if common != base_abs:
            return None
        return joined
    except Exception:
        return None


def _iso_mtime(p: Path) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
    except Exception:
        return ""


def fs_list(rel: str) -> Dict[str, Any]:
    rel = (rel or "").strip().lstrip("/")
    target = _safe_join(ROOT, rel)
    if not target:
        return {"ok": False, "error": "not found", "path": rel}

    # CPOM + ops ergonomics: template files can be symlinks to canonical workspace docs.
    # If the symlink target is missing on this machine, we still want the dashboard
    # to show a readable explanation instead of a hard 404.
    if not target.exists():
        if target.is_symlink():
            try:
                st = target.lstat()
                mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            except Exception:
                mtime = ""
            try:
                link_target = os.readlink(str(target))
            except Exception:
                link_target = ""
            return {
                "ok": True,
                "kind": "file",
                "path": rel,
                "size": None,
                "mtime": mtime,
                "entries": [],
                "broken_symlink": True,
                "link_target": link_target,
            }
        return {"ok": False, "error": "not found", "path": rel}

    if target.is_dir():
        entries = []
        for p in sorted(target.iterdir(), key=lambda x: x.name.lower()):
            if p.name in {".git", ".pytest_cache", "__pycache__", ".DS_Store"}:
                continue
            kind = "dir" if p.is_dir() else "file"
            size = None
            if kind == "file":
                try:
                    size = int(p.stat().st_size)
                except Exception:
                    size = None
            try:
                relp = str(p.relative_to(ROOT))
            except Exception:
                continue
            entries.append(
                {
                    "name": p.name,
                    "kind": kind,
                    "rel": relp,
                    "size": size,
                    "mtime": _iso_mtime(p),
                }
            )
        return {"ok": True, "kind": "dir", "path": rel, "entries": entries}

    # file
    size = None
    try:
        size = int(target.stat().st_size)
    except Exception:
        size = None
    return {"ok": True, "kind": "file", "path": rel, "size": size, "mtime": _iso_mtime(target), "entries": []}


def _load_system_map() -> Dict[str, Any]:
    try:
        return _read_json(SYSTEM_MAP_PATH)
    except Exception:
        return {"system_map": [], "repo_tour": []}


def _find_topic(topic: str) -> Optional[Dict[str, Any]]:
    data = _load_system_map()
    topic_norm = topic.strip().lower()
    for node in data.get("system_map") or []:
        if str(node.get("id") or "").strip().lower() == topic_norm:
            return node

    # Allow repo_tour items to be UX topics too (pitch-deck mode).
    for card in data.get("repo_tour") or []:
        if str(card.get("id") or "").strip().lower() == topic_norm:
            # Normalize to the "system_map node" shape used by build_ux_payload.
            links = []
            link = card.get("link") or {}
            if link.get("label") and link.get("href"):
                links.append({"label": str(link.get("label")), "href": str(link.get("href"))})
            return {
                "id": str(card.get("id") or ""),
                "name": str(card.get("name") or ""),
                "desc": card.get("desc") or {},
                "links": links,
            }
    return None


def _extract_skills_registry() -> List[Dict[str, Any]]:
    """
    Parse SKILLS.md in a best-effort way (no external markdown libs).
    Focus: Revenue MCP Registry bullets.
    """
    path = ROOT / "SKILLS.md"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    items: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("## "):
            in_section = line.strip() == "## Revenue MCP Registry"
            cur = None
            continue
        if not in_section:
            continue
        if line.startswith("- `") and "`" in line[3:]:
            # Start a new registry item.
            if cur:
                items.append(cur)
            cur = {"name": "", "scope": "", "endpoint": "", "details": []}
            # Example: - `n8n MCP` (remote): `https://...`
            try:
                name = line.split("`", 2)[1]
                cur["name"] = name
                if "(" in line and ")" in line and "):" in line:
                    scope = line.split("(", 1)[1].split(")", 1)[0].strip()
                    cur["scope"] = scope
                if ": `" in line:
                    endpoint = line.split(": `", 1)[1].rsplit("`", 1)[0]
                    cur["endpoint"] = endpoint
            except Exception:
                pass
            continue
        if cur and (line.startswith("  - ") or line.startswith("    - ")):
            cur["details"].append(line.strip(" -"))

    if cur:
        items.append(cur)
    return items


def _skills_laymen_enables(name: str) -> str:
    key = name.strip().lower()
    mapping = {
        "n8n mcp": "Runs automation workflows (the orchestration brain for external actions).",
        "supabase_mcp": "Durable memory and data storage (Eve's database and truth tables).",
        "apify_mcp": "Web intelligence ingestion (scraping and enrichment for leads/targets).",
        "retell_mcp": "Voice calls (Eve can place or manage phone/web calls).",
        "twilio_mcp": "Messaging and telephony delivery (SMS and calling rails).",
        "intelligence_mcp": "Operator intelligence (lead snapshots, recent events, context packets).",
        "cloudflare_mcp": "Infrastructure routing (tunnels and DNS for reliable connectivity).",
    }
    return mapping.get(key, "System connector that extends Eve's capabilities.")


def build_ux_payload(topic: str, audience: str) -> Dict[str, Any]:
    aud = (audience or "laymen").strip().lower()
    if aud not in {"laymen", "technical"}:
        aud = "laymen"

    node = _find_topic(topic)
    title = node.get("name") if node else topic
    desc = (node.get("desc") or {}) if node else {}
    overview = str(desc.get(aud) or desc.get("laymen") or desc.get("technical") or "")

    code_links = []
    if node:
        for link in node.get("links") or []:
            label = str(link.get("label") or "")
            href = str(link.get("href") or "")
            if label and href:
                code_links.append({"label": label, "href": href})

    # UI/UX lens should link to human-friendly Explorer/Doc pages.
    pretty_links = [{"label": x["label"], "href": _pretty_href_for_open(str(x.get("href") or ""))} for x in code_links]

    # UI/UX HTML
    if topic.strip().lower() == "capabilities_skills":
        registry = _extract_skills_registry()
        rows = []
        for item in registry:
            name = str(item.get("name") or "")
            scope = str(item.get("scope") or "")
            endpoint = str(item.get("endpoint") or "")
            details = item.get("details") or []

            if aud == "technical":
                detail_text = "\n".join(str(d) for d in details if d)
                rows.append(
                    "<tr>"
                    f"<td><b>{html.escape(name)}</b><div class='muted'>({html.escape(scope or 'n/a')})</div></td>"
                    f"<td class='mono'>{html.escape(endpoint or '')}</td>"
                    f"<td class='mono'>{html.escape(detail_text or '')}</td>"
                    "</tr>"
                )
            else:
                rows.append(
                    "<tr>"
                    f"<td><b>{html.escape(name)}</b><div class='muted'>({html.escape(scope or 'n/a')})</div></td>"
                    f"<td>{html.escape(_skills_laymen_enables(name))}</td>"
                    "</tr>"
                )

        if aud == "technical":
            table = (
                "<table class='ux-table'>"
                "<thead><tr><th>Connector</th><th>Endpoint / Command</th><th>Expected Tools / Notes</th></tr></thead>"
                f"<tbody>{''.join(rows) if rows else ''}</tbody>"
                "</table>"
            )
        else:
            table = (
                "<table class='ux-table'>"
                "<thead><tr><th>Connector</th><th>What It Enables</th></tr></thead>"
                f"<tbody>{''.join(rows) if rows else ''}</tbody>"
                "</table>"
            )

        actions_uiux = (
            "<div class='ux-actions'>"
            "<a href='/doc?path=SKILLS.md'>Read SKILLS.md</a>"
            "<a href='/open?path=.agents/skills/'>Explore .agents/skills/</a>"
            "<a href='/open?path=mcp_servers/'>Explore mcp_servers/</a>"
            "</div>"
        )
        actions_code = (
            "<div class='ux-actions'>"
            "<a href='/api/open?path=SKILLS.md'>Open SKILLS.md</a>"
            "<a href='/api/open?path=.agents/skills/'>Open .agents/skills/</a>"
            "<a href='/api/open?path=mcp_servers/'>Open mcp_servers/</a>"
            "</div>"
        )

        uiux_html = (
            f"<div class='ux-lede'>{html.escape(overview)}</div>"
            "<div class='ux-callout'>"
            "<b>CPOM-safe view:</b> This is the capabilities layer and outcome story. It avoids implementation details, secrets, and internal mechanics unless you switch to the Code tab."
            "</div>"
            + actions_uiux
            + "<h3>MCP Connectors (Skills Substrate)</h3>"
            + table
            + "<h3>What This Unlocks</h3>"
            + (
                "<ul>"
                "<li>Eve can observe, decide, and execute through audited connectors instead of hand-waving.</li>"
                "<li>Every external action can be gated by acceptance checks (Run Ready) before you allow autonomy.</li>"
                "<li>Capabilities scale by adding connectors and contracts, not by changing the core identity.</li>"
                "</ul>"
                if aud == "laymen"
                else "<ul>"
                "<li>Connectors expose discrete tools (MCP) with typed inputs/outputs.</li>"
                "<li>Runtime uses policy + gates to decide when to call tools.</li>"
                "<li>Contract tests enforce invariants before deployments or autonomous execution.</li>"
                "</ul>"
            )
        )

        # Code tab: show quick links + SKILLS.md excerpt
        skills_path = ROOT / "SKILLS.md"
        raw = ""
        try:
            raw = skills_path.read_text(encoding="utf-8")
        except Exception:
            raw = ""
        code_html = (
            "<div class='ux-callout'>"
            "<b>Code view:</b> This is the operational truth. It is for builders. For CPOM-safe communication, use the UI/UX tab."
            "</div>"
            "<h3>Source of Truth</h3>"
            + actions_code
            + "<h3>SKILLS.md (excerpt)</h3>"
            f"<pre class='mono pre'>{html.escape(_truncate(raw, limit=12000))}</pre>"
        )

        return {
            "ok": True,
            "topic": topic,
            "title": title,
            "audience": aud,
            "uiux_html": uiux_html,
            "code_html": code_html,
            "code_links": code_links,
        }

    topic_key = topic.strip().lower()
    story_overrides: Dict[str, Dict[str, str]] = {
        "identity_constraints": {
            "laymen": (
                "Eve’s identity and constraints are the non-negotiables: what she is allowed to do, what she must never do, "
                "and how she stays grounded in physical reality. This is where hallucination risk is reduced by design."
            ),
            "technical": (
                "Canonical identity/policy docs (soul.md + templates) and symlink invariants. These define constraints, "
                "threat boundaries, and the operating contract for any execution layer."
            ),
        },
        "runtime_core": {
            "laymen": (
                "This is the decision engine: it turns inputs into next actions. It is where we encode least-action behavior "
                "(minimum friction) without breaking safety constraints."
            ),
            "technical": (
                "Python runtime modules and orchestrator entrypoints. The runtime should prefer deterministic state + explicit tools "
                "over free-form generation."
            ),
        },
        "config_policy": {
            "laymen": (
                "Configuration wires Eve to the outside world. The rule is simple: secrets live in environment bindings, and the repo "
                "stays shareable without leaking tokens."
            ),
            "technical": (
                "openclaw.json + config/ + policy/ plus env handling. Workflows and services must bind secrets via env/vars, never "
                "literal tokens committed to JSON."
            ),
        },
        "workflows_n8n": {
            "laymen": (
                "Workflows are how Eve performs real actions. Each workflow is a controlled sequence: get facts, decide, then act. "
                "They should be gated by acceptance checks before execution."
            ),
            "technical": (
                "n8n workflow JSON plus deployment/patch tooling. Secrets must be expression-bound (={{$env.*}} or ={{$vars.*}}) "
                "and the dashboard enforces this invariant."
            ),
        },
        "acceptance_gates": {
            "laymen": (
                "These are the go/no-go gates before you let Eve touch reality. If a gate is red, you don’t run autonomous commands. "
                "Green means the system is operating as intended for that bundle."
            ),
            "technical": (
                "Acceptance runner + contracts/integration checks. Bundles map to different confidence levels (smoke -> patched_prod -> "
                "hardening/docker). The dashboard shows pass/fail and preserves last-green baselines."
            ),
        },
        "storage_schema": {
            "laymen": (
                "Storage is where Eve keeps durable memory and structure (truth tables). The goal is reproducibility: the same inputs "
                "should produce the same outputs unless the data changed."
            ),
            "technical": (
                "Supabase schema and migrations. Treat DB state as a sensor: validate constraints, enforce schemas, and minimize "
                "untracked side-effects."
            ),
        },
        "ops_deploy": {
            "laymen": (
                "Operations is how Eve stays online. It includes the scripts and runbooks to start, stop, and verify the system on a "
                "machine so you can trust what you’re seeing."
            ),
            "technical": (
                "Docker, launchd scripts, and ops docs. These define process supervision and environment provisioning; acceptance gates "
                "should be run before enabling automation."
            ),
        },
        "knowledge_base": {
            "laymen": (
                "The knowledge base is what Eve references. It should be treated like a library: curated, auditable, and separated "
                "from execution so ‘knowing’ doesn’t imply ‘doing’."
            ),
            "technical": (
                "Raw knowledge assets plus vector store artifacts. Keep ingestion deterministic and track provenance of sources."
            ),
        },
        "tour_readme": {
            "laymen": "This is the single-page explanation of what Eve is, how to run her, and what ‘green’ means.",
            "technical": "Top-level run/ops notes; start here if something is broken and you need the shortest path to a fix.",
        },
        "tour_sop": {
            "laymen": (
                "This is the operating methodology: how Eve stays safe, run-ready, and improvable. "
                "It is designed so a new operator can execute the system without needing code literacy."
            ),
            "technical": (
                "A repo-wide SOP: phases, gates, evidence paths, and change management. "
                "This is the runbook you evolve as the system grows."
            ),
        },
        "tour_architecture": {
            "laymen": "A human-readable map of the system: what parts exist and how information flows between them.",
            "technical": "Subsystem boundaries, responsibilities, and execution/data flow notes.",
        },
        "tour_runtime": {
            "laymen": "The ‘brain’: turns inputs into next actions while staying within constraints.",
            "technical": "Runtime modules: orchestration, policy enforcement, guardrails, and task execution.",
        },
        "tour_workflows": {
            "laymen": "The ‘hands’: automations that touch the outside world through controlled connectors.",
            "technical": "n8n workflow JSON plus deployment and patch tooling; secrets must be env/vars bound.",
        },
        "tour_business_code": {
            "laymen": "The playbooks: what outcomes we’re optimizing for and why.",
            "technical": "Strategy, prompts, and operational logic (human-facing, but still part of the system).",
        },
        "tour_contracts": {
            "laymen": "Guardrails that prevent regressions and keep the system run-ready.",
            "technical": "Contract tests and invariants that acceptance gates depend on.",
        },
        "tour_acceptance_runner": {
            "laymen": "The go/no-go switch: run this before letting Eve execute real commands.",
            "technical": "Orchestrates acceptance IDs; outputs evidence and preserves last-green baselines.",
        },
        "tour_templates": {
            "laymen": "Canonical rules and templates so every workspace stays aligned with Eve’s identity.",
            "technical": "Workspace template + symlink invariants for policy/identity docs.",
        },
    }

    story = story_overrides.get(topic_key) or {}
    lede = story.get(aud) or overview or "No overview available yet."

    # Add CPOM-safe CTAs for key operational topics.
    if topic_key in {"identity_constraints", "acceptance_gates", "ops_deploy", "tour_sop"}:
        extra = [
            {"label": "Open SOP", "href": "/sop"},
            {"label": "Run readiness gates (Dashboard)", "href": "/"},
        ]
        # Ensure these CTAs are visible even if the node has no links configured.
        pretty_links = extra + (pretty_links or [])

    actions = ""
    if pretty_links:
        actions = "<div class='ux-actions'>" + "".join(
            f"<a href='{html.escape(x.get('href') or '')}'>{html.escape(x.get('label') or '')}</a>" for x in pretty_links
        ) + "</div>"

    # Generic topic UX
    uiux_html = (
        f"<div class='ux-lede'>{html.escape(lede)}</div>"
        "<div class='ux-callout'><b>CPOM-safe view:</b> This page is designed to communicate vision and safety boundaries without requiring code literacy.</div>"
        + actions
        + "<h3>Key Artifacts</h3>"
        + (
            "<ul>"
            + "".join(f"<li>{html.escape(x.get('label') or '')}</li>" for x in code_links)
            + "</ul>"
            if code_links
            else "<div class='muted'>No links configured.</div>"
        )
    )
    code_html = (
        "<div class='ux-callout'><b>Code view:</b> Direct file/directory links.</div>"
        + (
            "<div class='ux-actions'>"
            + "".join(
                f"<a href='{html.escape(x.get('href') or '')}'>{html.escape(x.get('label') or '')}</a>" for x in code_links
            )
            + "</div>"
            if code_links
            else ""
        )
        + (
            "<ul>"
            + "".join(
                f"<li><a href='{html.escape(x.get('href') or '')}'>{html.escape(x.get('label') or '')}</a></li>"
                for x in code_links
            )
            + "</ul>"
            if code_links
            else "<div class='muted'>No links configured.</div>"
        )
    )
    return {
        "ok": True,
        "topic": topic,
        "title": title,
        "audience": aud,
        "uiux_html": uiux_html,
        "code_html": code_html,
        "code_links": code_links,
    }


class Handler(BaseHTTPRequestHandler):
    log_requests: bool = True

    def _send(
        self,
        code: int,
        body: bytes,
        content_type: str,
        *,
        cache_control: str = "no-store",
        etag: Optional[str] = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_page(
        self, code: int, title: str, message: str, *, details: str = "", actions: Optional[List[Tuple[str, str]]] = None
    ) -> None:
        body = _error_page(title, message, details=details, actions=actions)
        self._send(code, body, "text/html; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/ping":
            payload = {
                "ok": True,
                "git_head": _git(["rev-parse", "HEAD"]) or None,
                "build": SERVER_BUILD,
                "pid": os.getpid(),
            }
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")
        if parsed.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")

        if parsed.path == "/api/health":
            qs = parse_qs(parsed.query)
            deep = (qs.get("deep", ["0"])[0] == "1")
            cached = (qs.get("cached", ["0"])[0] == "1")
            strict = (qs.get("strict", ["0"])[0] == "1")
            bundle = (qs.get("bundle", [""])[0] or "").strip()

            bundle_key = _bundle_key(bundle, deep=deep) if bundle != "full" else "deep"
            if cached:
                cached_payload = _load_cached(bundle_key)
                if cached_payload is not None:
                    body = json.dumps(cached_payload, ensure_ascii=True).encode("utf-8")
                    return self._send(200, body, "application/json; charset=utf-8")
                if strict:
                    # Strict cached mode: never fall back to running checks.
                    payload = {
                        "ok": False,
                        "error": "no_cached_snapshot",
                        "summary": {
                            "ok": None,
                            "deep": bool(deep),
                            "bundle": bundle_key,
                            "generated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                            "duration_ms": 0,
                            "pass_count": 0,
                            "fail_count": 0,
                            "total_count": 0,
                            "git_head": _git(["rev-parse", "HEAD"]) or None,
                            "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]) or None,
                            "git_dirty": _git_dirty(),
                        },
                        "checks": [],
                        "git": _git_info(last_green_head=None),
                    }
                    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                    return self._send(200, body, "application/json; charset=utf-8")

            data = run_checks(deep=deep, bundle=bundle)
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/delta":
            qs = parse_qs(parsed.query)
            bundle = (qs.get("bundle", [""])[0] or "").strip()
            data = compute_delta(bundle=bundle)
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/ux":
            qs = parse_qs(parsed.query)
            topic = (qs.get("topic", [""])[0] or "").strip()
            audience = (qs.get("audience", ["laymen"])[0] or "").strip()
            if not topic:
                return self._send(400, b'{"ok":false,"error":"missing topic"}', "application/json; charset=utf-8")
            data = build_ux_payload(topic=topic, audience=audience)
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/repo":
            data = repo_overview()
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/fs":
            qs = parse_qs(parsed.query)
            rel = unquote((qs.get("path", [""])[0] or "").strip())
            data = fs_list(rel=rel)
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/suggest":
            qs = parse_qs(parsed.query)
            q = unquote((qs.get("q", [""])[0] or "").strip())
            out = _suggest_paths(q, limit=12)
            body = json.dumps({"ok": True, "paths": out}, ensure_ascii=True).encode("utf-8")
            return self._send(200, body, "application/json; charset=utf-8")

        if parsed.path == "/api/open":
            qs = parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            rel = unquote(rel)
            target = _safe_join(ROOT, rel)
            if not target:
                return self._send_error_page(
                    400,
                    "Bad Path",
                    "The requested path is not allowed (path traversal blocked).",
                    details=f"path={rel}",
                )
            # Directory listing (technical/raw view).
            if target.is_dir():
                rel_dir = str(target.relative_to(ROOT))
                # Render a classic "Index of ..." page for builder-mode, but include a
                # prominent CPOM-safe entrypoint.
                try:
                    entries = sorted(
                        list(target.iterdir()),
                        key=lambda p: (0 if p.is_dir() else 1, p.name.lower()),
                    )
                except Exception as e:
                    return self._send_error_page(
                        500,
                        "Index Error",
                        "Failed to list that directory.",
                        details=f"path={rel} error={e}",
                    )

                def href_for(child: Path) -> str:
                    child_rel = str(child.relative_to(ROOT))
                    return "/api/open?path=" + quote(child_rel)

                items: List[str] = []
                # Parent link (unless at repo root).
                if rel_dir not in ("", "."):
                    parent_rel = str(Path(rel_dir).parent)
                    if parent_rel == ".":
                        parent_rel = ""
                    items.append(
                        f"<li><a href='{html.escape('/api/open?path=' + quote(parent_rel))}'>..</a></li>"
                    )

                for p in entries:
                    child_rel = str(p.relative_to(ROOT))
                    name = p.name + ("/" if p.is_dir() else "")
                    raw_href = href_for(p)
                    if p.is_dir():
                        ux_item = "/open?path=" + quote(child_rel)
                    else:
                        ux_item = "/doc?path=" + quote(child_rel)
                    items.append(
                        "<li>"
                        f"<a href='{html.escape(raw_href)}'>{html.escape(name)}</a>"
                        f" <span class='muted'>(<a href='{html.escape(ux_item)}'>UI/UX</a>)</span>"
                        "</li>"
                    )

                ux_href = "/open?path=" + quote(rel_dir)
                body = (
                    "<!doctype html><html><head><meta charset='utf-8'/>"
                    "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                    "<title>Index</title>"
                    "<style>"
                    "body{font-family:ui-serif,Georgia,Times,serif;margin:32px;max-width:1100px}"
                    "h1{font-size:22px;margin:0 0 12px 0}"
                    ".bar{display:flex;gap:10px;align-items:center;margin:0 0 16px 0;flex-wrap:wrap}"
                    ".btn{display:inline-block;padding:6px 10px;border:1px solid #ddd;border-radius:10px;text-decoration:none;color:#111}"
                    ".btn:hover{background:#f5f5f5}"
                    ".muted{color:#666;font-size:12px}"
                    "ul{padding-left:18px}"
                    "</style></head><body>"
                    f"<h1>Index of {html.escape(str(target))}</h1>"
                    "<div class='bar'>"
                    f"<a class='btn' href='{html.escape(ux_href)}'>Open UI/UX Explorer</a>"
                    "<a class='btn' href='/'>Back to Dashboard</a>"
                    "<span class='muted'>Technical index; UI/UX view is CPOM-safe.</span>"
                    "</div>"
                    "<ul>"
                    + "\n".join(items)
                    + "</ul>"
                    "</body></html>"
                ).encode("utf-8")
                return self._send(200, body, "text/html; charset=utf-8")
            # File view (plaintext)
            if target.exists():
                data = target.read_bytes()
                return self._send(200, data, "text/plain; charset=utf-8")
            if target.is_symlink():
                try:
                    link_target = os.readlink(str(target))
                except Exception:
                    link_target = ""
                msg = (
                    "This path is a symlink inside the repo, but its target is missing on this machine.\n\n"
                    f"Repo path: {rel}\n"
                    f"Symlink target: {link_target or '(unknown)'}\n\n"
                    "This is expected if the canonical workspace/state directory has not been initialized.\n"
                    "Fix: create the canonical file at the target location (or re-run the installer/runtime that generates it).\n"
                )
                return self._send(200, msg.encode("utf-8"), "text/plain; charset=utf-8")
            sugg = _suggest_paths(rel, limit=10)
            actions = [("Open Repo Root", "/api/open?path=")]
            for s in sugg:
                actions.append((f"Try: {s}", "/api/open?path=" + quote(s)))
            return self._send_error_page(
                404,
                "Not Found",
                "That file or directory does not exist in this repo. If you recently updated the dashboard, run `eve-dashboard` to restart stale servers.",
                details=f"path={rel}",
                actions=actions,
            )

        # Static assets: serve from dashboard/
        path = parsed.path
        # SPA shell: app routes share one HTML.
        # (Legacy standalone HTML files are kept, but the router is now client-side.)
        norm = path.rstrip("/") or "/"
        if norm in ("/", "/ux", "/deck", "/open", "/doc", "/sop"):
            path = "/index.html"
        asset = _safe_join(DASHBOARD_DIR, path.lstrip("/"))
        if not asset or not asset.exists() or asset.is_dir():
            return self._send_error_page(
                404,
                "Not Found",
                "That dashboard page or asset was not found. If you are seeing this after a recent update, run `eve-dashboard` to restart stale servers.",
                details=f"path={path}",
            )

        ctype = "text/plain; charset=utf-8"
        if asset.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif asset.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif asset.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif asset.suffix == ".mjs":
            ctype = "application/javascript; charset=utf-8"
        elif asset.suffix == ".json":
            ctype = "application/json; charset=utf-8"

        # Cache static assets aggressively (speed on reload), but keep API + shell HTML uncached.
        cacheable = asset.suffix in {".css", ".js", ".mjs", ".json"}
        cache_control = "public, max-age=3600" if cacheable else "no-store"
        etag = None
        if cacheable:
            try:
                st = asset.stat()
                etag = f'W/"{int(st.st_mtime)}-{int(st.st_size)}"'
                inm = (self.headers.get("If-None-Match") or "").strip()
                if inm and etag and inm == etag:
                    return self._send(304, b"", ctype, cache_control=cache_control, etag=etag)
            except Exception:
                etag = None

        return self._send(200, asset.read_bytes(), ctype, cache_control=cache_control, etag=etag)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        if not self.log_requests:
            return
        super().log_message(fmt, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Eve health dashboard server (stdlib-only).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7331)
    parser.add_argument("--port-max", type=int, default=7340, help="If port is busy, try up to this port.")
    parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-request logs.")
    args = parser.parse_args()

    if not DASHBOARD_DIR.exists():
        raise SystemExit(f"dashboard directory missing: {DASHBOARD_DIR}")

    Handler.log_requests = not args.quiet

    # Bind with a small auto-port range to avoid "address already in use" stack traces.
    server: Optional[ThreadingHTTPServer] = None
    chosen_port: Optional[int] = None
    last_err: Optional[Exception] = None
    for port in range(args.port, args.port_max + 1):
        try:
            server = ThreadingHTTPServer((args.host, port), Handler)
            chosen_port = port
            break
        except OSError as e:
            last_err = e
            continue
    if server is None or chosen_port is None:
        raise SystemExit(f"Failed to bind any port in range {args.port}-{args.port_max}: {last_err}")

    open_host = args.host
    if open_host in ("0.0.0.0", "::"):
        open_host = "127.0.0.1"
    url = f"http://{open_host}:{chosen_port}"
    print(f"Eve dashboard: {url}")
    if args.open:
        try:
            webbrowser.open(url, new=1, autoraise=True)
        except Exception:
            # Don't fail startup if browser open is unavailable.
            pass
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
