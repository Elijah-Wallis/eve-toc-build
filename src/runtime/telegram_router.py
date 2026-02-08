from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src.runtime.runtime_paths import resolve_repo_root
from src.runtime.runtime_paths import resolve_state_dir
from src.runtime.runtime_paths import state_path

from .context_store import ContextStore
from .config_adapter import resolve_telemetry_path
from .medspa_launch import MedspaLaunch
from .registry_defaults import build_registry
from .task_engine import TaskEngine
from .telemetry import Telemetry


class TelegramRouter:
    """Routes Telegram commands into tasks and graph executions."""
    DAILY_LABEL = "com.openclaw.elijah_evebot_daily"
    WEEKLY_LABEL = "com.openclaw.elijah_evebot_weekly_deep"

    def __init__(self) -> None:
        self.registry = build_registry()
        self.telemetry = Telemetry(str(resolve_telemetry_path()))
        self.engine = TaskEngine(self.registry, telemetry=self.telemetry)
        self.context = ContextStore()
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.n8n_api_base = os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1")
        self.n8n_api_key = os.environ.get("N8N_API_KEY", "")

    def handle(self, text: str) -> Any:
        command_id = f"cmd-{uuid.uuid4().hex[:12]}"
        self.telemetry.set_context(command_id=command_id, correlation_id=command_id)
        parts = text.strip().split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if cmd == "/runpack":
                workflow = arg.strip()
                if not workflow:
                    return {"status": "error", "message": "workflow required"}
                gate = self._launch_path_gate(workflow)
                if gate is not None:
                    return gate
                cron = self._default_cron_for(workflow)
                job = self._upsert_cron_job(workflow, cron)
                record = self.engine.enqueue("n8n.trigger", {"workflow": workflow, "data": {}})
                status = "scheduled_with_warning" if isinstance(job, dict) and job.get("error") else "scheduled"
                return {
                    "status": status,
                    "cron": cron,
                    "job": self._compact_cron_job(job),
                    "task": self._compact_task_record(record),
                }

            if cmd == "/graph":
                graph = json.loads(arg) if arg else {}
                thread = self.context.create_thread("telegram")
                payload = {"graph": graph, "context": {}, "thread_name": "telegram"}
                self.context.append_event(thread["id"], "telegram_graph_request", payload)
                record = self.engine.enqueue("graph.run", payload)
                return {"status": "queued", "thread_id": thread["id"], "task": self._compact_task_record(record)}

            if cmd == "/tasks":
                tasks = self._recent_task_runs()
                return {"tasks": [self._compact_task_run(item) for item in tasks], "count": len(tasks)}

            if cmd == "/launch-medspa":
                try:
                    payload = self._parse_launch_command_args(arg)
                except ValueError as exc:
                    return {"status": "error", "message": str(exc)}
                task = self.engine.enqueue("medspa.launch", payload)
                return {
                    "status": "queued",
                    "campaign_tag": payload["campaign_tag"],
                    "mode": payload.get("mode", "manual"),
                    "profile": payload.get("profile", "balanced"),
                    "overrides": {
                        k: v
                        for k, v in payload.items()
                        if k in {"canary_size", "max_calls", "observation_seconds"}
                    },
                    "task": self._compact_task_record(task),
                }

            if cmd == "/launch-medspa-approve":
                try:
                    payload = self._parse_ramp_approve_args(arg)
                except ValueError as exc:
                    return {"status": "error", "message": str(exc)}
                task = self.engine.enqueue("medspa.ramp", payload)
                return {
                    "status": "queued",
                    "campaign_tag": payload["campaign_tag"],
                    "profile": payload.get("profile", "balanced"),
                    "overrides": {
                        k: v
                        for k, v in payload.items()
                        if k in {"max_calls", "min_recent_canary_calls", "canary_lookback_hours"}
                    },
                    "task": self._compact_task_record(task),
                }

            if cmd == "/launch-medspa-status":
                campaign_tag = arg.strip()
                if not campaign_tag:
                    return {
                        "status": "error",
                        "message": "campaign tag required, e.g. /launch-medspa-status tx-medspa-2026-02-07",
                    }
                launcher = MedspaLaunch()
                summary = launcher.campaign_status(campaign_tag)
                return {"status": "ok", "summary": self._compact_campaign_summary(summary)}

            if cmd == "/evebot_run":
                result = self._run_allowed_command(
                    ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{self.DAILY_LABEL}"],
                    timeout_s=5,
                )
                if result["ok"]:
                    return "Started daily run. Check /evebot_status in ~30–60s."
                return (
                    f"Failed to start daily run (exit {result['code']}): "
                    f"{self._truncate_error(result.get('stderr') or result.get('error') or '')}"
                )

            if cmd == "/evebot_deep":
                plist_path = Path.home() / "Library" / "LaunchAgents" / f"{self.WEEKLY_LABEL}.plist"
                if not plist_path.exists():
                    return "Weekly deep not installed. Run: install_elijah_evebot_launchd.sh --with-weekly-deep"
                result = self._run_allowed_command(
                    ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{self.WEEKLY_LABEL}"],
                    timeout_s=5,
                )
                if result["ok"]:
                    return "Started weekly deep run. Check /evebot_status in ~30–60s."
                return (
                    "Weekly deep is installed but not loaded. Run installer again to bootstrap it: "
                    "install_elijah_evebot_launchd.sh --with-weekly-deep"
                )

            if cmd == "/evebot_status":
                hb_path = resolve_state_dir() / "heartbeat" / "elijah_evebot_heartbeat.json"
                if not hb_path.exists():
                    return "No heartbeat found yet. Send /evebot_run to start."
                try:
                    heartbeat = json.loads(hb_path.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    return f"Heartbeat read failed: {self._truncate_error(str(exc))}"

                counts = heartbeat.get("counts") if isinstance(heartbeat.get("counts"), dict) else {}
                pointers = heartbeat.get("pointers") if isinstance(heartbeat.get("pointers"), dict) else {}
                status = str(heartbeat.get("status") or "unknown")
                repo_commit = str(heartbeat.get("repo_commit") or "unknown")
                finished_at = str(heartbeat.get("finished_at") or "unknown")
                findings = int(counts.get("findings") or 0)
                proposals_generated = int(counts.get("proposals_generated") or 0)
                patches_emitted = int(counts.get("patches_emitted") or 0)
                latest_report_md = str(
                    pointers.get("latest_report_markdown")
                    or pointers.get("report_markdown")
                    or "unknown"
                )
                latest_report_json = str(
                    pointers.get("latest_report_json")
                    or pointers.get("report_json")
                    or "unknown"
                )
                latest_proposals = str(
                    pointers.get("latest_proposals")
                    or pointers.get("proposals_dir")
                    or "unknown"
                )
                return "\n".join(
                    [
                        f"status: {status}",
                        f"repo_commit: {repo_commit}",
                        f"finished_at: {finished_at}",
                        (
                            "counts: "
                            f"findings={findings}, "
                            f"proposals_generated={proposals_generated}, "
                            f"patches_emitted={patches_emitted}"
                        ),
                        f"latest_report_markdown: {latest_report_md}",
                        f"latest_report_json: {latest_report_json}",
                        f"latest_proposals: {latest_proposals}",
                    ]
                )

            if cmd == "/evebot_heartbeat_now":
                args = [
                    sys.executable,
                    "-m",
                    "src.runtime.proactive_review.daily_review",
                    "--mode",
                    "offline",
                    "--profile",
                    "fast",
                    "--heartbeat-only",
                ]
                result = self._run_allowed_command(
                    args,
                    timeout_s=20,
                    cwd=resolve_repo_root(),
                )
                if result["ok"]:
                    return "Heartbeat refreshed. Use /evebot_status."
                return (
                    f"Failed to refresh heartbeat (exit {result['code']}): "
                    f"{self._truncate_error(result.get('stderr') or result.get('error') or '')}"
                )

            if cmd == "/evebot_digest":
                state_dir = resolve_state_dir()
                latest = state_dir / "reports" / "daily" / "LATEST_REPORT.json"
                if not latest.exists():
                    return "No latest report found. Run /evebot_run first, then retry /evebot_digest."
                try:
                    payload = json.loads(latest.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    return f"Failed to read latest report: {self._truncate_error(str(exc))}"

                top = payload.get("top_proposals") if isinstance(payload.get("top_proposals"), list) else []
                top3 = top[:3]
                blockers: List[str] = []
                for item in payload.get("blocked_actions") or []:
                    blockers.append(str(item))
                for item in payload.get("skipped_checks") or []:
                    if isinstance(item, dict):
                        blockers.append(f"{item.get('check')}: {item.get('reason')}")
                    else:
                        blockers.append(str(item))

                apply_order: List[str] = []
                seen: set[str] = set()
                proposal_by_id = {
                    str(item.get("proposal_id")): item for item in top if isinstance(item, dict) and item.get("proposal_id")
                }

                def add_with_deps(proposal_id: str) -> None:
                    if proposal_id in seen:
                        return
                    proposal = proposal_by_id.get(proposal_id, {})
                    for dep in proposal.get("depends_on") or []:
                        dep_id = str(dep)
                        if dep_id in proposal_by_id:
                            add_with_deps(dep_id)
                    seen.add(proposal_id)
                    apply_order.append(proposal_id)

                for item in top3:
                    if isinstance(item, dict) and item.get("proposal_id"):
                        add_with_deps(str(item.get("proposal_id")))

                lines = ["Top 3 proposals:"]
                if top3:
                    for idx, item in enumerate(top3, start=1):
                        pid = str(item.get("proposal_id") or f"proposal-{idx}")
                        title = str(item.get("title") or "Untitled")
                        why = str(item.get("why") or "")[:120]
                        lines.append(f"{idx}. {pid} — {title}")
                        lines.append(f"   why: {why}")
                else:
                    lines.append("- none")

                lines.append("Blockers:")
                if blockers:
                    for blocker in blockers[:5]:
                        lines.append(f"- {blocker}")
                else:
                    lines.append("- none")

                lines.append("Apply order:")
                if apply_order:
                    lines.append("- " + " -> ".join(apply_order))
                else:
                    lines.append("- none")

                return "\n".join(lines)

            if cmd == "/status":
                task_loop_raw = self._task_loop_status()
                supabase = self._supabase_health()
                n8n = self._n8n_health()

                task_loop = dict(task_loop_raw or {})
                # Map last task outcome into the same spatial syntax.
                last_event = (task_loop_raw or {}).get("last_event") or {}
                if last_event:
                    task_loop["last_event"] = self._summarize_last_event(last_event)
                last_task_status = str(last_event.get("status") or "").lower()
                if not last_task_status and task_loop_raw.get("status") == "ok":
                    last_task_status = "idle"
                resolved_last_status = last_task_status or "unknown"
                last_task = {"status": resolved_last_status, **self._decorate(resolved_last_status)}
                if last_task_status:
                    last_task["ts"] = last_event.get("ts")
                    if "error" in last_event:
                        last_task["error"] = last_event.get("error")
                    if "retries" in last_event:
                        last_task["retries"] = last_event.get("retries")

                return {
                    "overall": self._overall_status(task_loop_raw, supabase, n8n),
                    "task_loop": {**task_loop, **self._decorate(task_loop.get("status", "unknown"))},
                    "last_task": last_task,
                    "supabase": {**supabase, **self._decorate(supabase.get("status", "unknown"))},
                    "n8n": {**n8n, **self._decorate(n8n.get("status", "unknown"))},
                }

            return {"status": "unknown_command", "text": text}
        finally:
            self.telemetry.clear_context("correlation_id", "command_id")

    def _is_allowed_command(self, args: List[str]) -> tuple[bool, str]:
        uid = os.getuid()
        daily_args = ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.DAILY_LABEL}"]
        weekly_args = ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.WEEKLY_LABEL}"]
        if args == daily_args or args == weekly_args:
            return True, ""

        heartbeat_tail = [
            "-m",
            "src.runtime.proactive_review.daily_review",
            "--mode",
            "offline",
            "--profile",
            "fast",
            "--heartbeat-only",
        ]
        if len(args) == 1 + len(heartbeat_tail) and args[1:] == heartbeat_tail:
            if args[0] == sys.executable or args[0].endswith("python3"):
                return True, ""
            return False, "heartbeat interpreter not allowed"

        return False, "command not allowlisted"

    def _run_allowed_command(self, args: List[str], timeout_s: int, cwd: Optional[Path] = None) -> Dict[str, Any]:
        allowed, reason = self._is_allowed_command(args)
        if not allowed:
            return {"ok": False, "code": 126, "stdout": "", "stderr": "", "error": reason}
        try:
            proc = subprocess.run(
                args,
                cwd=str(cwd) if cwd else None,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            return {
                "ok": proc.returncode == 0,
                "code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "code": 1, "stdout": "", "stderr": "", "error": str(exc)}

    def _truncate_error(self, text: str) -> str:
        clean = " ".join((text or "").strip().split())
        if not clean:
            return "no stderr"
        return clean if len(clean) <= 240 else f"{clean[:237]}..."

    def _default_cron_for(self, workflow: str) -> str:
        defaults = {
            "openclaw-apify-ingest": "0 * * * *",
            "openclaw-retell-dispatch": "10 * * * *",
            "openclaw-nurture-run": "0 10 * * *",
            "openclaw-feedback-nightly": "5 3 * * *",
        }
        return defaults.get(workflow, "0 * * * *")

    def _is_launch_path_workflow(self, workflow: str) -> bool:
        normalized = workflow.strip().lower().replace("_", "-")
        return normalized in {
            "openclaw-retell-dispatch",
            "openclaw-nurture-run",
            "openclaw-retell-postcall-ingest",
            "openclaw-apify-ingest",
        }

    def _launch_path_gate(self, workflow: str) -> Optional[Dict[str, Any]]:
        if not self._is_launch_path_workflow(workflow):
            return None
        try:
            preflight = MedspaLaunch().preflight()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "blocked",
                "reason": "preflight_unavailable",
                "workflow": workflow,
                "error": str(exc),
            }
        preflight_color = str(((preflight.get("overall_spatial") or {}).get("color") or "")).upper()
        if preflight_color == "GREEN" or preflight.get("overall") == "ok":
            return None
        return {
            "status": "blocked",
            "reason": "preflight_failed",
            "workflow": workflow,
            "preflight": preflight,
        }

    def _upsert_cron_job(self, workflow: str, cron: str) -> Dict[str, Any]:
        if not self.supabase_url or not self.supabase_key:
            return {"error": "supabase_missing"}
        job = {
            "name": f"cron:{workflow}",
            "cron": cron,
            "task_type": "n8n.trigger",
            "payload_json": {"workflow": workflow, "data": {}},
            "active": True,
            "updated_at": self._now(),
        }
        headers = self._headers()
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        try:
            resp = requests.post(
                f"{self.supabase_url}/rest/v1/cron_jobs?on_conflict=name",
                headers=headers,
                data=json.dumps(job),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0] if isinstance(data, list) and data else data
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 409:
                return {"error": f"upsert_failed:{exc}"}
            # Last-resort fallback if conflict handling is not accepted by the PostgREST version.
            try:
                patch_headers = self._headers()
                patch_headers["Prefer"] = "return=representation"
                patch = {
                    "cron": cron,
                    "task_type": "n8n.trigger",
                    "payload_json": {"workflow": workflow, "data": {}},
                    "active": True,
                    "updated_at": self._now(),
                }
                patch_resp = requests.patch(
                    f"{self.supabase_url}/rest/v1/cron_jobs?name=eq.{job['name']}",
                    headers=patch_headers,
                    data=json.dumps(patch),
                    timeout=30,
                )
                patch_resp.raise_for_status()
                data = patch_resp.json()
                return data[0] if isinstance(data, list) and data else data
            except requests.RequestException as patch_exc:
                return {"error": f"upsert_conflict:{patch_exc}"}
        except requests.RequestException as exc:
            return {"error": f"upsert_failed:{exc}"}

    def _recent_task_runs(self) -> List[Dict[str, Any]]:
        if not self.supabase_url or not self.supabase_key:
            return []
        try:
            params = {"select": "id,task_id,status,started_at,ended_at,error", "order": "created_at.desc", "limit": "5"}
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/task_runs",
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return []

    def _task_loop_status(self) -> Dict[str, Any]:
        try:
            path = str(state_path("runtime", "telemetry.jsonl"))
            if not os.path.exists(path):
                return {"status": "no_telemetry"}
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return {"status": "empty"}
            last = json.loads(lines[-1])
            return {"status": "ok", "last_event": last}
        except Exception as exc:  # pylint: disable=broad-except
            return {"status": "error", "error": str(exc)}

    def _supabase_health(self) -> Dict[str, Any]:
        if not self.supabase_url or not self.supabase_key:
            return {"status": "missing"}
        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/tasks?select=id&limit=1",
                headers=self._headers(),
                timeout=15,
            )
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
        except requests.RequestException as exc:
            return {"status": "error", "error": f"{type(exc).__name__}:{exc}"}

    def _n8n_health(self) -> Dict[str, Any]:
        if not self.n8n_api_key:
            return {"status": "missing"}
        try:
            resp = requests.get(
                f"{self.n8n_api_base}/workflows",
                headers={"X-N8N-API-KEY": self.n8n_api_key},
                timeout=15,
            )
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
        except requests.RequestException as exc:
            return {"status": "error", "error": f"{type(exc).__name__}:{exc}"}

    def _decorate(self, status: str) -> Dict[str, Any]:
        """
        Spatial mapping for fast scanning:
        - GREEN: healthy / operating normally
        - RED: down / hard failure
        - YELLOW: degraded / unknown / missing signal
        """
        if status in {"ok", "completed"}:
            return {"color": "GREEN", "meaning": "Operating normally."}
        if status == "idle":
            return {"color": "GREEN", "meaning": "Healthy and idle (no recent task execution)."}
        if status in {"running", "queued"}:
            return {"color": "YELLOW", "meaning": "In progress; waiting for completion."}
        if status in {"failed", "error"}:
            return {"color": "RED", "meaning": "Hard failure; intervention required."}
        if status == "missing":
            return {"color": "YELLOW", "meaning": "Not configured or missing credentials."}
        if status in {"no_telemetry", "empty"}:
            return {"color": "YELLOW", "meaning": "No recent telemetry; cannot confirm health."}
        if status == "down":
            return {"color": "RED", "meaning": "Service unreachable / down."}
        return {"color": "YELLOW", "meaning": "Degraded or unknown state."}

    def _summarize_last_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        keep_keys = (
            "event",
            "ts",
            "status",
            "processed",
            "cron_fired",
            "role",
            "runtime_role",
            "correlation_id",
            "ledger_seq",
            "error",
            "retries",
        )
        return {k: event.get(k) for k in keep_keys if k in event}

    def _overall_status(self, task_loop: Dict[str, Any], supabase: Dict[str, Any], n8n: Dict[str, Any]) -> Dict[str, Any]:
        # If dependencies are down, overall is red.
        if supabase.get("status") != "ok" or n8n.get("status") != "ok":
            status = "down"
        else:
            last_event = (task_loop or {}).get("last_event") or {}
            last_task_status = str(last_event.get("status") or "").lower()
            if last_task_status == "failed":
                status = "failed"
            else:
                status = "ok"
        return {"status": status, **self._decorate(status)}

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"}

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _compact_task_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(record, dict):
            return {}
        keep = {
            "id",
            "type",
            "status",
            "scheduled_for",
            "retries",
            "max_retries",
            "created_at",
            "started_at",
            "ended_at",
            "error",
        }
        out = {k: record.get(k) for k in keep if k in record}
        payload = record.get("payload_json")
        if isinstance(payload, dict):
            payload_keep = (
                "campaign_tag",
                "workflow",
                "mode",
                "profile",
                "max_calls",
                "canary_size",
                "observation_seconds",
                "correlation_id",
            )
            preview = {k: payload.get(k) for k in payload_keep if k in payload}
            if preview:
                out["payload_preview"] = preview
        return out

    def _compact_task_run(self, task_run: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(task_run, dict):
            return {}
        keep = ("id", "task_id", "status", "started_at", "ended_at", "error")
        return {k: task_run.get(k) for k in keep if k in task_run}

    def _compact_cron_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(job, dict):
            return {}
        if "error" in job:
            return {"error": job.get("error")}
        keep = ("id", "name", "cron", "active", "updated_at")
        return {k: job.get(k) for k in keep if k in job}

    def _compact_campaign_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        keep = (
            "campaign_tag",
            "status",
            "mode",
            "profile",
            "started_at",
            "updated_at",
            "finished_at",
            "calls_total",
            "calls_completed",
            "calls_failed",
            "canary_passed",
            "ramp_approved",
            "preflight_ok",
            "blocked_reason",
        )
        return {k: summary.get(k) for k in keep if k in summary}

    def _parse_launch_command_args(self, arg: str) -> Dict[str, Any]:
        tokens = shlex.split(arg)
        if not tokens:
            raise ValueError(
                "campaign tag required, e.g. /launch-medspa tx-medspa-2026-02-07 --mode manual --profile balanced"
            )
        payload: Dict[str, Any] = {
            "campaign_tag": tokens[0],
            "mode": "manual",
            "profile": "balanced",
        }
        idx = 1
        while idx < len(tokens):
            flag = tokens[idx]
            if idx + 1 >= len(tokens):
                raise ValueError(f"missing value for {flag}")
            value = tokens[idx + 1]
            if flag == "--mode":
                payload["mode"] = value.strip().lower()
            elif flag == "--profile":
                payload["profile"] = value.strip().lower()
            elif flag == "--canary-size":
                payload["canary_size"] = int(value)
            elif flag == "--max-calls":
                payload["max_calls"] = int(value)
            elif flag == "--observation-seconds":
                payload["observation_seconds"] = int(value)
            else:
                raise ValueError(f"unknown launch option: {flag}")
            idx += 2

        modes = MedspaLaunch.supported_modes()
        profiles = MedspaLaunch.supported_profiles()
        if payload["mode"] not in modes:
            raise ValueError(f"mode must be one of: {', '.join(modes)}")
        if payload["profile"] not in profiles:
            raise ValueError(f"profile must be one of: {', '.join(profiles)}")
        if int(payload.get("canary_size", 1)) <= 0:
            raise ValueError("canary_size must be >= 1")
        if int(payload.get("max_calls", 1)) <= 0:
            raise ValueError("max_calls must be >= 1")
        if int(payload.get("observation_seconds", 1)) <= 0:
            raise ValueError("observation_seconds must be >= 1")
        return payload

    def _parse_ramp_approve_args(self, arg: str) -> Dict[str, Any]:
        tokens = shlex.split(arg)
        if not tokens:
            raise ValueError(
                "campaign tag required, e.g. /launch-medspa-approve tx-medspa-2026-02-07 --profile balanced"
            )
        payload: Dict[str, Any] = {
            "campaign_tag": tokens[0],
            "profile": "balanced",
        }
        idx = 1
        while idx < len(tokens):
            flag = tokens[idx]
            if idx + 1 >= len(tokens):
                raise ValueError(f"missing value for {flag}")
            value = tokens[idx + 1]
            if flag == "--profile":
                payload["profile"] = value.strip().lower()
            elif flag == "--max-calls":
                payload["max_calls"] = int(value)
            elif flag == "--min-recent-canary-calls":
                payload["min_recent_canary_calls"] = int(value)
            elif flag == "--canary-lookback-hours":
                payload["canary_lookback_hours"] = int(value)
            else:
                raise ValueError(f"unknown ramp option: {flag}")
            idx += 2

        profiles = MedspaLaunch.supported_profiles()
        if payload["profile"] not in profiles:
            raise ValueError(f"profile must be one of: {', '.join(profiles)}")
        if int(payload.get("max_calls", 1)) <= 0:
            raise ValueError("max_calls must be >= 1")
        if int(payload.get("min_recent_canary_calls", 1)) <= 0:
            raise ValueError("min_recent_canary_calls must be >= 1")
        if int(payload.get("canary_lookback_hours", 1)) <= 0:
            raise ValueError("canary_lookback_hours must be >= 1")
        return payload
