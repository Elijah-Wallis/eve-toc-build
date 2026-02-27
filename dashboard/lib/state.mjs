const STORAGE_KEY = "eve_dashboard_v2_prefs";

function safeJsonParse(s) {
  try {
    return JSON.parse(String(s || ""));
  } catch (_) {
    return null;
  }
}

function clampAudience(a) {
  return a === "technical" ? "technical" : "laymen";
}

function clampLens(l) {
  if (l === "code") return "code";
  if (l === "split") return "split";
  return "uiux";
}

function clampBundle(b) {
  return (b == null ? "" : String(b)).trim();
}

function clampBool(v) {
  return v === true;
}

function prefersReducedMotion() {
  try {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  } catch (_) {
    return false;
  }
}

function clampState(next) {
  const out = {
    audience: clampAudience(next.audience),
    lens: clampLens(next.lens),
    bundle: clampBundle(next.bundle),
    reducedMotion: clampBool(next.reducedMotion),
  };

  // CPOM separation: Laymen can only be in the Vision lens.
  if (out.audience === "laymen") out.lens = "uiux";
  return out;
}

function loadInitial() {
  const base = { audience: "laymen", lens: "uiux", bundle: "", reducedMotion: prefersReducedMotion() };
  try {
    const raw = window.localStorage ? window.localStorage.getItem(STORAGE_KEY) : "";
    const obj = safeJsonParse(raw);
    if (!obj || typeof obj !== "object") return base;
    return clampState({ ...base, ...obj });
  } catch (_) {
    return base;
  }
}

let state = loadInitial();
const listeners = new Set();

function persist() {
  try {
    if (!window.localStorage) return;
    const payload = { audience: state.audience, lens: state.lens, bundle: state.bundle, reducedMotion: state.reducedMotion };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (_) {
    // best-effort
  }
}

export function getState() {
  return state;
}

export function setState(patch, opts) {
  const o = opts || {};
  const next = clampState({ ...state, ...(patch || {}) });
  const changed =
    next.audience !== state.audience ||
    next.lens !== state.lens ||
    next.bundle !== state.bundle ||
    next.reducedMotion !== state.reducedMotion;
  state = next;
  if (o.persist !== false) persist();
  if (changed) listeners.forEach((fn) => fn(state));
  return state;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

