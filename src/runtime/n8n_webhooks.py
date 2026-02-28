from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, List, Optional

import requests


_RECOVERY_COOLDOWN_SECONDS = 60
_LAST_RECOVERY_AT: Dict[str, float] = {}


def build_webhook_candidates(base: str, workflow_path: str) -> List[str]:
    base_clean = str(base or "").rstrip("/")
    wf = str(workflow_path or "").lstrip("/")
    if not base_clean or not wf:
        return []

    candidates = [f"{base_clean}/{wf}"]
    if "/webhook" not in base_clean:
        candidates.append(f"{base_clean}/webhook/{wf}")
        candidates.append(f"{base_clean}/webhook-test/{wf}")
    return candidates


def post_with_auto_heal(
    *,
    webhook_base: str,
    workflow_path: str,
    data: Dict[str, Any],
    timeout: int,
    n8n_api_base: Optional[str] = None,
    n8n_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    candidates = build_webhook_candidates(webhook_base, workflow_path)
    if not candidates:
        raise RuntimeError("invalid webhook target: missing base or workflow path")

    first = _post_candidates(candidates, data, timeout)
    if first.get("result"):
        return first["result"]

    attempts = first["attempts"]
    if not _is_not_registered_404_set(attempts):
        raise RuntimeError(f"n8n trigger failed for {workflow_path}; attempts={_attempts_for_error(attempts)}")

    if not _can_attempt_recovery(workflow_path):
        raise RuntimeError(
            f"n8n trigger failed for {workflow_path}; webhook not registered and recovery cooldown active; "
            f"attempts={_attempts_for_error(attempts)}"
        )

    api_base = (n8n_api_base or os.environ.get("N8N_API_BASE") or "").rstrip("/")
    api_key = n8n_api_key or os.environ.get("N8N_API_KEY", "")
    if not api_base or not api_key:
        raise RuntimeError(
            f"n8n trigger failed for {workflow_path}; webhook not registered and N8N_API_BASE/N8N_API_KEY missing; "
            f"attempts={_attempts_for_error(attempts)}"
        )

    try:
        recovery = _recover_webhook_registration(
            workflow_path=workflow_path,
            n8n_api_base=api_base,
            n8n_api_key=api_key,
            webhook_base=webhook_base,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"n8n trigger failed for {workflow_path}; auto-heal failed:{type(exc).__name__}:{exc}; "
            f"attempts={_attempts_for_error(attempts)}"
        ) from exc

    second = _post_candidates(candidates, data, timeout)
    if second.get("result"):
        result = dict(second["result"])
        result["auto_heal"] = recovery
        result["attempts"] = attempts + second["attempts"]
        return result

    combined_attempts = attempts + second["attempts"]
    raise RuntimeError(
        f"n8n trigger failed for {workflow_path}; still failing after auto-heal; "
        f"recovery={recovery}; attempts={_attempts_for_error(combined_attempts)}"
    )


def _post_candidates(candidates: List[str], data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for target in candidates:
        try:
            resp = requests.post(target, json=data, timeout=timeout)
        except requests.RequestException as exc:
            attempts.append({"url": target, "error": f"{type(exc).__name__}:{exc}"})
            continue

        body = _decode_body(resp)
        attempts.append({"url": target, "status_code": resp.status_code, "body": body})
        if resp.status_code == 404:
            continue
        return {"result": {"url": target, "status_code": resp.status_code, "body": body}, "attempts": attempts}
    return {"result": None, "attempts": attempts}


def _decode_body(resp: requests.Response) -> Dict[str, Any]:
    try:
        body = resp.json()
        if isinstance(body, dict):
            return body
        return {"response": body}
    except ValueError:
        return {"response": resp.text}


def _is_not_registered_404_set(attempts: List[Dict[str, Any]]) -> bool:
    if not attempts:
        return False
    for attempt in attempts:
        if int(attempt.get("status_code") or 0) != 404:
            return False
        if "error" in attempt:
            return False

    joined = " ".join(_attempt_text(a).lower() for a in attempts)
    return "not registered" in joined or "requested webhook" in joined


def _attempt_text(attempt: Dict[str, Any]) -> str:
    body = attempt.get("body")
    if isinstance(body, dict):
        return " ".join(str(v) for v in body.values())
    return str(body or "")


def _attempts_for_error(attempts: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for attempt in attempts:
        if "error" in attempt:
            out.append(f"{attempt['error']}:{attempt.get('url')}")
        else:
            out.append(f"{attempt.get('status_code')}:{attempt.get('url')}")
    return out


def _can_attempt_recovery(workflow_path: str) -> bool:
    now = time.time()
    previous = _LAST_RECOVERY_AT.get(workflow_path)
    if previous and (now - previous) < _RECOVERY_COOLDOWN_SECONDS:
        return False
    _LAST_RECOVERY_AT[workflow_path] = now
    return True


def _recover_webhook_registration(
    *,
    workflow_path: str,
    n8n_api_base: str,
    n8n_api_key: str,
    webhook_base: str,
) -> Dict[str, Any]:
    headers = {"X-N8N-API-KEY": n8n_api_key, "Accept": "application/json"}
    workflow = _find_workflow_by_webhook_path(n8n_api_base, headers, workflow_path)
    if not workflow:
        raise RuntimeError(f"workflow_not_found_for_path:{workflow_path}")

    workflow_id = str(workflow.get("id") or "")
    if not workflow_id:
        raise RuntimeError(f"workflow_id_missing_for_path:{workflow_path}")

    patched_webhook_id = _ensure_webhook_id(
        n8n_api_base=n8n_api_base,
        headers=headers,
        workflow_id=workflow_id,
        workflow_path=workflow_path,
    )

    deactivate = requests.post(f"{n8n_api_base}/workflows/{workflow_id}/deactivate", headers=headers, timeout=30)
    activate = requests.post(f"{n8n_api_base}/workflows/{workflow_id}/activate", headers=headers, timeout=30)
    activate.raise_for_status()

    time.sleep(1.0)
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow.get("name"),
        "webhook_path": workflow_path,
        "webhook_base": webhook_base,
        "webhook_id_patched": patched_webhook_id,
        "deactivate_code": deactivate.status_code,
        "activate_code": activate.status_code,
    }


def _find_workflow_by_webhook_path(n8n_api_base: str, headers: Dict[str, str], workflow_path: str) -> Optional[Dict[str, Any]]:
    resp = requests.get(f"{n8n_api_base}/workflows", headers=headers, timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("data", [])

    for row in rows:
        wid = row.get("id")
        if not wid:
            continue
        detail_resp = requests.get(f"{n8n_api_base}/workflows/{wid}", headers=headers, timeout=30)
        detail_resp.raise_for_status()
        detail = detail_resp.json()
        workflow = detail.get("data", detail)
        for node in workflow.get("nodes", []):
            if node.get("type") != "n8n-nodes-base.webhook":
                continue
            path = str(((node.get("parameters") or {}).get("path") or "")).strip().lstrip("/")
            if path == workflow_path.lstrip("/"):
                return {"id": wid, "name": workflow.get("name")}
    return None


def _ensure_webhook_id(
    *,
    n8n_api_base: str,
    headers: Dict[str, str],
    workflow_id: str,
    workflow_path: str,
) -> bool:
    detail_resp = requests.get(f"{n8n_api_base}/workflows/{workflow_id}", headers=headers, timeout=30)
    detail_resp.raise_for_status()
    detail = detail_resp.json()
    workflow = detail.get("data", detail)
    nodes = workflow.get("nodes", [])
    changed = False
    clean_path = workflow_path.lstrip("/")
    for node in nodes:
        if node.get("type") != "n8n-nodes-base.webhook":
            continue
        path = str(((node.get("parameters") or {}).get("path") or "")).strip().lstrip("/")
        if path != clean_path:
            continue
        if node.get("webhookId"):
            return False
        node["webhookId"] = hashlib.md5(clean_path.encode("utf-8")).hexdigest().upper()
        changed = True

    if not changed:
        return False

    raw_settings = workflow.get("settings") or {}
    allowed_settings = {
        "timezone",
        "saveExecutionProgress",
        "saveManualExecutions",
        "callerPolicy",
        "availableInMCP",
        "executionTimeout",
        "errorWorkflow",
    }
    settings = {k: v for k, v in raw_settings.items() if k in allowed_settings}
    payload = {
        "name": workflow.get("name"),
        "nodes": nodes,
        "connections": workflow.get("connections"),
        "settings": settings,
    }
    update_resp = requests.put(
        f"{n8n_api_base}/workflows/{workflow_id}",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    update_resp.raise_for_status()
    return True
