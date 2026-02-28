#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests


def n8n_base() -> str:
    return os.environ.get("N8N_API_BASE", "https://elijah-wallis.app.n8n.cloud/api/v1").rstrip("/")


def n8n_webhook_base() -> str:
    return os.environ.get("N8N_PUBLIC_WEBHOOK_BASE", "https://elijah-wallis.app.n8n.cloud").rstrip("/")


def n8n_headers() -> Dict[str, str]:
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        raise RuntimeError("N8N_API_KEY is required")
    return {"X-N8N-API-KEY": key, "Content-Type": "application/json", "Accept": "application/json"}


def list_workflows() -> List[Dict[str, Any]]:
    resp = requests.get(f"{n8n_base()}/workflows", headers=n8n_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_workflow_by_name(name: str) -> Optional[Dict[str, Any]]:
    rows = list_workflows()
    existing = next((row for row in rows if row.get("name") == name), None)
    if not existing:
        return None
    wid = existing.get("id")
    if not wid:
        return None
    detail = requests.get(f"{n8n_base()}/workflows/{wid}", headers=n8n_headers(), timeout=30)
    detail.raise_for_status()
    body = detail.json()
    data = body.get("data", body)
    data["_id"] = wid
    return data


def list_webhook_paths(workflow: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for node in workflow.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.webhook":
            continue
        path = str(((node.get("parameters") or {}).get("path") or "")).strip().lstrip("/")
        if path:
            paths.append(path)
    return sorted(set(paths))


def force_reregister_workflow_webhooks(workflow_id: str) -> Dict[str, Any]:
    headers = n8n_headers()
    deactivate = requests.post(f"{n8n_base()}/workflows/{workflow_id}/deactivate", headers=headers, timeout=30)
    activate = requests.post(f"{n8n_base()}/workflows/{workflow_id}/activate", headers=headers, timeout=30)
    activate.raise_for_status()
    time.sleep(1.0)
    return {
        "workflow_id": workflow_id,
        "deactivate_status_code": deactivate.status_code,
        "activate_status_code": activate.status_code,
    }


def verify_webhook_paths_registered(
    base_webhook_url: str,
    paths: List[str],
    probe_payloads: Dict[str, Dict[str, Any]],
    timeout: int = 20,
    require_2xx: bool = False,
) -> Dict[str, Any]:
    failures: List[str] = []
    results: List[Dict[str, Any]] = []
    for path in paths:
        payload = probe_payloads.get(path, {})
        probe = _probe_webhook_path(base_webhook_url, path, payload, timeout=timeout, require_2xx=require_2xx)
        results.append(probe)
        if probe.get("status") != "ok":
            failures.append(path)
    if failures:
        return {"status": "error", "failures": failures, "results": results}
    return {"status": "ok", "results": results}


def _probe_webhook_path(
    base_webhook_url: str,
    path: str,
    payload: Dict[str, Any],
    timeout: int,
    require_2xx: bool,
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for url in _candidate_urls(base_webhook_url, path):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            body = _parse_body(resp)
            attempts.append({"url": url, "status_code": resp.status_code, "body": body})
            if require_2xx and (200 <= resp.status_code < 300):
                return {"status": "ok", "path": path, "url": url, "status_code": resp.status_code, "attempts": attempts}
            if (not require_2xx) and resp.status_code != 404:
                return {"status": "ok", "path": path, "url": url, "status_code": resp.status_code, "attempts": attempts}
        except requests.RequestException as exc:
            attempts.append({"url": url, "error": f"{type(exc).__name__}:{exc}"})
    return {"status": "error", "path": path, "attempts": attempts}


def _candidate_urls(base_webhook_url: str, path: str) -> List[str]:
    base = str(base_webhook_url or "").rstrip("/")
    clean_path = str(path or "").lstrip("/")
    urls = [f"{base}/{clean_path}"]
    if "/webhook" not in base:
        urls.append(f"{base}/webhook/{clean_path}")
        urls.append(f"{base}/webhook-test/{clean_path}")
    return urls


def _parse_body(resp: requests.Response) -> Dict[str, Any]:
    try:
        body = resp.json()
        if isinstance(body, dict):
            return body
        return {"response": body}
    except ValueError:
        return {"response": resp.text}
