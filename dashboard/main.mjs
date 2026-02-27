import { fetchJSON } from "./lib/api.mjs";
import { getState, setState, subscribe } from "./lib/state.mjs";
import { initPalette } from "./components/palette.mjs";

import { renderHome } from "./views/home.mjs";
import { renderDeck } from "./views/deck.mjs";
import { renderExplorer } from "./views/explorer.mjs";
import { renderDoc } from "./views/doc.mjs";
import { renderTopic } from "./views/topic.mjs";
import { renderSop } from "./views/sop.mjs";

function qs(id) {
  return document.getElementById(id);
}

function clampAudience(a) {
  return a === "technical" ? "technical" : "laymen";
}

function clampLens(l) {
  if (l === "code") return "code";
  if (l === "split") return "split";
  return "uiux";
}

function normalizePathname(p) {
  const raw = String(p || "");
  if (raw === "") return "/";
  if (raw === "/") return "/";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

function parseRoute() {
  return {
    path: normalizePathname(window.location.pathname),
    q: new URLSearchParams(window.location.search),
    hash: window.location.hash || "",
  };
}

function withViewTransition(fn) {
  try {
    if (document.startViewTransition) {
      document.startViewTransition(() => fn());
      return;
    }
  } catch (_) {
    // ignore
  }
  fn();
}

const root = qs("app-root");
const brandSub = qs("brand-sub");
const runControls = qs("run-controls");
const bundleSel = qs("bundle");

const audLay = qs("aud-laymen");
const audTech = qs("aud-technical");
const lensSeg = qs("lens-seg");
const lensUiux = qs("lens-uiux");
const lensSplit = qs("lens-split");
const lensCode = qs("lens-code");

const runBtn = qs("run");
const refreshBtn = qs("refresh");
const cmdkBtn = qs("cmdk");

if (!root) throw new Error("missing #app-root");

// Cross-route, cross-rerender cache to avoid refetch storms on toggles.
const shared = {
  home: null, // {bundleKey, health, repo, delta, graph, atMs}
  uxByKey: new Map(), // `${audience}:${topic}` -> payload
  fsByPath: new Map(), // `path` -> payload
  textByPath: new Map(), // `path` -> raw text
};

let cleanup = null;
let navSeq = 0;
let chrome = { sub: "", routeKey: "home", showRun: true };

let runAction = null;
let refreshAction = null;
let lastState = getState();
let lastRouteKey = window.location.pathname + window.location.search + window.location.hash;
let lastStableKey = window.location.pathname;

function stableKeyFromLocation() {
  const p = normalizePathname(window.location.pathname);
  const q = new URLSearchParams(window.location.search);
  // Preference params should not force a full remount (prevents scroll reset on toggles).
  q.delete("audience");
  q.delete("lens");
  q.delete("bundle");
  const qs = q.toString();
  return p + (qs ? `?${qs}` : "");
}

function setRunAction(fn) {
  runAction = typeof fn === "function" ? fn : null;
}

function setRefreshAction(fn) {
  refreshAction = typeof fn === "function" ? fn : null;
}

function isActiveFactory(seq) {
  return () => seq === navSeq;
}

function setChrome(next) {
  chrome = { ...chrome, ...(next || {}) };
  if (brandSub) brandSub.textContent = chrome.sub || "";

  // Nav active states.
  const key = chrome.routeKey || "";
  Array.from(document.querySelectorAll("[data-navkey]")).forEach((a) => {
    a.classList.toggle("active", a.getAttribute("data-navkey") === key);
  });

  // Run controls only belong on the dashboard (home).
  if (runControls) runControls.style.display = chrome.showRun ? "inline-flex" : "none";

  // Title
  const suffix = chrome.routeKey && chrome.routeKey !== "home" ? ` • ${chrome.routeKey}` : "";
  document.title = `Eve${suffix}`;
}

function setPointerVars(e) {
  try {
    const x = (e.clientX / Math.max(1, window.innerWidth)) * 100;
    const y = (e.clientY / Math.max(1, window.innerHeight)) * 100;
    document.documentElement.style.setProperty("--mx", `${x.toFixed(2)}%`);
    document.documentElement.style.setProperty("--my", `${y.toFixed(2)}%`);
  } catch (_) {
    // ignore
  }
}

function adoptPrefsFromUrl(route) {
  const qAud = route.q.get("audience");
  const qLens = route.q.get("lens");
  const qBundle = route.q.get("bundle");
  const patch = {};
  if (qAud) patch.audience = clampAudience(qAud);
  if (qLens) patch.lens = clampLens(qLens);
  if (qBundle != null) patch.bundle = String(qBundle || "");
  if (Object.keys(patch).length) setState(patch, { persist: true });
}

function syncUrlPrefs() {
  const st = getState();
  const u = new URL(window.location.href);

  u.searchParams.set("audience", st.audience);
  if (st.lens !== "uiux") u.searchParams.set("lens", st.lens);
  else u.searchParams.delete("lens");

  if (st.bundle) u.searchParams.set("bundle", st.bundle);
  else u.searchParams.delete("bundle");

  // Avoid infinite loops: only replace if changed.
  const next = u.pathname + u.search + u.hash;
  const cur = window.location.pathname + window.location.search + window.location.hash;
  if (next !== cur) window.history.replaceState({}, "", next);
}

function updateToggleUI() {
  const st = getState();
  if (audLay) audLay.classList.toggle("active", st.audience === "laymen");
  if (audTech) audTech.classList.toggle("active", st.audience === "technical");

  // Lens buttons: disabled in laymen mode.
  const lay = st.audience === "laymen";
  if (lensUiux) lensUiux.classList.toggle("active", st.lens === "uiux");
  if (lensSplit) lensSplit.classList.toggle("active", st.lens === "split");
  if (lensCode) lensCode.classList.toggle("active", st.lens === "code");
  if (lensSplit) lensSplit.disabled = lay;
  if (lensCode) lensCode.disabled = lay;

  if (bundleSel) bundleSel.value = st.bundle || "";
  if (lensSeg) lensSeg.style.opacity = lay ? "0.92" : "1";
}

function isAppRoute(path) {
  const p = normalizePathname(path);
  return p === "/" || p === "/deck" || p === "/open" || p === "/doc" || p === "/ux" || p === "/sop";
}

function navigate(href, opts) {
  const o = opts || {};
  const u = new URL(String(href || ""), window.location.href);
  if (u.origin !== window.location.origin) {
    window.location.href = u.toString();
    return;
  }
  if (u.pathname.startsWith("/api/")) {
    window.location.href = u.toString();
    return;
  }

  const next = u.pathname + u.search + u.hash;
  const cur = window.location.pathname + window.location.search + window.location.hash;
  if (next === cur) return;

  if (o.replace) window.history.replaceState({}, "", next);
  else window.history.pushState({}, "", next);

  withViewTransition(() => renderRoute());
}

function interceptLinks() {
  document.addEventListener("click", (e) => {
    const t = e.target;
    const a = t && t.closest ? t.closest("a") : null;
    if (!a) return;
    if (a.target === "_blank" || a.getAttribute("target") === "_blank") return;
    if (a.hasAttribute("download")) return;
    const href = a.getAttribute("href") || "";
    if (!href) return;
    if (href.startsWith("#")) return;
    if (a.getAttribute("rel") && String(a.getAttribute("rel")).includes("external")) return;
    const u = new URL(a.href, window.location.href);
    if (u.origin !== window.location.origin) return;
    if (u.pathname.startsWith("/api/")) return;
    if (!isAppRoute(u.pathname) && !a.hasAttribute("data-nav")) return;
    e.preventDefault();
    navigate(u.pathname + u.search + u.hash);
  });
}

async function refreshPresence() {
  try {
    // Never auto-run checks from the chrome. Strict cached keeps first paint instant.
    const cached = await fetchJSON("/api/health?cached=1&strict=1", { timeoutMs: 900, ttlMs: 600 });
    const ok = cached && cached.summary ? cached.summary.ok : null;
    if (document.body && document.body.dataset) {
      document.body.dataset.health = ok === true ? "good" : ok === false ? "bad" : "unk";
    }
  } catch (_) {
    // ignore
  }
}

async function renderRoute() {
  navSeq += 1;
  const seq = navSeq;
  const isActive = isActiveFactory(seq);

  const route = parseRoute();
  lastRouteKey = window.location.pathname + window.location.search + window.location.hash;
  lastStableKey = stableKeyFromLocation();
  adoptPrefsFromUrl(route);

  if (cleanup) {
    try {
      cleanup();
    } catch (_) {}
    cleanup = null;
  }

  // Basic 404 inside the shell.
  function renderNotFound() {
    setChrome({ sub: "Not Found", routeKey: "", showRun: false });
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Not Found</div>
        <div class="panel-body">
          <div class="callout">
            <b>That page does not exist.</b>
            <div class="muted" style="margin-top:6px">Try the dashboard or explore the repo.</div>
            <div style="height:10px"></div>
            <div class="row">
              <a class="btn btn-primary" href="/" data-nav>Dashboard</a>
              <a class="btn" href="/open?path=" data-nav>Explore</a>
              <a class="btn" href="/deck" data-nav>Deck</a>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  const ctx = {
    root,
    route,
    getState,
    setState,
    setChrome,
    setRunAction,
    setRefreshAction,
    navigate,
    isActive,
    shared,
  };

  try {
    if (route.path === "/") cleanup = await renderHome(ctx);
    else if (route.path === "/deck") cleanup = await renderDeck(ctx);
    else if (route.path === "/open") cleanup = await renderExplorer(ctx);
    else if (route.path === "/doc") cleanup = await renderDoc(ctx);
    else if (route.path === "/ux") cleanup = await renderTopic(ctx);
    else if (route.path === "/sop") cleanup = await renderSop(ctx);
    else renderNotFound();
  } catch (e) {
    if (!isActive()) return;
    setChrome({ sub: "Error", routeKey: "", showRun: false });
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Render Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Something broke while rendering this page.</b>
            <div class="muted" style="margin-top:6px">${String(e && e.message ? e.message : e)}</div>
            <div style="height:10px"></div>
            <button class="btn btn-primary" id="rerender" type="button">Retry</button>
          </div>
        </div>
      </section>
    `;
    const b = qs("rerender");
    if (b) b.addEventListener("click", () => renderRoute());
  }

  // Keep focus stable on navigation.
  try {
    root.focus({ preventScroll: true });
  } catch (_) {}

  syncUrlPrefs();
  updateToggleUI();
  refreshPresence();
}

function bindTopbar() {
  if (audLay) audLay.addEventListener("click", () => setState({ audience: "laymen" }));
  if (audTech) audTech.addEventListener("click", () => setState({ audience: "technical" }));

  if (lensUiux) lensUiux.addEventListener("click", () => setState({ lens: "uiux" }));
  if (lensSplit) lensSplit.addEventListener("click", () => setState({ lens: "split" }));
  if (lensCode) lensCode.addEventListener("click", () => setState({ lens: "code" }));

  if (bundleSel) bundleSel.addEventListener("change", () => setState({ bundle: bundleSel.value || "" }));

  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      if (!runAction) return;
      runBtn.disabled = true;
      const prev = runBtn.textContent;
      runBtn.textContent = "Running…";
      try {
        await runAction();
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = prev || "Run";
      }
    });
  }
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      if (refreshAction) {
        refreshBtn.disabled = true;
        const prev = refreshBtn.textContent;
        refreshBtn.textContent = "Refreshing…";
        try {
          await refreshAction();
        } finally {
          refreshBtn.disabled = false;
          refreshBtn.textContent = prev || "Refresh";
        }
        return;
      }
      renderRoute();
    });
  }

  // Pointer gradient feel.
  window.addEventListener("mousemove", setPointerVars, { passive: true });
}

async function bootPalette() {
  const palette = initPalette({
    onPick: async (it) => {
      if (!it) return;
      if (typeof it.action === "function") {
        await it.action();
        return;
      }
      if (it.href) {
        navigate(it.href);
      }
    },
    onQuery: async (q) => {
      // Query: file/path suggestions (command palette).
      try {
        const data = await fetchJSON(`/api/suggest?q=${encodeURIComponent(q)}`, { timeoutMs: 900 });
        const paths = (data && data.paths) || [];
        return paths.map((p) => ({
          group: "Open",
          title: String(p),
          subtitle: "Open in Doc/Explorer",
          action: async () => navigate(`/doc?path=${encodeURIComponent(String(p))}`),
        }));
      } catch (_) {
        return [];
      }
    },
  });

  if (cmdkBtn) cmdkBtn.addEventListener("click", () => palette.open());

  // Static items
  const base = [
    { group: "Navigate", title: "Dashboard", subtitle: "Health + System Graph", key: "G D", href: "/" },
    { group: "Navigate", title: "Deck", subtitle: "Pitch deck mode", key: "G P", href: "/deck" },
    { group: "Navigate", title: "SOP", subtitle: "Methodology + runbook", key: "G S", href: "/sop" },
    { group: "Navigate", title: "Explore", subtitle: "Repo explorer", key: "G E", href: "/open?path=" },
    {
      group: "Actions",
      title: "Run Checks",
      subtitle: "Run current bundle (Dashboard only)",
      key: "R",
      action: async () => {
        if (window.location.pathname !== "/") navigate("/");
        // Give the dashboard a beat to mount.
        await new Promise((r) => window.setTimeout(r, 60));
        if (runAction) await runAction();
      },
    },
    { group: "Actions", title: "Refresh", subtitle: "Reload sensors", key: "F5", action: async () => (refreshAction ? refreshAction() : renderRoute()) },
    {
      group: "Toggle",
      title: "Audience: Laymen",
      subtitle: "CPOM-safe",
      action: async () => setState({ audience: "laymen" }),
    },
    {
      group: "Toggle",
      title: "Audience: Technical",
      subtitle: "Builder mode",
      action: async () => setState({ audience: "technical" }),
    },
    {
      group: "Toggle",
      title: "Reduced Motion",
      subtitle: "Disable extra motion",
      action: async () => setState({ reducedMotion: !getState().reducedMotion }),
    },
    { group: "Docs", title: "README.md", subtitle: "What Eve is + how to run", href: "/doc?path=README.md" },
    { group: "Docs", title: "SKILLS.md", subtitle: "Connectors and capabilities", href: "/doc?path=SKILLS.md" },
    { group: "Docs", title: "soul.md", subtitle: "Identity substrate", href: "/doc?path=soul.md" },
  ];

  // Topics (from /api/repo)
  try {
    const repo = await fetchJSON("/api/repo", { timeoutMs: 1200, ttlMs: 15000 });
    const topics = (repo && repo.system_map) || [];
    for (const t of topics) {
      base.push({
        group: "Topics",
        title: String(t.name || t.id || ""),
        subtitle: String(((t.desc || {}).laymen || "") || ""),
        href: `/ux?topic=${encodeURIComponent(String(t.id || ""))}`,
      });
    }
  } catch (_) {
    // ignore
  }

  palette.setItems(base);
}

function boot() {
  bindTopbar();
  interceptLinks();

  subscribe(() => {
    const prev = lastState;
    const next = getState();
    lastState = next;

    syncUrlPrefs();
    updateToggleUI();

    // If we're still on the same route and the current view supports an in-place update,
    // prefer that over a full teardown/remount. This keeps toggles feeling instant.
    const curStableKey = stableKeyFromLocation();
    if (curStableKey === lastStableKey && cleanup && typeof cleanup.update === "function" && prev.bundle === next.bundle) {
      withViewTransition(() => {
        try {
          const r = cleanup.update(prev, next);
          if (r && typeof r.then === "function") r.catch(() => {});
        } catch (_) {
          // ignore
        }
      });
      return;
    }

    withViewTransition(() => renderRoute());
  });

  window.addEventListener("popstate", () => renderRoute());

  updateToggleUI();
  setChrome({ sub: "Reality-grounded operations", routeKey: "home", showRun: true });

  bootPalette();
  renderRoute();
  refreshPresence();
  window.setInterval(refreshPresence, 12000);
}

boot();
