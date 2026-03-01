#!/usr/bin/env python3
"""
EVE Launch Control Center — Cyber-Luxe Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Premium Streamlit dashboard for orchestrating EVE B2B outbound campaigns.
Wraps MedspaLaunch, preflight checks, CSV import, dogfood scoring,
emergency stop, self-healing loop, and V13.3 emotional prompt on custom LLM.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "runtime"))
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EVE | Launch Control Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS: Cyber-Luxe Theme
# ---------------------------------------------------------------------------
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600;700;800;900&family=JetBrains+Mono:wght@300;400;500;600&display=swap');

:root {
    --eve-black: #050508;
    --eve-dark: #0a0a10;
    --eve-card: rgba(12, 18, 30, 0.65);
    --eve-border: rgba(0, 245, 255, 0.12);
    --eve-teal: #00f5ff;
    --eve-blue: #00b8ff;
    --eve-green: #00ff88;
    --eve-red: #ff3366;
    --eve-yellow: #ffcc00;
    --eve-purple: #8855ff;
    --eve-text: #e0e8f0;
    --eve-muted: #5a6a7a;
    --glass-bg: rgba(8, 14, 25, 0.55);
    --glass-border: rgba(0, 245, 255, 0.08);
}

/* Global canvas */
.stApp {
    background: var(--eve-black) !important;
    color: var(--eve-text) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Animated particle background */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    background:
        radial-gradient(ellipse at 15% 20%, rgba(0, 245, 255, 0.03) 0%, transparent 50%),
        radial-gradient(ellipse at 85% 80%, rgba(0, 184, 255, 0.02) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 50%, rgba(136, 85, 255, 0.015) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
    animation: nebulaDrift 30s ease-in-out infinite alternate;
}

@keyframes nebulaDrift {
    0% { opacity: 0.7; filter: hue-rotate(0deg); }
    50% { opacity: 1; filter: hue-rotate(8deg); }
    100% { opacity: 0.7; filter: hue-rotate(-5deg); }
}

/* Neural grid overlay */
.stApp::after {
    content: '';
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    background-image:
        linear-gradient(rgba(0, 245, 255, 0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 245, 255, 0.015) 1px, transparent 1px);
    background-size: 80px 80px;
    pointer-events: none;
    z-index: 0;
    animation: gridPulse 8s ease-in-out infinite;
}

@keyframes gridPulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 0.6; }
}

/* Hide Streamlit chrome */
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding-top: 1.5rem !important; max-width: 1600px !important; }

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(5, 5, 12, 0.97) 0%, rgba(8, 14, 28, 0.95) 100%) !important;
    border-right: 1px solid var(--glass-border) !important;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--eve-teal) !important;
    font-weight: 300 !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    font-size: 13px !important;
}

/* Glassmorphic cards */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow:
        0 4px 30px rgba(0, 0, 0, 0.4),
        inset 0 0 30px rgba(0, 245, 255, 0.01);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}
.glass-card:hover {
    border-color: rgba(0, 245, 255, 0.2);
    box-shadow:
        0 8px 40px rgba(0, 0, 0, 0.5),
        inset 0 0 40px rgba(0, 245, 255, 0.02),
        0 0 20px rgba(0, 245, 255, 0.05);
    transform: translateY(-1px);
}
.glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--eve-teal), transparent);
    opacity: 0.3;
}

/* Header */
.eve-header {
    text-align: center;
    padding: 20px 0 10px;
    position: relative;
}
.eve-header h1 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 100 !important;
    font-size: 42px !important;
    letter-spacing: 18px !important;
    color: #fff !important;
    text-shadow: 0 0 40px rgba(0, 245, 255, 0.3), 0 0 80px rgba(0, 184, 255, 0.1);
    margin: 0 !important;
    line-height: 1.2 !important;
}
.eve-subtitle {
    font-size: 11px;
    letter-spacing: 6px;
    text-transform: uppercase;
    color: var(--eve-muted);
    margin-top: 4px;
}
.eve-version {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--eve-teal);
    opacity: 0.6;
    letter-spacing: 2px;
}

/* Status rings */
.status-ring {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 48px; height: 48px;
    border-radius: 50%;
    font-size: 20px;
    position: relative;
    margin: 0 auto;
}
.status-ring.green {
    background: radial-gradient(circle, rgba(0, 255, 136, 0.15) 0%, transparent 70%);
    box-shadow: 0 0 20px rgba(0, 255, 136, 0.2), 0 0 40px rgba(0, 255, 136, 0.05);
    animation: pulseGreen 2s ease-in-out infinite;
}
.status-ring.red {
    background: radial-gradient(circle, rgba(255, 51, 102, 0.15) 0%, transparent 70%);
    box-shadow: 0 0 20px rgba(255, 51, 102, 0.2), 0 0 40px rgba(255, 51, 102, 0.05);
    animation: pulseRed 1.5s ease-in-out infinite;
}
.status-ring.yellow {
    background: radial-gradient(circle, rgba(255, 204, 0, 0.15) 0%, transparent 70%);
    box-shadow: 0 0 20px rgba(255, 204, 0, 0.2), 0 0 40px rgba(255, 204, 0, 0.05);
    animation: pulseYellow 2.5s ease-in-out infinite;
}
.status-ring.unknown {
    background: radial-gradient(circle, rgba(90, 106, 122, 0.15) 0%, transparent 70%);
    box-shadow: 0 0 10px rgba(90, 106, 122, 0.1);
}

@keyframes pulseGreen {
    0%, 100% { box-shadow: 0 0 20px rgba(0, 255, 136, 0.2), 0 0 40px rgba(0, 255, 136, 0.05); }
    50% { box-shadow: 0 0 30px rgba(0, 255, 136, 0.4), 0 0 60px rgba(0, 255, 136, 0.1); }
}
@keyframes pulseRed {
    0%, 100% { box-shadow: 0 0 20px rgba(255, 51, 102, 0.2), 0 0 40px rgba(255, 51, 102, 0.05); }
    50% { box-shadow: 0 0 30px rgba(255, 51, 102, 0.5), 0 0 60px rgba(255, 51, 102, 0.15); }
}
@keyframes pulseYellow {
    0%, 100% { box-shadow: 0 0 20px rgba(255, 204, 0, 0.2), 0 0 40px rgba(255, 204, 0, 0.05); }
    50% { box-shadow: 0 0 30px rgba(255, 204, 0, 0.35), 0 0 50px rgba(255, 204, 0, 0.08); }
}

/* Status label */
.status-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    text-align: center;
    margin-top: 8px;
    opacity: 0.8;
}

/* System Armed badge */
.system-armed {
    display: inline-block;
    padding: 8px 28px;
    background: linear-gradient(135deg, rgba(0, 255, 136, 0.1), rgba(0, 245, 255, 0.1));
    border: 1px solid rgba(0, 255, 136, 0.3);
    border-radius: 30px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 4px;
    color: var(--eve-green);
    text-transform: uppercase;
    animation: armedFloat 3s ease-in-out infinite, armedGlow 2s ease-in-out infinite;
    text-shadow: 0 0 10px rgba(0, 255, 136, 0.4);
    box-shadow: 0 0 30px rgba(0, 255, 136, 0.1), inset 0 0 20px rgba(0, 255, 136, 0.03);
}
@keyframes armedFloat {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-4px); }
}
@keyframes armedGlow {
    0%, 100% { border-color: rgba(0, 255, 136, 0.3); }
    50% { border-color: rgba(0, 255, 136, 0.6); }
}

/* Launch button */
.launch-btn-wrapper {
    text-align: center;
    padding: 20px 0;
}

/* Style Streamlit buttons */
div[data-testid="stButton"] > button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    letter-spacing: 1px !important;
    border-radius: 12px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Concurrency value display */
.concurrency-display {
    font-family: 'JetBrains Mono', monospace;
    font-size: 64px;
    font-weight: 200;
    text-align: center;
    line-height: 1;
    margin: 10px 0;
    transition: color 0.3s ease;
}
.concurrency-display.low { color: var(--eve-yellow); text-shadow: 0 0 30px rgba(255, 204, 0, 0.2); }
.concurrency-display.mid { color: var(--eve-green); text-shadow: 0 0 30px rgba(0, 255, 136, 0.2); }
.concurrency-display.high { color: var(--eve-teal); text-shadow: 0 0 30px rgba(0, 245, 255, 0.3); }
.concurrency-display.max { color: var(--eve-blue); text-shadow: 0 0 40px rgba(0, 184, 255, 0.4); }

/* Slider track */
.stSlider > div > div > div {
    background: linear-gradient(90deg, var(--eve-yellow), var(--eve-green), var(--eve-teal), var(--eve-blue)) !important;
}

/* Log stream */
.log-stream {
    background: rgba(5, 5, 10, 0.8);
    border: 1px solid rgba(0, 245, 255, 0.06);
    border-radius: 12px;
    padding: 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.7;
    max-height: 400px;
    overflow-y: auto;
    color: var(--eve-muted);
}
.log-stream .log-ok { color: var(--eve-green); }
.log-stream .log-err { color: var(--eve-red); }
.log-stream .log-warn { color: var(--eve-yellow); }
.log-stream .log-info { color: var(--eve-teal); }
.log-stream .log-ts { color: rgba(0, 245, 255, 0.3); font-size: 10px; }

/* Section headers */
.section-header {
    font-family: 'Inter', sans-serif;
    font-weight: 200;
    font-size: 14px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--eve-teal);
    margin: 24px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(0, 245, 255, 0.08);
}

/* Metric mini */
.metric-mini {
    text-align: center;
    padding: 12px 8px;
}
.metric-mini .val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 300;
    color: #fff;
}
.metric-mini .lbl {
    font-size: 9px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--eve-muted);
    margin-top: 4px;
}

/* Emergency stop */
.emergency-stop {
    background: linear-gradient(135deg, rgba(255, 51, 102, 0.08), rgba(255, 51, 102, 0.02)) !important;
    border: 1px solid rgba(255, 51, 102, 0.3) !important;
}
.emergency-stop:hover {
    background: linear-gradient(135deg, rgba(255, 51, 102, 0.15), rgba(255, 51, 102, 0.05)) !important;
    box-shadow: 0 0 40px rgba(255, 51, 102, 0.15) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(0, 245, 255, 0.15);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 245, 255, 0.3);
}

/* Selectbox / Input styling */
.stSelectbox, .stTextInput, .stTextArea {
    font-family: 'Inter', sans-serif !important;
}
input, textarea, select {
    background: rgba(8, 14, 25, 0.6) !important;
    border-color: rgba(0, 245, 255, 0.1) !important;
    color: var(--eve-text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important;
}
input:focus, textarea:focus {
    border-color: var(--eve-teal) !important;
    box-shadow: 0 0 15px rgba(0, 245, 255, 0.1) !important;
}

/* Dividers */
hr {
    border-color: rgba(0, 245, 255, 0.06) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: var(--eve-muted) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    padding: 8px 16px !important;
    border: 1px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(0, 245, 255, 0.06) !important;
    color: var(--eve-teal) !important;
    border-color: rgba(0, 245, 255, 0.15) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--eve-teal) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: rgba(8, 14, 25, 0.4) !important;
    border: 1px dashed rgba(0, 245, 255, 0.15) !important;
    border-radius: 12px !important;
    padding: 16px !important;
}

/* Checkbox */
.stCheckbox label span {
    color: var(--eve-text) !important;
    font-size: 13px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: rgba(8, 14, 25, 0.4) !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 1px !important;
    color: var(--eve-teal) !important;
}

/* Toast / Alert boxes */
.stAlert {
    background: rgba(8, 14, 25, 0.5) !important;
    border-radius: 12px !important;
    border-left: 3px solid var(--eve-teal) !important;
}

/* JSON output */
pre {
    background: rgba(5, 5, 10, 0.8) !important;
    border: 1px solid rgba(0, 245, 255, 0.06) !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    color: var(--eve-teal) !important;
}

</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_defaults = {
    "logs": [],
    "preflight_results": {},
    "launch_result": None,
    "self_healing": False,
    "campaign_tag": "medspa_tx_q1_2026",
    "concurrency": 5,
    "launch_profile": "balanced",
    "launch_mode": "manual",
    "emergency_stopped": False,
    "csv_import_result": None,
    "dogfood_result": None,
    "export_data": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _log(msg: str, level: str = "info") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    st.session_state.logs.append({"ts": ts, "msg": msg, "level": level})
    if len(st.session_state.logs) > 500:
        st.session_state.logs = st.session_state.logs[-300:]


def _status_ring(status: str, label: str) -> str:
    icon_map = {"ok": ("✓", "green"), "error": ("✕", "red"), "warn": ("!", "yellow"),
                "skipped": ("—", "unknown"), "unknown": ("?", "unknown"), "missing": ("?", "unknown")}
    icon, css = icon_map.get(status, ("?", "unknown"))
    return (
        f'<div style="text-align:center">'
        f'<div class="status-ring {css}">{icon}</div>'
        f'<div class="status-label">{label}</div>'
        f'</div>'
    )


def _concurrency_class(val: int) -> str:
    if val <= 4:
        return "low"
    if val <= 10:
        return "mid"
    if val <= 15:
        return "high"
    return "max"


# ---------------------------------------------------------------------------
# Backend wrappers (safe import)
# ---------------------------------------------------------------------------
def _get_medspa_launch():
    try:
        from medspa_launch import MedspaLaunch
        return MedspaLaunch()
    except Exception:
        return None


def _run_preflight_check(check_id: str, command: str, kind: str, timeout_s: int) -> Dict[str, Any]:
    try:
        if kind == "shell":
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True, text=True, timeout=timeout_s,
                cwd=str(REPO_ROOT),
                env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            )
        else:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / command)],
                capture_output=True, text=True, timeout=timeout_s,
                cwd=str(REPO_ROOT),
                env={**os.environ, "REPO_ROOT": str(REPO_ROOT)},
            )
        ok = result.returncode == 0
        return {
            "status": "ok" if ok else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"timeout after {timeout_s}s"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _load_checks() -> List[Dict[str, Any]]:
    checks_file = REPO_ROOT / "dashboard" / "checks.json"
    if not checks_file.exists():
        return []
    try:
        data = json.loads(checks_file.read_text(encoding="utf-8"))
        return data.get("checks", [])
    except Exception:
        return []


def _run_dogfood(campaign_tag: str) -> Dict[str, Any]:
    scorecard = REPO_ROOT / "scripts" / "ops" / "prebatch_retell_v133_test.py"
    if not scorecard.exists():
        for alt in [
            REPO_ROOT / "reviews" / "toc-build" / "scripts" / "dogfood_scorecard.py",
            REPO_ROOT / "policies" / "scripts" / "dogfood_scorecard.py",
        ]:
            if alt.exists():
                scorecard = alt
                break
    if not scorecard.exists():
        return {"status": "error", "error": "dogfood script not found"}
    try:
        workflow = REPO_ROOT / "mcp_servers" / "b2b_workflow.yaml"
        args = [sys.executable, str(scorecard), "--workflow", str(workflow)]
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {"status": "ok" if result.returncode == 0 else "error", "output": result.stdout[-2000:]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _import_csv(file_bytes: bytes, filename: str, campaign_tag: str, dry_run: bool) -> Dict[str, Any]:
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(file_bytes)
            csv_path = f.name

        args = [
            sys.executable, str(REPO_ROOT / "scripts" / "import_medspa_csv.py"),
            "--csv", csv_path,
            "--campaign-tag", campaign_tag,
        ]
        if dry_run:
            args.append("--dry-run")

        result = subprocess.run(
            args, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT),
        )
        os.unlink(csv_path)
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-500:],
            }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="eve-header">'
    '<h1>E V E</h1>'
    '<div class="eve-subtitle">Launch Control Center</div>'
    '<div class="eve-version">V13.3 EMOTIONAL RESILIENCE INVERTER &mdash; CUSTOM LLM READY</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# SIDEBAR: Configuration Panel
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="section-header">Mission Config</div>', unsafe_allow_html=True)

    st.session_state.campaign_tag = st.text_input(
        "Campaign Tag",
        value=st.session_state.campaign_tag,
        placeholder="medspa_tx_q1_2026",
    )

    st.session_state.launch_profile = st.selectbox(
        "Launch Profile",
        options=["conservative", "balanced", "aggressive"],
        index=["conservative", "balanced", "aggressive"].index(st.session_state.launch_profile),
    )

    st.session_state.launch_mode = st.selectbox(
        "Dispatch Mode",
        options=["manual", "auto"],
        index=["manual", "auto"].index(st.session_state.launch_mode),
    )

    st.markdown('<div class="section-header">Concurrency</div>', unsafe_allow_html=True)
    st.session_state.concurrency = st.slider(
        "Max Concurrent Calls",
        min_value=1, max_value=20, value=st.session_state.concurrency, step=1,
    )
    cc_class = _concurrency_class(st.session_state.concurrency)
    st.markdown(
        f'<div class="concurrency-display {cc_class}">{st.session_state.concurrency}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-header">Automation</div>', unsafe_allow_html=True)
    st.session_state.self_healing = st.checkbox(
        "Self-Healing Loop",
        value=st.session_state.self_healing,
        help="Continuously monitor preflight and auto-retry failed launches",
    )
    if st.session_state.self_healing:
        st.markdown(
            '<div style="font-size:11px; color: var(--eve-green); letter-spacing: 1px;">'
            '● SELF-HEALING ACTIVE</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-header">CSV Import</div>', unsafe_allow_html=True)
    uploaded_csv = st.file_uploader("Upload Leads CSV", type=["csv"], key="csv_upload")
    csv_dry_run = st.checkbox("Dry Run", value=True, key="csv_dry")
    if uploaded_csv and st.button("Import CSV", key="btn_csv"):
        _log(f"CSV import started: {uploaded_csv.name}", "info")
        result = _import_csv(
            uploaded_csv.getvalue(), uploaded_csv.name,
            st.session_state.campaign_tag, csv_dry_run,
        )
        st.session_state.csv_import_result = result
        _log(f"CSV import result: {result.get('status', 'unknown')}", "ok" if result.get("accepted") else "warn")

    if st.session_state.csv_import_result:
        r = st.session_state.csv_import_result
        with st.expander("CSV Import Result", expanded=False):
            st.json(r)

    st.markdown('<div class="section-header">Export</div>', unsafe_allow_html=True)
    if st.button("Export Session Data", key="btn_export"):
        export = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "campaign_tag": st.session_state.campaign_tag,
            "profile": st.session_state.launch_profile,
            "mode": st.session_state.launch_mode,
            "concurrency": st.session_state.concurrency,
            "preflight": st.session_state.preflight_results,
            "launch_result": st.session_state.launch_result,
            "logs": st.session_state.logs[-100:],
        }
        st.session_state.export_data = json.dumps(export, indent=2, default=str)
        _log("Session data exported", "ok")

    if st.session_state.export_data:
        st.download_button(
            "Download JSON",
            data=st.session_state.export_data,
            file_name=f"eve_launch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="dl_export",
        )


# ---------------------------------------------------------------------------
# MAIN BODY
# ---------------------------------------------------------------------------
tab_mission, tab_preflight, tab_dogfood, tab_logs = st.tabs([
    "Mission Control", "Preflight Systems", "Dogfood QA", "Live Telemetry",
])

# ===================== TAB: MISSION CONTROL =====================
with tab_mission:
    # Preflight summary strip
    st.markdown('<div class="section-header">System Status</div>', unsafe_allow_html=True)

    checks = _load_checks()
    default_checks = [c for c in checks if c.get("default", False)]
    pf = st.session_state.preflight_results

    col_refresh, col_armed = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh Preflight", key="btn_pf_refresh", use_container_width=True):
            _log("Preflight scan initiated...", "info")
            results = {}
            for c in default_checks:
                cid = c["id"]
                _log(f"  Checking: {c['name']}", "info")
                results[cid] = _run_preflight_check(cid, c["command"], c["kind"], c.get("timeout_s", 30))
                results[cid]["name"] = c["name"]
                results[cid]["group"] = c.get("group", "")
                lvl = "ok" if results[cid]["status"] == "ok" else "err"
                _log(f"  {c['name']}: {results[cid]['status']}", lvl)
            st.session_state.preflight_results = results
            _log("Preflight scan complete", "ok")

    all_green = pf and all(v.get("status") == "ok" for v in pf.values())
    with col_armed:
        if all_green:
            st.markdown(
                '<div style="text-align:right; padding-top:4px;">'
                '<span class="system-armed">System Armed</span>'
                '</div>',
                unsafe_allow_html=True,
            )

    if pf:
        ring_cols = st.columns(min(len(pf), 8))
        for i, (cid, result) in enumerate(pf.items()):
            col_idx = i % len(ring_cols)
            with ring_cols[col_idx]:
                short_name = result.get("name", cid).split("(")[0].strip()[:18]
                st.markdown(_status_ring(result["status"], short_name), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="glass-card" style="text-align:center; padding: 40px; opacity: 0.5;">'
            '<div style="font-size: 28px; margin-bottom: 12px;">◇</div>'
            '<div style="font-size: 12px; letter-spacing: 3px; text-transform: uppercase;">Press Refresh to Initialize Preflight</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Launch section
    st.markdown('<div class="section-header">Launch Sequence</div>', unsafe_allow_html=True)

    lcol, rcol = st.columns([2, 1])

    with lcol:
        st.markdown(
            '<div class="glass-card">'
            '<div style="display: flex; justify-content: space-between; align-items: center;">'
            '<div>'
            f'<div style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">Campaign</div>'
            f'<div style="font-size: 22px; font-weight: 300; color: #fff; margin-top: 4px;">{st.session_state.campaign_tag}</div>'
            '</div>'
            '<div style="text-align: right;">'
            f'<div style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">Profile</div>'
            f'<div style="font-size: 18px; font-weight: 300; color: var(--eve-teal); margin-top: 4px;">{st.session_state.launch_profile.upper()}</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Big launch button
        if st.session_state.emergency_stopped:
            st.error("EMERGENCY STOP ACTIVE — All operations halted. Disengage to proceed.")
        else:
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            with btn_col2:
                launch_disabled = not all_green and bool(pf)
                if st.button(
                    "🚀  L A U N C H",
                    key="btn_launch",
                    use_container_width=True,
                    disabled=launch_disabled,
                    type="primary",
                ):
                    _log("=" * 50, "info")
                    _log("LAUNCH SEQUENCE INITIATED", "info")
                    _log(f"Campaign: {st.session_state.campaign_tag}", "info")
                    _log(f"Profile: {st.session_state.launch_profile}", "info")
                    _log(f"Mode: {st.session_state.launch_mode}", "info")
                    _log(f"Concurrency: {st.session_state.concurrency}", "info")

                    launcher = _get_medspa_launch()
                    if launcher:
                        try:
                            from medspa_launch import LAUNCH_PROFILES
                            profile_defaults = LAUNCH_PROFILES.get(
                                st.session_state.launch_profile, {}
                            )
                            payload = {
                                "campaign_tag": st.session_state.campaign_tag,
                                "profile": st.session_state.launch_profile,
                                "mode": st.session_state.launch_mode,
                                "max_calls": st.session_state.concurrency,
                                "canary_size": profile_defaults.get("canary_size", 5),
                                "observation_seconds": profile_defaults.get("observation_seconds", 60),
                            }
                            result = launcher.launch(payload)
                            st.session_state.launch_result = result
                            status = result.get("status", "unknown")
                            _log(f"Launch result: {status}", "ok" if status == "launched" else "err")
                        except Exception as exc:
                            _log(f"Launch error: {exc}", "err")
                            st.session_state.launch_result = {"status": "error", "error": str(exc)}
                    else:
                        _log("MedspaLaunch unavailable (missing env vars). Simulating...", "warn")
                        st.session_state.launch_result = {
                            "status": "simulated",
                            "campaign_tag": st.session_state.campaign_tag,
                            "mode": st.session_state.launch_mode,
                            "profile": st.session_state.launch_profile,
                            "concurrency": st.session_state.concurrency,
                            "note": "Backend not connected. Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, N8N_PUBLIC_WEBHOOK_BASE to enable.",
                        }
                        _log("Simulated launch complete", "warn")

                if launch_disabled and pf:
                    st.caption("Resolve all preflight failures before launching")

    with rcol:
        st.markdown(
            '<div class="glass-card">'
            '<div style="font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted); margin-bottom: 12px;">Quick Actions</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if st.button("🛡 Run Preflight Only", key="btn_pf_only", use_container_width=True):
            launcher = _get_medspa_launch()
            if launcher:
                try:
                    result = launcher.preflight()
                    _log(f"Preflight result: {result.get('overall', 'unknown')}", "ok" if result.get("overall") == "ok" else "err")
                    st.session_state.launch_result = {"preflight_only": result}
                except Exception as exc:
                    _log(f"Preflight error: {exc}", "err")
            else:
                _log("MedspaLaunch unavailable for preflight probe", "warn")

        if st.button("📊 Campaign Status", key="btn_status", use_container_width=True):
            launcher = _get_medspa_launch()
            if launcher:
                try:
                    result = launcher.campaign_status(st.session_state.campaign_tag)
                    st.session_state.launch_result = {"campaign_status": result}
                    _log(f"Campaign: {result.get('lead_count', 0)} leads, {result.get('call_session_count', 0)} calls", "ok")
                except Exception as exc:
                    _log(f"Status error: {exc}", "err")
            else:
                _log("MedspaLaunch unavailable", "warn")

        st.markdown("---")

        emergency = st.button(
            "🛑  EMERGENCY STOP",
            key="btn_estop",
            use_container_width=True,
            type="secondary",
        )
        if emergency:
            st.session_state.emergency_stopped = not st.session_state.emergency_stopped
            state_str = "ENGAGED" if st.session_state.emergency_stopped else "DISENGAGED"
            _log(f"Emergency stop {state_str}", "err" if st.session_state.emergency_stopped else "ok")

    # Launch result display
    if st.session_state.launch_result:
        st.markdown('<div class="section-header">Mission Report</div>', unsafe_allow_html=True)
        with st.expander("Launch / Operation Result", expanded=True):
            st.json(st.session_state.launch_result)


# ===================== TAB: PREFLIGHT SYSTEMS =====================
with tab_preflight:
    st.markdown('<div class="section-header">Preflight Gate Matrix</div>', unsafe_allow_html=True)

    checks = _load_checks()
    if not checks:
        st.info("No preflight checks found in dashboard/checks.json")
    else:
        default_checks = [c for c in checks if c.get("default", False)]
        deep_checks = [c for c in checks if not c.get("default", False)]

        st.markdown(
            '<div class="glass-card">'
            '<div style="font-size: 13px; font-weight: 500; color: var(--eve-teal); margin-bottom: 8px;">Default Gates</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        for c in default_checks:
            cid = c["id"]
            result = st.session_state.preflight_results.get(cid, {})
            status = result.get("status", "unknown")
            icon = {"ok": "✅", "error": "❌", "warn": "⚠️"}.get(status, "◇")

            with st.expander(f"{icon}  {c['name']}  ({c.get('group', '')})", expanded=False):
                st.markdown(f"**Purpose:** {c.get('purpose', {}).get('laymen', 'N/A')}")
                st.markdown(f"**Technical:** `{c.get('purpose', {}).get('technical', 'N/A')}`")
                if result:
                    st.json(result)
                else:
                    st.caption("Not yet evaluated. Press Refresh Preflight in Mission Control.")

                if st.button(f"Run: {c['name']}", key=f"run_{cid}"):
                    _log(f"Running individual check: {c['name']}", "info")
                    r = _run_preflight_check(cid, c["command"], c["kind"], c.get("timeout_s", 30))
                    r["name"] = c["name"]
                    r["group"] = c.get("group", "")
                    st.session_state.preflight_results[cid] = r
                    _log(f"{c['name']}: {r['status']}", "ok" if r["status"] == "ok" else "err")

        if deep_checks:
            st.markdown("---")
            st.markdown(
                '<div class="glass-card">'
                '<div style="font-size: 13px; font-weight: 500; color: var(--eve-purple); margin-bottom: 8px;">Deep / Optional Gates</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            for c in deep_checks:
                cid = c["id"]
                result = st.session_state.preflight_results.get(cid, {})
                status = result.get("status", "unknown")
                icon = {"ok": "✅", "error": "❌", "warn": "⚠️"}.get(status, "◇")
                bundles = ", ".join(c.get("bundles", []))

                with st.expander(f"{icon}  {c['name']}  [{bundles}]", expanded=False):
                    st.markdown(f"**Purpose:** {c.get('purpose', {}).get('laymen', 'N/A')}")
                    if result:
                        st.json(result)
                    if st.button(f"Run: {c['name']}", key=f"run_{cid}"):
                        _log(f"Running deep check: {c['name']}", "info")
                        r = _run_preflight_check(cid, c["command"], c["kind"], c.get("timeout_s", 30))
                        r["name"] = c["name"]
                        r["group"] = c.get("group", "")
                        st.session_state.preflight_results[cid] = r
                        _log(f"{c['name']}: {r['status']}", "ok" if r["status"] == "ok" else "err")


# ===================== TAB: DOGFOOD QA =====================
with tab_dogfood:
    st.markdown('<div class="section-header">V13.3 Prompt Validation</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="glass-card">'
        '<div style="font-size: 13px; color: var(--eve-text);">'
        'Validates the V13.3 Emotional Resilience Inverter prompt (b2b_workflow.yaml) against '
        'contract coverage: flow sections, nuclear keywords, objection handlers, edge cases, and checklist items.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    workflow_path = REPO_ROOT / "mcp_servers" / "b2b_workflow.yaml"
    st.markdown(
        f'<div style="font-size: 11px; font-family: \'JetBrains Mono\', monospace; color: var(--eve-muted);">'
        f'Workflow: {workflow_path}'
        f'{"  ✅  EXISTS" if workflow_path.exists() else "  ❌  MISSING"}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if st.button("Run Dogfood Validation", key="btn_dogfood", use_container_width=True):
        _log("Dogfood V13.3 validation started", "info")
        result = _run_dogfood(st.session_state.campaign_tag)
        st.session_state.dogfood_result = result
        status = result.get("status", "unknown")
        failures = result.get("failures", [])
        _log(f"Dogfood result: {status}, failures: {len(failures)}", "ok" if status == "pass" else "err")

    if st.session_state.dogfood_result:
        dr = st.session_state.dogfood_result
        status = dr.get("status", "unknown")
        failures = dr.get("failures", [])

        col_s, col_f, col_sc = st.columns(3)
        with col_s:
            color = "var(--eve-green)" if status == "pass" else "var(--eve-red)"
            st.markdown(
                f'<div class="metric-mini">'
                f'<div class="val" style="color: {color};">{status.upper()}</div>'
                f'<div class="lbl">Status</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_f:
            st.markdown(
                f'<div class="metric-mini">'
                f'<div class="val">{len(failures)}</div>'
                f'<div class="lbl">Failures</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_sc:
            scenario_count = dr.get("scenario_count", "—")
            st.markdown(
                f'<div class="metric-mini">'
                f'<div class="val">{scenario_count}</div>'
                f'<div class="lbl">Scenarios</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if failures:
            with st.expander(f"Failures ({len(failures)})", expanded=True):
                for f in failures:
                    st.markdown(f"- `{f}`")

        with st.expander("Full Report", expanded=False):
            st.json(dr)

    # V13.3 prompt info
    st.markdown('<div class="section-header">Custom LLM Configuration</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="glass-card">'
        '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">'
        '<div>'
        '<div style="font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">Prompt Version</div>'
        '<div style="font-size: 18px; font-weight: 300; color: var(--eve-teal); margin-top: 4px;">V13.3</div>'
        '</div>'
        '<div>'
        '<div style="font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">Engine</div>'
        '<div style="font-size: 18px; font-weight: 300; color: var(--eve-teal); margin-top: 4px;">Emotional Resilience Inverter</div>'
        '</div>'
        '<div>'
        '<div style="font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">LLM Mode</div>'
        '<div style="font-size: 14px; font-weight: 300; color: var(--eve-text); margin-top: 4px;">Custom LLM (BYOM) + Retell</div>'
        '</div>'
        '<div>'
        '<div style="font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--eve-muted);">Prompt File</div>'
        '<div style="font-size: 11px; font-family: \'JetBrains Mono\', monospace; color: var(--eve-muted); margin-top: 4px;">'
        'mcp_servers/b2b_workflow.yaml'
        '</div>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ===================== TAB: LIVE TELEMETRY =====================
with tab_logs:
    st.markdown('<div class="section-header">Live Telemetry Feed</div>', unsafe_allow_html=True)

    col_clear, col_count = st.columns([1, 3])
    with col_clear:
        if st.button("Clear Logs", key="btn_clear_logs"):
            st.session_state.logs = []
            _log("Telemetry cleared", "info")
    with col_count:
        st.markdown(
            f'<div style="text-align: right; font-family: \'JetBrains Mono\', monospace; '
            f'font-size: 11px; color: var(--eve-muted); padding-top: 8px;">'
            f'{len(st.session_state.logs)} entries</div>',
            unsafe_allow_html=True,
        )

    if st.session_state.logs:
        log_html_lines = []
        for entry in reversed(st.session_state.logs[-200:]):
            css_class = {
                "ok": "log-ok", "err": "log-err",
                "warn": "log-warn", "info": "log-info",
            }.get(entry["level"], "")
            msg = entry["msg"].replace("<", "&lt;").replace(">", "&gt;")
            log_html_lines.append(
                f'<span class="log-ts">[{entry["ts"]}]</span> '
                f'<span class="{css_class}">{msg}</span>'
            )
        log_html = "<br>".join(log_html_lines)
        st.markdown(f'<div class="log-stream">{log_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="log-stream" style="text-align: center; padding: 60px; opacity: 0.3;">'
            'Awaiting telemetry data...'
            '</div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    '<div style="text-align: center; font-size: 10px; letter-spacing: 3px; '
    'text-transform: uppercase; color: var(--eve-muted); padding: 8px 0 20px;">'
    'EVE Launch Control Center &mdash; OpenClaw Runtime &mdash; '
    f'{datetime.now(timezone.utc).strftime("%Y-%m-%d")}'
    '</div>',
    unsafe_allow_html=True,
)
