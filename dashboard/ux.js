/* global window, document, fetch */

function qs(sel) {
  return document.querySelector(sel);
}
function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function installPointerGlow() {
  if (!window.requestAnimationFrame) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  let mx = 50;
  let my = 18;
  let raf = null;
  function commit() {
    raf = null;
    const root = document.documentElement;
    root.style.setProperty("--mx", `${mx.toFixed(2)}%`);
    root.style.setProperty("--my", `${my.toFixed(2)}%`);
  }
  window.addEventListener(
    "mousemove",
    (e) => {
      const w = window.innerWidth || 1;
      const h = window.innerHeight || 1;
      mx = clamp((e.clientX / w) * 100, 0, 100);
      my = clamp((e.clientY / h) * 100, 0, 100);
      if (raf == null) raf = window.requestAnimationFrame(commit);
    },
    { passive: true }
  );
}

function parseQuery() {
  const u = new URL(window.location.href);
  return {
    topic: u.searchParams.get("topic") || "capabilities_skills",
    audience: u.searchParams.get("audience") || "laymen",
    tab: u.searchParams.get("tab") || ""
  };
}

function setQuery(updates) {
  const u = new URL(window.location.href);
  Object.entries(updates).forEach(([k, v]) => u.searchParams.set(k, v));
  window.history.replaceState({}, "", u.toString());
}

function setActive(groupSelector, key, value) {
  qsa(groupSelector).forEach((b) => b.classList.toggle("active", b.dataset[key] === value));
}

async function loadHealthBadge() {
  try {
    const res = await fetch("/api/health?cached=1", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const ok = data && data.summary ? data.summary.ok : null;
    if (document.body && document.body.dataset) {
      document.body.dataset.health = ok === true ? "good" : ok === false ? "bad" : "unk";
    }
  } catch (_) {
    // best-effort only
  }
}

async function load() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const tabRaw = q.tab || (audience === "technical" ? "code" : "uiux");
  const tab = audience === "laymen" && tabRaw === "code" ? "uiux" : tabRaw;
  qsa(".seg-btn[data-tab]").forEach((b) => {
    if (b.dataset.tab === "code") b.disabled = audience !== "technical";
  });
  setActive(".seg-btn[data-audience]", "audience", audience);
  setActive(".seg-btn[data-tab]", "tab", tab);

  const res = await fetch(`/api/ux?topic=${encodeURIComponent(q.topic)}&audience=${encodeURIComponent(audience)}`, {
    cache: "no-store"
  });
  const data = await res.json();
  if (!data.ok) {
    qs("#title").textContent = "Error";
    qs("#content").textContent = data.error || "Unknown error";
    return;
  }

  qs("#title").textContent = data.title || data.topic || "UX";
  qs("#meta").textContent = `topic=${data.topic} | audience=${data.audience}`;
  qs("#content").innerHTML = tab === "code" ? data.code_html : data.uiux_html;
}

function init() {
  const q = parseQuery();
  installPointerGlow();
  loadHealthBadge().catch(() => {});
  // Bind buttons.
  qsa(".seg-btn[data-audience]").forEach((b) => {
    b.addEventListener("click", async () => {
      setQuery({ audience: b.dataset.audience, tab: parseQuery().tab });
      await load();
    });
  });
  qsa(".seg-btn[data-tab]").forEach((b) => {
    b.addEventListener("click", async () => {
      const cur = parseQuery();
      if ((cur.audience || "laymen") !== "technical" && b.dataset.tab === "code") {
        setQuery({ tab: "code", audience: "technical" });
      } else {
        setQuery({ tab: b.dataset.tab, audience: cur.audience });
      }
      await load();
    });
  });

  // Default tabs by audience: laymen -> uiux, technical -> code.
  if (!q.tab) setQuery({ tab: q.audience === "technical" ? "code" : "uiux" });

  load().catch((e) => {
    qs("#title").textContent = "Error";
    qs("#content").textContent = e.message;
  });
}

document.addEventListener("DOMContentLoaded", init);
