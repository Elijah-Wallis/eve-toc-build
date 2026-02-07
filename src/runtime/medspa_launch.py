from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

import requests


ALLOWED_STATUSES = "in.(NEW,NURTURE,RETRY,HOLD)"
SENSITIVE_CONFIG_KEYS = {
    "SUPABASE_SERVICE_ROLE_KEY",
    "RETELL_AI_KEY",
    "TWILIO_AUTH_TOKEN",
    "APIFY_API_TOKEN",
    "N8N_API_KEY",
    "N8N_MCP_TOKEN",
    "N8N_MCP_ACCESS_TOKEN",
    "OPENCLAW_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _in_filter(values: Iterable[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return f"in.({','.join(cleaned)})" if cleaned else "in.()"


class MedspaLaunch:
    """Campaign-scoped launch orchestration with canary gating."""

    def __init__(self) -> None:
        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.n8n_webhook_base = os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", "").rstrip("/")
        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        if not self.n8n_webhook_base:
            raise RuntimeError("N8N_PUBLIC_WEBHOOK_BASE is required")

    def _preflight_overall_spatial(self, overall: str, blockers: List[str]) -> Dict[str, Any]:
        if overall == "ok":
            return {"status": "ok", "color": "GREEN", "meaning": "All launch gates passed."}
        return {
            "status": "error",
            "color": "RED",
            "meaning": "Launch blocked until gates are resolved.",
            "blockers": blockers,
        }

    def _is_preflight_green(self, preflight: Dict[str, Any]) -> bool:
        color = str(((preflight.get("overall_spatial") or {}).get("color") or "")).upper()
        return color == "GREEN" or str(preflight.get("overall") or "").lower() == "ok"

    def launch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        campaign_tag = str(payload.get("campaign_tag") or "").strip()
        if not campaign_tag:
            raise RuntimeError("campaign_tag is required")

        canary_size = int(payload.get("canary_size", 5))
        observation_seconds = int(payload.get("observation_seconds", 60))
        full_dispatch_max_calls = int(payload.get("max_calls", 50))
        if canary_size <= 0:
            raise RuntimeError("canary_size must be >= 1")

        preflight = self._preflight()
        if not self._is_preflight_green(preflight):
            return {
                "status": "blocked",
                "campaign_tag": campaign_tag,
                "reason": "preflight_failed",
                "preflight": preflight,
            }
        candidates = self._fetch_campaign_candidates(campaign_tag)
        if not candidates:
            return {
                "status": "blocked",
                "campaign_tag": campaign_tag,
                "reason": "no_eligible_leads",
                "preflight": preflight,
            }

        canary_ids = [row["id"] for row in candidates[:canary_size]]
        canary_lead_count = len(canary_ids)

        # Canary enforcement: pause full campaign, then unpause canary IDs only.
        pause_until = _iso(_now_utc() + timedelta(hours=12))
        self._patch_leads(
            filters={"source": f"eq.{campaign_tag}"},
            patch={"paused_until": pause_until},
        )
        self._patch_leads(filters={"id": _in_filter(canary_ids)}, patch={"paused_until": None})

        canary_started_at = _now_utc()
        canary_dispatch = self._trigger_n8n(
            "openclaw-retell-dispatch",
            {
                "campaign_tag": campaign_tag,
                "lead_limit": canary_lead_count,
                "max_calls": canary_lead_count,
                "source_filter": campaign_tag,
            },
        )
        time.sleep(max(1, observation_seconds))
        canary_assessment = self._assess_canary(campaign_tag, canary_ids, canary_started_at, canary_lead_count)

        if not canary_assessment["pass"]:
            return {
                "status": "blocked",
                "campaign_tag": campaign_tag,
                "reason": "canary_failed",
                "preflight": preflight,
                "canary_dispatch": canary_dispatch,
                "canary": canary_assessment,
            }

        # Full ramp: unpause campaign and run dispatch + nurture.
        self._patch_leads(
            filters={"source": f"eq.{campaign_tag}"},
            patch={"paused_until": None},
        )
        full_dispatch = self._trigger_n8n(
            "openclaw-retell-dispatch",
            {
                "campaign_tag": campaign_tag,
                "max_calls": full_dispatch_max_calls,
                "source_filter": campaign_tag,
            },
        )
        nurture = self._trigger_n8n(
            "openclaw-nurture-run",
            {"campaign_tag": campaign_tag, "source_filter": campaign_tag},
        )

        return {
            "status": "launched",
            "campaign_tag": campaign_tag,
            "preflight": preflight,
            "canary_dispatch": canary_dispatch,
            "canary": canary_assessment,
            "full_dispatch": full_dispatch,
            "nurture": nurture,
            "summary": self.campaign_status(campaign_tag),
        }

    def preflight(self) -> Dict[str, Any]:
        return self._preflight()

    def campaign_status(self, campaign_tag: str) -> Dict[str, Any]:
        leads = self._get(
            "/rest/v1/leads",
            {
                "select": "id,status,phone,source,paused_until,created_at,last_contacted_at",
                "source": f"eq.{campaign_tag}",
                "order": "created_at.asc",
                "limit": "1000",
            },
        )
        ids = [row["id"] for row in leads]
        calls = []
        if ids:
            calls = self._get(
                "/rest/v1/call_sessions",
                {
                    "select": "id,lead_id,retell_call_id,agent_type,outcome,created_at",
                    "lead_id": _in_filter(ids),
                    "order": "created_at.desc",
                    "limit": "500",
                },
            )
        stoplist = self._get("/rest/v1/stoplist", {"select": "phone"})
        stopset = {s.get("phone") for s in stoplist}
        call_lead_ids = {c.get("lead_id") for c in calls if c.get("lead_id")}
        called_leads = [l for l in leads if l.get("id") in call_lead_ids]
        violations = [l.get("phone") for l in called_leads if l.get("phone") in stopset]

        by_status: Dict[str, int] = {}
        for row in leads:
            key = str(row.get("status") or "UNKNOWN")
            by_status[key] = by_status.get(key, 0) + 1

        by_outcome: Dict[str, int] = {}
        for row in calls:
            key = str(row.get("outcome") or "PENDING")
            by_outcome[key] = by_outcome.get(key, 0) + 1

        return {
            "campaign_tag": campaign_tag,
            "lead_count": len(leads),
            "status_breakdown": by_status,
            "call_session_count": len(calls),
            "outcome_breakdown": by_outcome,
            "stoplist_violations": violations,
        }

    def _preflight(self) -> Dict[str, Any]:
        sup = requests.get(
            f"{self.supabase_url}/rest/v1/tasks?select=id&limit=1",
            headers=self._headers(),
            timeout=15,
        )
        n8n_api_base = os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")
        n8n_api_key = os.environ.get("N8N_API_KEY", "")
        n8n_status = {"status": "missing"}
        if n8n_api_key:
            n8n = requests.get(
                f"{n8n_api_base}/workflows",
                headers={"X-N8N-API-KEY": n8n_api_key},
                timeout=15,
            )
            n8n_status = {"status": "ok" if n8n.status_code == 200 else "error", "code": n8n.status_code}

        twilio_from = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
        twilio_sms = {
            "status": "ok" if twilio_from else "warn",
            "message": "TWILIO_FROM_NUMBER set" if twilio_from else "TWILIO_FROM_NUMBER missing; SMS nurture disabled",
        }

        env_expression_runtime = self._probe_n8n_env_expression_runtime()
        secret_guard = self._check_n8n_workflow_secret_hygiene(n8n_api_base, n8n_api_key)
        if env_expression_runtime.get("status") == "ok":
            guardrail_probe = self._probe_retell_guardrail_workflows()
        else:
            guardrail_probe = {
                "status": "skipped",
                "reason": "blocked_by_n8n_env_expression_runtime",
            }
        blockers = []
        if (sup.status_code != 200) or (n8n_status.get("status") != "ok"):
            blockers.append("core_connectivity")
        if env_expression_runtime.get("status") != "ok":
            blockers.append("n8n_env_expression_runtime")
        if secret_guard.get("status") == "error":
            blockers.append("secret_hygiene")
        if guardrail_probe.get("status") == "error":
            blockers.append("guardrail_workflows")
        overall = "ok" if not blockers else "error"

        return {
            "overall": overall,
            "overall_spatial": self._preflight_overall_spatial(overall, blockers),
            "blockers": blockers,
            "supabase": {"status": "ok" if sup.status_code == 200 else "error", "code": sup.status_code},
            "n8n_api": n8n_status,
            "n8n_env_expression_runtime": env_expression_runtime,
            "secret_hygiene": secret_guard,
            "guardrail_probe": guardrail_probe,
            "twilio_sms": twilio_sms,
            "n8n_webhook_base": self.n8n_webhook_base,
        }

    def _check_n8n_workflow_secret_hygiene(self, n8n_api_base: str, n8n_api_key: str) -> Dict[str, Any]:
        if not n8n_api_key:
            return {"status": "unknown", "message": "N8N_API_KEY missing"}

        allow_literal = os.environ.get("OPENCLAW_ALLOW_LITERAL_WORKFLOW_SECRETS", "0") == "1"
        headers = {"X-N8N-API-KEY": n8n_api_key, "Accept": "application/json"}
        try:
            rows = requests.get(f"{n8n_api_base}/workflows", headers=headers, timeout=20).json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            return {"status": "unknown", "message": f"scan_failed:{type(exc).__name__}"}

        findings: List[Dict[str, str]] = []
        for row in rows:
            wid = row.get("id")
            name = str(row.get("name") or "")
            if not wid or not name.startswith("openclaw_"):
                continue
            try:
                detail = requests.get(f"{n8n_api_base}/workflows/{wid}", headers=headers, timeout=20).json()
            except Exception:  # noqa: BLE001
                continue
            workflow = detail.get("data", detail)
            for node in workflow.get("nodes", []):
                if node.get("type") != "n8n-nodes-base.set" or node.get("name") != "Config":
                    continue
                strings = (((node.get("parameters") or {}).get("values") or {}).get("string") or [])
                for entry in strings:
                    key = str(entry.get("name") or "")
                    if key not in SENSITIVE_CONFIG_KEYS:
                        continue
                    value = str(entry.get("value") or "")
                    if not (value.startswith("={{$env.") or value.startswith("={{$vars.")):
                        findings.append({"workflow": name, "key": key})

        if findings and not allow_literal:
            return {
                "status": "error",
                "message": "literal secrets detected in workflow Config nodes",
                "finding_count": len(findings),
                "sample": findings[:10],
            }
        if findings and allow_literal:
            return {
                "status": "warn",
                "message": "literal secrets present but bypass enabled",
                "finding_count": len(findings),
                "sample": findings[:10],
            }
        return {"status": "ok", "finding_count": 0}

    def _probe_n8n_env_expression_runtime(self) -> Dict[str, Any]:
        """
        Detect whether n8n workflow runtime can execute Config-bound expressions.
        This uses low-impact, idempotent payloads against guardrail tool workflows.
        """
        probe_lead_id = self._sample_probe_lead_id()
        if not probe_lead_id:
            return {"status": "unknown", "reason": "no_probe_lead_id"}
        date_key = _now_utc().date().isoformat()
        probes = [
            {
                "workflow": "openclaw-retell-fn-log-insight",
                "payload": {
                    "lead_id": probe_lead_id,
                    "notes": "env_runtime_probe",
                    "idempotency_key": f"{probe_lead_id}-env-runtime-{date_key}",
                },
                "expect_status": "logged",
            },
            {
                "workflow": "openclaw-retell-fn-set-followup",
                "payload": {
                    "lead_id": probe_lead_id,
                    "status": "NURTURE",
                    "next_touch_at": _iso(_now_utc() + timedelta(days=3)),
                },
                "expect_status": "updated",
            },
        ]
        results: List[Dict[str, Any]] = []
        failures: List[str] = []
        env_block_hits = 0
        for probe in probes:
            workflow = str(probe["workflow"])
            try:
                res = self._post_webhook(workflow, probe["payload"], timeout=30)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{workflow}:transport_error")
                results.append({"workflow": workflow, "status": "error", "error": str(exc)})
                continue

            status_code = int(res.get("status_code") or 0)
            body = res.get("body")
            observed = str(body.get("status") or "").lower() if isinstance(body, dict) else ""
            expected = str(probe["expect_status"]).lower()
            if observed == expected:
                results.append({"workflow": workflow, "status": "ok", "observed": observed})
                continue

            workflow_error = (
                status_code >= 500
                and isinstance(body, dict)
                and str(body.get("message") or "").lower() == "error in workflow"
            )
            if workflow_error:
                env_block_hits += 1
                results.append(
                    {
                        "workflow": workflow,
                        "status": "error",
                        "error": "workflow_error",
                        "status_code": status_code,
                    }
                )
                continue

            failures.append(f"{workflow}:unexpected_response")
            results.append(
                {
                    "workflow": workflow,
                    "status": "error",
                    "status_code": status_code,
                    "response": body,
                }
            )

        if env_block_hits > 0:
            return {
                "status": "error",
                "reason": "n8n_env_expression_blocked",
                "message": (
                    "n8n runtime is blocking $env expressions in workflow nodes. "
                    "On n8n Cloud, switch these bindings to literal Config values or credentials, "
                    "or move to self-hosted n8n if you need runtime env access."
                ),
                "workflow_error_hits": env_block_hits,
                "results": results,
            }
        if failures:
            return {"status": "error", "reason": "probe_failed", "failures": failures, "results": results}
        return {"status": "ok", "results": results}

    def _probe_retell_guardrail_workflows(self) -> Dict[str, Any]:
        probe_lead_id = self._sample_probe_lead_id()
        if not probe_lead_id:
            return {"status": "unknown", "reason": "no_probe_lead_id"}
        date_key = _now_utc().date().isoformat()
        probes = [
            {
                "workflow": "openclaw-retell-fn-log-insight",
                "payload": {
                    "lead_id": probe_lead_id,
                    "notes": "guardrail_probe",
                    "idempotency_key": f"{probe_lead_id}-guardrail-probe-{date_key}",
                },
                "expect_status": "logged",
            },
            {
                "workflow": "openclaw-retell-fn-set-followup",
                "payload": {
                    "lead_id": probe_lead_id,
                    "status": "NURTURE",
                    "next_touch_at": _iso(_now_utc() + timedelta(days=3)),
                },
                "expect_status": "updated",
            },
        ]
        results: List[Dict[str, Any]] = []
        failures: List[str] = []
        for probe in probes:
            workflow = str(probe["workflow"])
            try:
                res = self._post_webhook(workflow, probe["payload"], timeout=30)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{workflow}:transport_error")
                results.append({"workflow": workflow, "status": "error", "error": str(exc)})
                continue
            status_code = int(res.get("status_code") or 0)
            body = res.get("body")
            if isinstance(body, dict) and str(body.get("status") or "").lower() == str(probe["expect_status"]).lower():
                results.append({"workflow": workflow, "status": "ok"})
                continue
            if status_code >= 500 and isinstance(body, dict) and str(body.get("message") or "").lower() == "error in workflow":
                failures.append(f"{workflow}:workflow_error")
                results.append({"workflow": workflow, "status": "error", "error": "workflow_error"})
                continue
            failures.append(f"{workflow}:unexpected_response")
            results.append({"workflow": workflow, "status": "error", "status_code": status_code, "response": body})

        if failures:
            return {"status": "error", "failures": failures, "results": results}
        return {"status": "ok", "results": results}

    def _sample_probe_lead_id(self) -> str | None:
        try:
            rows = self._get("/rest/v1/leads", {"select": "id", "limit": "1", "order": "created_at.asc"})
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None
        return str(rows[0].get("id") or "") or None

    def _fetch_campaign_candidates(self, campaign_tag: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "/rest/v1/leads",
            {
                "select": "id,source,phone,status,paused_until,touch_count,last_contacted_at,created_at",
                "source": f"eq.{campaign_tag}",
                "status": ALLOWED_STATUSES,
                "phone": "not.is.null",
                "order": "created_at.asc",
                "limit": "1000",
            },
        )
        now = _now_utc()
        eligible: List[Dict[str, Any]] = []
        for row in rows:
            paused_until = row.get("paused_until")
            if paused_until:
                try:
                    if datetime.fromisoformat(paused_until) > now:
                        continue
                except ValueError:
                    pass
            eligible.append(row)
        return eligible

    def _assess_canary(
        self,
        campaign_tag: str,
        canary_ids: List[str],
        started_at: datetime,
        canary_target: int,
    ) -> Dict[str, Any]:
        calls = self._get(
            "/rest/v1/call_sessions",
            {
                "select": "id,lead_id,retell_call_id,outcome,created_at",
                "lead_id": _in_filter(canary_ids),
                "created_at": f"gte.{_iso(started_at)}",
                "order": "created_at.desc",
                "limit": "100",
            },
        )
        stoplist = self._get("/rest/v1/stoplist", {"select": "phone"})
        stopset = {s.get("phone") for s in stoplist}
        canary_leads = self._get(
            "/rest/v1/leads",
            {"select": "id,phone", "id": _in_filter(canary_ids), "limit": "100"},
        )
        lead_phone = {row.get("id"): row.get("phone") for row in canary_leads}
        violations = [lead_phone.get(call.get("lead_id")) for call in calls if lead_phone.get(call.get("lead_id")) in stopset]

        pass_check = len(calls) > 0 and len(calls) <= canary_target and len(violations) == 0
        return {
            "pass": pass_check,
            "target": canary_target,
            "call_sessions": len(calls),
            "stoplist_violations": [v for v in violations if v],
            "campaign_tag": campaign_tag,
        }

    def _trigger_n8n(self, workflow: str, data: Dict[str, Any]) -> Dict[str, Any]:
        res = self._post_webhook(workflow, data, timeout=45)
        if int(res.get("status_code") or 0) >= 400:
            raise RuntimeError(f"n8n webhook failed for {workflow}; status={res.get('status_code')}; url={res.get('url')}")
        return res

    def _post_webhook(self, workflow: str, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        url = f"{self.n8n_webhook_base.rstrip('/')}/{workflow.lstrip('/')}"
        candidates = [url]
        if "/webhook" not in self.n8n_webhook_base:
            candidates.append(f"{self.n8n_webhook_base.rstrip('/')}/webhook/{workflow.lstrip('/')}")
            candidates.append(f"{self.n8n_webhook_base.rstrip('/')}/webhook-test/{workflow.lstrip('/')}")

        errors = []
        for target in candidates:
            try:
                resp = requests.post(target, json=data, timeout=timeout)
                if resp.status_code == 404:
                    errors.append(f"404:{target}")
                    continue
                try:
                    body = resp.json()
                except ValueError:
                    body = {"response": resp.text}
                return {"url": target, "status_code": resp.status_code, "body": body}
            except requests.RequestException as exc:
                errors.append(f"{type(exc).__name__}:{target}")
        raise RuntimeError(f"n8n trigger failed for {workflow}; attempts={errors}")

    def _patch_leads(self, filters: Dict[str, str], patch: Dict[str, Any]) -> None:
        params = "&".join(f"{k}={v}" for k, v in filters.items())
        resp = requests.patch(
            f"{self.supabase_url}/rest/v1/leads?{params}",
            headers=self._headers(),
            json=patch,
            timeout=30,
        )
        resp.raise_for_status()

    def _get(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{self.supabase_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
