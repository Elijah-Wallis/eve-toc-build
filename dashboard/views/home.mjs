import { fetchJSON } from "../lib/api.mjs";
import { mountGraph } from "../components/graph.mjs";

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function statusClass(ok) {
  if (ok === true) return "good";
  if (ok === false) return "bad";
  return "unk";
}

function fmtMs(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n)) return "n/a";
  if (n < 1000) return `${Math.round(n)}ms`;
  return `${(n / 1000).toFixed(2)}s`;
}

function modeText(audience, lens, obj) {
  const aud = audience === "technical" ? "technical" : "laymen";
  if (lens === "uiux") return (obj && (obj.laymen || obj[aud])) || "";
  if (lens === "code") return (obj && (obj.technical || obj[aud])) || "";
  // split: caller decides
  return (obj && (obj.laymen || obj.technical || "")) || "";
}

function computeGroupSummary(checks) {
  const by = {};
  for (const c of checks || []) {
    const g = c.group || "Other";
    if (!by[g]) by[g] = { pass: 0, fail: 0, total: 0 };
    by[g].total += 1;
    if (c.ok === true) by[g].pass += 1;
    else if (c.ok === false) by[g].fail += 1;
  }
  return by;
}

function skeleton() {
  return `
    <section class="hero">
      <div class="hero-left">
        <div class="panel">
          <div class="panel-title">Status</div>
          <div class="panel-body">
            <div class="row">
              <div class="skeleton" style="width:120px;height:30px"></div>
              <div class="skeleton" style="flex:1;height:16px"></div>
            </div>
            <div style="height:12px"></div>
            <div class="kpi-row">
              <div class="kpi skeleton"></div>
              <div class="kpi skeleton"></div>
              <div class="kpi skeleton"></div>
              <div class="kpi skeleton"></div>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">Checks</div>
          <div class="panel-body">
            <div class="skeleton" style="height:150px"></div>
          </div>
        </div>
      </div>
      <div class="hero-right">
        <div class="panel">
          <div class="panel-title">System Map</div>
          <div class="panel-body">
            <div class="skeleton" style="height:240px"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">Repo Tour</div>
          <div class="panel-body">
            <div class="skeleton" style="height:180px"></div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderOverall(health) {
  const s = (health && health.summary) || {};
  const ok = s.ok;
  const cls = statusClass(ok);
  const pillText = ok === true ? "GREEN" : ok === false ? "RED" : "UNKNOWN";
  const meta = s.generated_at_iso ? `Updated: ${s.generated_at_iso}` : "Updated: n/a";
  const fail = s.fail_count != null ? `Failing: ${s.fail_count}` : "";
  const bundle = s.bundle ? `Bundle: ${s.bundle}` : "";
  return `
    <div class="row">
      <span class="pill ${cls}"><span class="dot ${cls}"></span>${safeText(pillText)}</span>
      <div class="muted mono">${safeText([meta, fail, bundle].filter(Boolean).join(" | "))}</div>
    </div>
  `;
}

function renderKpis(health) {
  const s = (health && health.summary) || {};
  const pass = s.pass_count ?? "n/a";
  const total = s.total_count ?? "n/a";
  const fail = s.fail_count ?? "n/a";
  const dur = fmtMs(s.duration_ms);
  const bundle = s.bundle ?? (s.deep ? "deep" : "fast");
  const items = [
    { k: "Passing", v: String(pass), sub: `of ${total}` },
    { k: "Failing", v: String(fail), sub: "needs attention" },
    { k: "Duration", v: dur, sub: "check sweep" },
    { k: "Bundle", v: String(bundle), sub: "selected" },
  ];
  return items
    .map(
      (it) => `
      <div class="kpi">
        <div class="k">${safeText(it.k)}</div>
        <div class="v">${safeText(it.v)}</div>
        <div class="s mono">${safeText(it.sub)}</div>
      </div>`
    )
    .join("");
}

function renderGroups(checks) {
  const by = computeGroupSummary(checks);
  const rows = Object.entries(by).sort((a, b) => a[0].localeCompare(b[0]));
  return rows
    .map(([g, s]) => {
      const label = s.fail > 0 ? "RED" : s.pass === s.total ? "GREEN" : "MIXED";
      const cls = s.fail > 0 ? "bad" : s.pass === s.total ? "good" : "unk";
      return `
        <div class="gcard">
          <div class="t">${safeText(g)}</div>
          <div class="n ${cls}">${safeText(label)}</div>
          <div class="b mono">${safeText(`${s.pass}/${s.total} pass, ${s.fail} fail`)}</div>
        </div>
      `;
    })
    .join("");
}

function renderChecks(audience, lens, checks) {
  const sorted = (checks || []).slice().sort((a, b) => {
    const ao = a.ok === true ? 0 : a.ok === false ? 2 : 1;
    const bo = b.ok === true ? 0 : b.ok === false ? 2 : 1;
    if (ao !== bo) return bo - ao;
    return (a.group || "").localeCompare(b.group || "") || (a.name || "").localeCompare(b.name || "");
  });

  function cols(c) {
    const lay = safeText((c.purpose || {}).laymen || "");
    const tech = safeText((c.purpose || {}).technical || "");
    const fixLay = safeText((c.how_to_fix || {}).laymen || "");
    const fixTech = safeText((c.how_to_fix || {}).technical || "");

    if (lens === "uiux") {
      return `
        <div class="cols">
          <div class="col">
            <div class="h">Purpose</div>
            <div class="p">${lay || "<span class='muted'>(none)</span>"}</div>
          </div>
          <div class="col">
            <div class="h">Fix</div>
            <div class="p">${fixLay || "<span class='muted'>(none)</span>"}</div>
          </div>
        </div>
      `;
    }

    if (lens === "code") {
      const cmd = safeText(c.command || "");
      const out = safeText(c.output || "");
      return `
        <div class="cols">
          <div class="col">
            <div class="h">Purpose</div>
            <div class="p mono">${tech || "<span class='muted'>(none)</span>"}</div>
            <div style="height:8px"></div>
            <div class="h">Fix</div>
            <div class="p mono">${fixTech || "<span class='muted'>(none)</span>"}</div>
          </div>
          <div class="col">
            <div class="h">Command / Output</div>
            <div class="p mono">command: ${cmd || "<span class='muted'>(none)</span>"}\n\noutput:\n${out || "<span class='muted'>(none)</span>"}</div>
          </div>
        </div>
      `;
    }

    // split
    const cmd = safeText(c.command || "");
    const out = safeText(c.output || "");
    return `
      <div class="cols">
        <div class="col">
          <div class="h">Laymen</div>
          <div class="p">${lay || "<span class='muted'>(none)</span>"}</div>
          <div style="height:8px"></div>
          <div class="h">Fix (Laymen)</div>
          <div class="p">${fixLay || "<span class='muted'>(none)</span>"}</div>
        </div>
        <div class="col">
          <div class="h">Technical</div>
          <div class="p mono">${tech || "<span class='muted'>(none)</span>"}</div>
          <div style="height:8px"></div>
          <div class="h">Command</div>
          <div class="p mono">${cmd || "<span class='muted'>(none)</span>"}</div>
        </div>
      </div>
      <div style="height:10px"></div>
      <div class="callout">
        <div class="mono" style="white-space:pre-wrap">${safeText(out || "(no output)")}</div>
      </div>
    `;
  }

  return sorted
    .map((c, idx) => {
      const dot = statusClass(c.ok);
      const title = `${c.name || c.id || "check"}${c.group ? ` (${c.group})` : ""}`;
      const dur = c.duration_ms != null ? fmtMs(c.duration_ms) : "n/a";
      const meta = `${c.id || ""}${c.timeout_s ? ` | timeout=${c.timeout_s}s` : ""} | dur=${dur}`;

      const tools =
        audience === "technical" && lens !== "uiux"
          ? `<div class="ctools">
              <button class="btn btn-quiet mono ccopy" data-kind="cmd" data-idx="${idx}" type="button">Copy cmd</button>
              <button class="btn btn-quiet mono ccopy" data-kind="out" data-idx="${idx}" type="button">Copy out</button>
            </div>`
          : "";

      return `
        <div class="check ${c.ok === false ? "fail" : ""}" data-idx="${idx}">
          <button class="check-head" type="button" data-toggle="${idx}">
            <span class="dot ${dot}"></span>
            <span class="ct">
              <span class="ttl">${safeText(title)}</span>
              <span class="meta mono">${safeText(meta)}</span>
            </span>
            <span class="st mono">${c.ok === true ? "PASS" : c.ok === false ? "FAIL" : "UNK"}</span>
          </button>
          <div class="check-body" id="check-body-${idx}">
            ${cols(c)}
            ${tools}
          </div>
        </div>
      `;
    })
    .join("");
}

export async function renderHome(ctx) {
  const { root, getState, setChrome, setRunAction, setRefreshAction, navigate, isActive, shared } = ctx;
  const st = getState();
  setChrome({ sub: "Health + System Map", routeKey: "home", showRun: true });

  // If we already have a snapshot for this bundle, render immediately (no network)
  // so audience/lens toggles feel instant.
  const st0 = getState();
  const bundle0 = st0.bundle || "";
  const deep0 = bundle0 !== "" && bundle0 !== "full";
  const bundleKey0 = bundle0 ? bundle0.trim().toLowerCase() : deep0 ? "deep" : "fast";
  const hasSnap0 = Boolean(shared && shared.home && shared.home.bundleKey === bundleKey0);
  root.innerHTML = hasSnap0 ? "" : skeleton();

  let lastHealth = null;
  let lastRepo = null;
  let graphCleanup = null;
  let checksForCopy = [];
  let currentPayload = null; // {health,repo,delta,graph}
  let els = { groups: null, checks: null, tour: null };

  function disposeGraph() {
    if (graphCleanup) {
      graphCleanup();
      graphCleanup = null;
    }
  }

  async function copy(text) {
    const t = String(text || "");
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(t);
    const ta = document.createElement("textarea");
    ta.value = t;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  // Event delegation so toggles and copy stay fast across re-renders.
  function onRootClick(e) {
    const t = e.target;
    if (!t || !t.closest) return;

    const ccopy = t.closest(".ccopy");
    if (ccopy) {
      e.preventDefault();
      e.stopPropagation();
      const idx = Number(ccopy.getAttribute("data-idx") || "0");
      const kind = ccopy.getAttribute("data-kind") || "";
      const c = checksForCopy[idx];
      if (!c) return;
      ccopy.disabled = true;
      const prev = ccopy.textContent;
      (async () => {
        try {
          await copy(kind === "cmd" ? c.command || "" : c.output || "");
          ccopy.textContent = "Copied";
          window.setTimeout(() => (ccopy.textContent = prev || (kind === "cmd" ? "Copy cmd" : "Copy out")), 900);
        } finally {
          ccopy.disabled = false;
        }
      })();
      return;
    }

    const toggler = t.closest("[data-toggle]");
    if (toggler) {
      const idx = toggler.getAttribute("data-toggle");
      const el = root.querySelector(`#check-body-${idx}`);
      if (el) el.classList.toggle("open");
      return;
    }

    const runFirst = t.closest("#run-first");
    if (runFirst) {
      e.preventDefault();
      runDeep();
      return;
    }
  }

  root.addEventListener("click", onRootClick);

  function renderSnapshot(payload) {
    const p = payload || {};
    const stNow = getState();
    const health = p.health;
    const repo = p.repo;
    const delta = p.delta;
    const graph = p.graph || { edges: [] };
    currentPayload = { health, repo, delta, graph };

    lastHealth = health;
    lastRepo = repo;
    checksForCopy = (health && health.checks) || [];

    // Presence orb + body health indicator
    const ok = health && health.summary ? health.summary.ok : null;
    if (document.body && document.body.dataset) {
      document.body.dataset.health = ok === true ? "good" : ok === false ? "bad" : "unk";
    }

    // Strict cached miss: show CTA (never auto-run).
    if (health && health.error === "no_cached_snapshot") {
      root.innerHTML = `
        <div class="panel">
          <div class="panel-title">Status</div>
          <div class="panel-body">
            <div class="callout">
              <b>No cached snapshot yet.</b>
              <div class="muted" style="margin-top:6px">This dashboard is instant by default. Click <b>Run</b> to generate the first health snapshot.</div>
              <div style="height:10px"></div>
              <button class="btn btn-primary" id="run-first" type="button">Run</button>
            </div>
          </div>
        </div>
      `;
      return;
    }

    // Render
    const audience = stNow.audience;
    const lens = stNow.lens;

    const rr = (delta && delta.run_ready) || {};
    const rrCls = rr.ok === true ? "good" : rr.ok === false ? "bad" : "unk";
    const rrTxt = rr.ok === true ? "RUN READY" : rr.ok === false ? "NOT READY" : "UNKNOWN";

    const git = (delta && delta.git) || {};
    const gitLine = git.head ? `git: ${(git.branch || "?")}@${String(git.head).slice(0, 8)}${git.dirty ? " (dirty)" : ""}` : "git: n/a";
    const sinceGreen = git.last_green_head ? `since green: ${String(git.last_green_head).slice(0, 8)} -> ${String(git.head).slice(0, 8)}` : "";

    const flipToFail = ((delta && delta.check_deltas && delta.check_deltas.flipped_to_fail) || []).slice(0, 10);
    const failingNow = ((delta && delta.check_deltas && delta.check_deltas.failing_now) || []).slice(0, 10);

    const deltaLines = [];
    deltaLines.push(`<span class="pill ${rrCls}"><span class="dot ${rrCls}"></span>${safeText(rrTxt)}</span>`);
    if (rr.last_run_at) deltaLines.push(`<span class="mono muted">${safeText(`last: ${rr.last_run_at}`)}</span>`);
    deltaLines.push(`<div class="mono muted">${safeText(gitLine)}${sinceGreen ? `\n${sinceGreen}` : ""}</div>`);
    if (flipToFail.length) deltaLines.push(`<div class="mono muted">${safeText(`new failures: ${flipToFail.join(", ")}`)}</div>`);
    if (failingNow.length) deltaLines.push(`<div class="mono muted">${safeText(`failing now: ${failingNow.join(", ")}`)}</div>`);

    const sysNodes = (repo && repo.system_map) || [];
    const edges = (graph && graph.edges) || [];

    root.innerHTML = `
      <section class="hero">
        <div class="hero-left">
          <div class="panel">
            <div class="panel-title">Status</div>
            <div class="panel-body">
              ${renderOverall(health)}
              <div style="height:10px"></div>
              <div class="kpi-row">${renderKpis(health)}</div>
              <div style="height:12px"></div>
              <div class="callout">
                <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px">
                  <div>
                    <div style="font-weight:600">Run Ready and Deltas</div>
                    <div class="muted" style="margin-top:4px">Acceptance gates are the go/no-go switch before autonomy.</div>
                  </div>
                  <div class="mono muted">bundle=${safeText((delta && delta.bundle) || "fast")}</div>
                </div>
                <div style="height:10px"></div>
                <div class="delta">${deltaLines.join("<div style='height:8px'></div>")}</div>
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-title">Checks</div>
            <div class="panel-body">
              <div class="groups" id="groups">${renderGroups(health.checks || [])}</div>
              <div style="height:12px"></div>
              <div class="checks" id="checks">${renderChecks(audience, lens, health.checks || [])}</div>
            </div>
          </div>
        </div>

        <div class="hero-right">
          <div class="panel">
            <div class="panel-title">System Graph</div>
            <div class="panel-body">
              <div class="muted">A physics-sim map of major subsystems. Hover to read; click to open.</div>
              <div style="height:10px"></div>
              <div class="graph-wrap" id="graph-wrap"></div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-title">Repo Tour</div>
            <div class="panel-body">
              <div class="tour" id="tour">
                ${((repo && repo.repo_tour) || [])
                  .map((t) => {
                    const href = `/ux?topic=${encodeURIComponent(t.id || "")}`;
                    const desc = modeText(audience, "uiux", t.desc || {});
                    return `<a class="tour-card" href="${safeText(href)}" data-nav>
                      <div class="h">${safeText(t.name || t.id || "")}</div>
                      <div class="p">${safeText(desc || "")}</div>
                      <div class="k mono">${safeText(t.id || "")}</div>
                    </a>`;
                  })
                  .join("")}
              </div>
            </div>
          </div>
        </div>
      </section>
    `;

    els.groups = root.querySelector("#groups");
    els.checks = root.querySelector("#checks");
    els.tour = root.querySelector("#tour");

    disposeGraph();
    const gw = root.querySelector("#graph-wrap");
    if (gw) {
      graphCleanup = mountGraph(gw, {
        nodes: sysNodes,
        edges,
        reducedMotion: stNow.reducedMotion,
        tooltipText: (n) => {
          const stTip = getState();
          const aud = stTip.audience === "technical" ? "technical" : "laymen";
          const d = n && n.desc ? n.desc[aud] || n.desc.laymen || n.desc.technical || "" : "";
          return d;
        },
        onSelect: (n) => navigate(`/ux?topic=${encodeURIComponent(n.id)}`),
      });
    }
  }

  function updateFromState(prev, next) {
    if (!currentPayload) return;
    if (!els.groups || !els.checks || !els.tour) return;

    // If reduced motion toggled, update the mounted graph without remount.
    try {
      if (graphCleanup && typeof graphCleanup.setReducedMotion === "function") {
        graphCleanup.setReducedMotion(next.reducedMotion === true);
      }
      if (graphCleanup && typeof graphCleanup.setTooltipText === "function") {
        graphCleanup.setTooltipText((n) => {
          const aud = next.audience === "technical" ? "technical" : "laymen";
          const d = n && n.desc ? n.desc[aud] || n.desc.laymen || n.desc.technical || "" : "";
          return d;
        });
      }
    } catch (_) {}

    const audience = next.audience;
    const lens = next.lens;
    const checks = (currentPayload.health && currentPayload.health.checks) || [];

    // Preserve open check bodies across updates.
    const open = new Set();
    Array.from(root.querySelectorAll(".check-body.open")).forEach((el) => {
      const id = el.getAttribute("id") || "";
      const m = id.match(/^check-body-(\d+)$/);
      if (m) open.add(Number(m[1]));
    });

    els.groups.innerHTML = renderGroups(checks);
    els.checks.innerHTML = renderChecks(audience, lens, checks);

    // Restore open state.
    open.forEach((idx) => {
      const el = root.querySelector(`#check-body-${idx}`);
      if (el) el.classList.add("open");
    });

    // Repo tour copy changes with audience.
    const tourItems = ((currentPayload.repo && currentPayload.repo.repo_tour) || []).map((t) => {
      const href = `/ux?topic=${encodeURIComponent(t.id || "")}`;
      const desc = modeText(audience, "uiux", t.desc || {});
      return `<a class="tour-card" href="${safeText(href)}" data-nav>
        <div class="h">${safeText(t.name || t.id || "")}</div>
        <div class="p">${safeText(desc || "")}</div>
        <div class="k mono">${safeText(t.id || "")}</div>
      </a>`;
    });
    els.tour.innerHTML = tourItems.join("");
  }

  async function loadAll(opts) {
    const o = opts || {};
    const stNow = getState();
    const bundle = stNow.bundle || "";
    const deep = bundle !== "" && bundle !== "full";
    const timeoutMs = o.deep ? 120000 : 3000;

    const healthUrl =
      "/api/health" +
      (o.cached ? `?cached=1${o.strict ? "&strict=1" : ""}` : "") +
      (bundle ? `${o.cached ? "&" : "?"}bundle=${encodeURIComponent(bundle)}${deep ? "&deep=1" : ""}` : "");

    const [health, repo, delta, graph] = await Promise.all([
      fetchJSON(healthUrl, { timeoutMs, ttlMs: o.cached ? 500 : 0 }),
      fetchJSON("/api/repo", { timeoutMs: 2500, ttlMs: 15000 }),
      fetchJSON(bundle ? `/api/delta?bundle=${encodeURIComponent(bundle)}` : "/api/delta", { timeoutMs: 2500, ttlMs: 2500 }),
      fetchJSON("/graph.json", { timeoutMs: 2500, ttlMs: 60000 }).catch(() => ({ edges: [] })),
    ]);

    if (!isActive()) return;

    // Persist snapshot for instant re-renders (skip strict cache miss).
    try {
      const bk = (health && health.summary && health.summary.bundle) || (deep ? "deep" : "fast");
      if (shared && !(health && health.error === "no_cached_snapshot")) {
        shared.home = { bundleKey: String(bk || ""), health, repo, delta, graph, atMs: Date.now() };
      }
    } catch (_) {}

    renderSnapshot({ health, repo, delta, graph });
  }

  async function runDeep() {
    const bundle = getState().bundle || "";
    const deep = bundle !== "";
    await loadAll({ cached: false, deep });
  }

  setRunAction(async () => runDeep());
  // Refresh is cached-only: keep it instant.
  setRefreshAction(async () => loadAll({ cached: true, strict: true }));

  // Instant-by-default: cached only (strict), never auto-run fresh checks.
  try {
    const stNow = getState();
    const bundleNow = stNow.bundle || "";
    const deepNow = bundleNow !== "" && bundleNow !== "full";
    const wantKey = bundleNow ? bundleNow.trim().toLowerCase() : deepNow ? "deep" : "fast";
    if (shared && shared.home && shared.home.bundleKey === wantKey) {
      renderSnapshot(shared.home);
    } else {
      await loadAll({ cached: true, strict: true });
    }
  } catch (e) {
    if (!isActive()) return () => {};
    root.innerHTML = `
      <div class="panel">
        <div class="panel-title">Dashboard Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load health.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
            <div style="height:10px"></div>
            <button class="btn btn-primary" id="retry" type="button">Retry</button>
          </div>
        </div>
      </div>
    `;
    const r = root.querySelector("#retry");
    if (r) r.addEventListener("click", () => loadAll({ cached: true, strict: true }));
  }

  const cleanup = () => {
    disposeGraph();
    setRunAction(null);
    setRefreshAction(null);
    root.removeEventListener("click", onRootClick);
  };
  cleanup.update = (prev, next) => updateFromState(prev, next);
  return cleanup;
}
