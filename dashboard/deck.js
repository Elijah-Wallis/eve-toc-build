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

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function parseQuery() {
  const u = new URL(window.location.href);
  return {
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

async function fetchUx(topic, audience) {
  const res = await fetch(`/api/ux?topic=${encodeURIComponent(topic)}&audience=${encodeURIComponent(audience)}`, {
    cache: "no-store"
  });
  if (!res.ok) throw new Error(`ux fetch failed: ${res.status}`);
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "ux error");
  return data;
}

function mkRailLink(id, title, subtitle) {
  return `
    <a class="rail-link" href="#s-${safeText(id)}" data-target="s-${safeText(id)}">
      <div class="t">${safeText(title)}</div>
      <div class="s">${safeText(subtitle || "")}</div>
    </a>
  `;
}

function mkSlide(id, title, tag, htmlBody, actionsHtml) {
  return `
    <div class="slide reveal" id="s-${safeText(id)}" data-id="${safeText(id)}">
      <div class="slide-title-row">
        <h2 class="slide-title">${safeText(title)}</h2>
        <div class="slide-tag">${safeText(tag || "")}</div>
      </div>
      <div class="slide-body">${htmlBody || ""}</div>
      <div class="slide-actions">${actionsHtml || ""}</div>
    </div>
  `;
}

function bindSmoothRail() {
  qsa(".rail-link").forEach((a) => {
    a.addEventListener("click", (e) => {
      const href = a.getAttribute("href") || "";
      if (!href.startsWith("#")) return;
      e.preventDefault();
      const el = document.querySelector(href);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState({}, "", href);
    });
  });
}

function installRevealObserver() {
  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add("on");
      });
    },
    { threshold: 0.15 }
  );
  qsa(".reveal").forEach((el) => obs.observe(el));
}

function installActiveSectionObserver() {
  const links = qsa(".rail-link");
  const byTarget = {};
  links.forEach((l) => {
    const t = l.dataset.target;
    if (t) byTarget[t] = l;
  });
  const obs = new IntersectionObserver(
    (entries) => {
      // Pick the most visible intersecting slide.
      const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => (b.intersectionRatio || 0) - (a.intersectionRatio || 0));
      if (!visible.length) return;
      const id = visible[0].target.id;
      links.forEach((l) => l.classList.toggle("active", l.dataset.target === id));
    },
    { threshold: [0.2, 0.35, 0.5, 0.65] }
  );
  qsa(".slide").forEach((s) => obs.observe(s));
}

function scrollToSibling(dir) {
  const slides = qsa(".slide");
  if (!slides.length) return;
  const y = window.scrollY + 120;
  const idx = slides.findIndex((s) => s.getBoundingClientRect().top + window.scrollY >= y - 10);
  const cur = idx >= 0 ? idx : slides.length - 1;
  const next = Math.max(0, Math.min(slides.length - 1, cur + dir));
  slides[next].scrollIntoView({ behavior: "smooth", block: "start" });
}

function bindKeys() {
  window.addEventListener("keydown", (e) => {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    if (e.key === "j" || e.key === "ArrowDown") scrollToSibling(1);
    if (e.key === "k" || e.key === "ArrowUp") scrollToSibling(-1);
  });
}

async function load() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const tabRaw = q.tab || (audience === "technical" ? "code" : "uiux");
  const tab = audience === "laymen" && tabRaw === "code" ? "uiux" : tabRaw;

  setActive(".seg-btn[data-audience]", "audience", audience);
  setActive(".seg-btn[data-tab]", "tab", tab);

  const repoRes = await fetch("/api/repo", { cache: "no-store" });
  if (!repoRes.ok) throw new Error(`repo fetch failed: ${repoRes.status}`);
  const repo = await repoRes.json();
  const stats = repo.stats || {};

  const meta = [];
  meta.push(`workflows=${stats.workflows_n8n_json ?? "n/a"} | runtime_py=${stats.runtime_py ?? "n/a"} | contracts=${stats.contracts_py ?? "n/a"}`);
  meta.push(`scripts=${stats.scripts_total ?? "n/a"} | mcp_servers=${stats.mcp_servers_dirs ?? "n/a"} | services=${stats.services_dirs ?? "n/a"}`);
  qs("#hero-meta").textContent = meta.join("\n");

  const tour = (repo.repo_tour || []).filter((x) => x && x.id);
  const sys = (repo.system_map || []).filter((x) => x && x.id);
  const nav = qs("#rail-nav");
  const slidesEl = qs("#slides");
  nav.innerHTML =
    `<div class="rail-group">Repo Tour</div>` +
    tour.map((t) => mkRailLink(t.id, t.name || t.id, tab === "code" ? "Code anchors" : "Vision-first overview")).join("") +
    `<div class="rail-group">System Map</div>` +
    sys.map((t) => mkRailLink(t.id, t.name || t.id, tab === "code" ? "Code anchors" : "Vision-first overview")).join("");

  // Build slides: fetch UX payload per topic to keep narrative consistent with the dashboard.
  const slides = [];
  const chapters = tour.concat(sys);
  for (const t of chapters) {
    const uxAud = tab === "code" ? "technical" : audience;
    const ux = await fetchUx(t.id, uxAud);
    const body = tab === "code" ? ux.code_html : ux.uiux_html;

    const overviewHref = `/ux?topic=${encodeURIComponent(t.id)}&audience=${encodeURIComponent(audience)}&tab=uiux`;
    const codeHref = `/ux?topic=${encodeURIComponent(t.id)}&audience=${encodeURIComponent("technical")}&tab=code`;

    // Only surface raw file anchors in technical context.
    const openLinks =
      tab === "code" || audience === "technical" ? (Array.isArray(ux.code_links) ? ux.code_links.slice(0, 2) : []) : [];
    const extra = openLinks
      .map((l) => `<a class="pill ghost" href="${safeText(l.href || "")}">${safeText(l.label || "Open")}</a>`)
      .join("");

    const actions =
      `<a class="pill" href="${safeText(overviewHref)}">Open Overview</a>` +
      `<a class="pill ghost" href="${safeText(codeHref)}">Open Code</a>` +
      extra;

    slides.push(mkSlide(t.id, t.name || t.id, t.id, body, actions));
  }
  slidesEl.innerHTML = slides.join("");

  bindSmoothRail();
  installRevealObserver();
  installActiveSectionObserver();
  bindKeys();
}

function init() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const tab = q.tab || (audience === "technical" ? "code" : "uiux");
  if (!q.tab) setQuery({ tab, audience });

  installPointerGlow();
  loadHealthBadge().catch(() => {});
  if (audience !== "technical") {
    qsa(".seg-btn[data-tab]").forEach((b) => {
      if (b.dataset.tab === "code") b.disabled = true;
    });
  }

  qsa(".seg-btn[data-audience]").forEach((b) => {
    b.addEventListener("click", async () => {
      setQuery({ audience: b.dataset.audience, tab: parseQuery().tab });
      window.location.reload(); // keeps the deck deterministic (no partial state)
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
      window.location.reload();
    });
  });

  load().catch((e) => {
    qs("#hero-meta").textContent = `Error: ${e.message}`;
  });
}

document.addEventListener("DOMContentLoaded", init);
