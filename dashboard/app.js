/* global window, document, fetch */

let audience = "laymen"; // laymen | technical | split
let lastHealth = null;
let lastRepo = null;
let lastDelta = null;
let lens = "ux"; // ux | code

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

function installRevealObserver() {
  if (!window.IntersectionObserver) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const els = qsa(".panel, .overall, .delta, .kpi, .group, .check, .node, .repo-card");
  els.forEach((el) => el.classList.add("reveal"));

  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add("on");
      });
    },
    { threshold: 0.12 }
  );
  els.forEach((el) => obs.observe(el));
}

function fmtMs(ms) {
  if (ms == null) return "n/a";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function setAudience(next) {
  audience = next;
  qsa(".seg-btn[data-audience]").forEach((b) => b.classList.toggle("active", b.dataset.audience === next));
  render();
}

function setLens(next) {
  // CPOM separation: code lens implies technical context.
  if (next === "code" && audience === "laymen") {
    setAudience("technical");
  }
  lens = next;
  const uxBtn = qs("#lens-ux");
  const codeBtn = qs("#lens-code");
  if (uxBtn) uxBtn.classList.toggle("active", next === "ux");
  if (codeBtn) codeBtn.classList.toggle("active", next === "code");
  if (window.localStorage) window.localStorage.setItem("eve_dashboard_lens", next);
  render();
}

function statusClass(ok) {
  if (ok === true) return "good";
  if (ok === false) return "bad";
  return "unk";
}

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function modeText(obj) {
  if (!obj) return "";
  if (audience === "laymen") return obj.laymen || "";
  if (audience === "technical") return obj.technical || "";
  // split
  return "";
}

function renderKpis(health) {
  const el = qs("#kpis");
  const p = health.summary || {};
  el.innerHTML = [
    { label: "Passing", val: p.pass_count ?? "n/a", sub: `of ${p.total_count ?? "n/a"}` },
    { label: "Failing", val: p.fail_count ?? "n/a", sub: "needs attention" },
    { label: "Duration", val: fmtMs(p.duration_ms), sub: "check sweep" },
    { label: "Bundle", val: p.bundle ?? (p.deep ? "deep" : "fast"), sub: "select + Run" },
  ]
    .map(
      (k) => `
      <div class="kpi">
        <div class="label">${safeText(k.label)}</div>
        <div class="val">${safeText(k.val)}</div>
        <div class="sub">${safeText(k.sub)}</div>
      </div>`
    )
    .join("");
}

function renderOverall(health) {
  const pill = qs("#overall-pill");
  const meta = qs("#overall-meta");
  const ok = health.summary ? health.summary.ok : null;
  if (document.body && document.body.dataset) {
    document.body.dataset.health = ok === true ? "good" : ok === false ? "bad" : "unk";
  }
  pill.className = `overall-pill ${statusClass(ok)}`;
  pill.textContent = ok === true ? "GREEN" : ok === false ? "RED" : "UNKNOWN";
  meta.textContent = health.summary
    ? `Updated: ${health.summary.generated_at_iso || "n/a"} | Failing: ${health.summary.fail_count || 0}`
    : "Loading...";
}

function renderDelta(delta) {
  const el = qs("#delta-body");
  if (!el) return;
  if (!delta) {
    el.textContent = "No delta data yet.";
    return;
  }
  if (delta.error) {
    el.textContent = `delta error: ${delta.error}`;
    return;
  }

  const bundle = delta.bundle || "";
  const rr = delta.run_ready;
  const rrCls = rr && rr.ok === true ? "good" : rr && rr.ok === false ? "bad" : "unk";
  const rrTxt = rr && rr.ok === true ? "RUN READY" : rr && rr.ok === false ? "NOT READY" : "UNKNOWN";
  const rrMeta = rr ? `bundle=${bundle || "fast"} last=${rr.last_run_at || "n/a"}` : "";

  const git = delta.git || {};
  const gitLine = git.head
    ? `git: ${git.branch || "?"}@${git.head.slice(0, 8)}${git.dirty ? " (dirty)" : ""}`
    : "git: n/a";
  const sinceGreen = git.last_green_head ? `since green: ${git.last_green_head.slice(0, 8)} -> ${git.head.slice(0, 8)}` : "since green: n/a";

  const flipToFail = (delta.check_deltas?.flipped_to_fail || []).slice(0, 8);
  const flipToPass = (delta.check_deltas?.flipped_to_pass || []).slice(0, 8);
  const failingNow = (delta.check_deltas?.failing_now || []).slice(0, 10);

  const lines = [];
  lines.push(`<span class="tag ${rrCls}">${safeText(rrTxt)}</span>  <span class="mono">${safeText(rrMeta)}</span>`);
  lines.push(`<span class="mono">${safeText(gitLine)}\n${safeText(sinceGreen)}</span>`);
  if (flipToFail.length) lines.push(`<span class="mono">${safeText(`new failures: ${flipToFail.join(", ")}`)}</span>`);
  if (flipToPass.length) lines.push(`<span class="mono">${safeText(`recovered: ${flipToPass.join(", ")}`)}</span>`);
  if (failingNow.length) lines.push(`<span class="mono">${safeText(`failing now: ${failingNow.join(", ")}`)}</span>`);
  if (git.diffstat && git.diffstat.trim()) lines.push(`<span class="mono">${safeText(`diffstat:\n${git.diffstat.trim()}`)}</span>`);

  el.innerHTML = lines.join("<br><br>");
}

function renderGroups(health) {
  const el = qs("#groups");
  const byGroup = {};
  for (const c of health.checks || []) {
    const g = c.group || "Other";
    if (!byGroup[g]) byGroup[g] = { pass: 0, fail: 0, total: 0 };
    byGroup[g].total += 1;
    if (c.ok === true) byGroup[g].pass += 1;
    else if (c.ok === false) byGroup[g].fail += 1;
  }
  const rows = Object.entries(byGroup).sort((a, b) => a[0].localeCompare(b[0]));
  el.innerHTML = rows
    .map(([g, s]) => {
      const label = s.fail > 0 ? "RED" : s.pass === s.total ? "GREEN" : "MIXED";
      return `
        <div class="group">
          <div class="t">${safeText(g)}</div>
          <div class="n">${safeText(label)}</div>
          <div class="b">${safeText(`${s.pass}/${s.total} pass, ${s.fail} fail`)}</div>
        </div>
      `;
    })
    .join("");
}

function renderChecks(health) {
  const el = qs("#checks");
  const checks = (health.checks || []).slice().sort((a, b) => {
    const ao = a.ok === true ? 0 : a.ok === false ? 2 : 1;
    const bo = b.ok === true ? 0 : b.ok === false ? 2 : 1;
    if (ao !== bo) return bo - ao; // failing first
    return (a.group || "").localeCompare(b.group || "") || (a.name || "").localeCompare(b.name || "");
  });

  el.innerHTML = checks
    .map((c, idx) => {
      const dot = statusClass(c.ok);
      const title = `${c.name || c.id || "check"}${c.group ? ` (${c.group})` : ""}`;
      const dur = c.duration_ms != null ? fmtMs(c.duration_ms) : "n/a";
      const meta = `${c.id || ""}${c.timeout_s ? ` | timeout=${c.timeout_s}s` : ""} | dur=${dur}`;

      const lay = safeText((c.purpose || {}).laymen || "");
      const tech = safeText((c.purpose || {}).technical || "");
      const fixLay = safeText((c.how_to_fix || {}).laymen || "");
      const fixTech = safeText((c.how_to_fix || {}).technical || "");

      const cmd = safeText(c.command || "");
      const out = safeText(c.output || "");
      const parsed = c.parsed || null;
      let parsedSummary = "";
      if (parsed && Array.isArray(parsed.results)) {
        const rows = parsed.results
          .slice(0, 24)
          .map((r) => `${r.id || "?"}: ${String(r.status || "?").toUpperCase()}`);
        if (rows.length) parsedSummary = `\n\nacceptance:\n${rows.join("\n")}`;
      }

      let cols = "";
      if (audience === "laymen") {
        cols = `
          <div class="cols">
            <div class="col">
              <div class="h">Purpose (Laymen)</div>
              <div class="p">${lay || "(none)"}</div>
            </div>
            <div class="col">
              <div class="h">How To Fix (Laymen)</div>
              <div class="p">${fixLay || "(none)"}</div>
            </div>
          </div>
        `;
      } else if (audience === "technical") {
        cols = `
          <div class="cols">
            <div class="col">
              <div class="h">Purpose (Technical)</div>
              <div class="p mono">${tech || "(none)"}</div>
            </div>
            <div class="col">
              <div class="h">Run / Evidence</div>
              <div class="p mono">command: ${cmd || "(none)"}${safeText(parsedSummary)}\n\noutput:\n${out || "(none)"}</div>
            </div>
          </div>
          <div class="cols">
            <div class="col">
              <div class="h">How To Fix (Technical)</div>
              <div class="p mono">${fixTech || "(none)"}</div>
            </div>
            <div class="col">
              <div class="h">Meta</div>
              <div class="p mono">${safeText(meta)}</div>
            </div>
          </div>
        `;
      } else {
        cols = `
          <div class="cols">
            <div class="col">
              <div class="h">Laymen</div>
              <div class="p">${lay || "(none)"}\n\nFix: ${fixLay || "(none)"}</div>
            </div>
            <div class="col">
              <div class="h">Technical</div>
              <div class="p mono">${tech || "(none)"}\n\ncommand: ${cmd || "(none)"}${safeText(parsedSummary)}\n\ndur: ${dur}</div>
            </div>
          </div>
          <div class="cols">
            <div class="col">
              <div class="h">Output (Truncated)</div>
              <div class="p mono">${out || "(none)"}</div>
            </div>
            <div class="col">
              <div class="h">How To Fix (Technical)</div>
              <div class="p mono">${fixTech || "(none)"}</div>
            </div>
          </div>
        `;
      }

      return `
        <div class="check" data-idx="${idx}">
          <div class="check-head">
            <div class="dot ${dot}"></div>
            <div>
              <div class="check-title">${safeText(title)}</div>
              <div class="check-meta">${safeText(meta)}</div>
            </div>
            <div class="check-meta">${c.ok === true ? "PASS" : c.ok === false ? "FAIL" : "UNKNOWN"}</div>
          </div>
          <div class="check-body">
            ${cols}
            <div class="toolbar">
              <button class="mini-btn copy-cmd" data-idx="${idx}">Copy Command</button>
              <button class="mini-btn copy-out" data-idx="${idx}">Copy Output</button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  qsa(".check-head").forEach((h) => {
    h.addEventListener("click", () => {
      const parent = h.closest(".check");
      if (!parent) return;
      parent.classList.toggle("open");
    });
  });

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback: best-effort copy via selection.
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return Promise.resolve();
  }

  qsa(".copy-cmd").forEach((b) => {
    b.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const idx = Number(b.dataset.idx || "0");
      const cmdRaw = (lastHealth?.checks?.[idx]?.command || "").toString();
      b.disabled = true;
      try {
        await copyText(cmdRaw);
        b.textContent = "Copied";
        window.setTimeout(() => (b.textContent = "Copy Command"), 900);
      } finally {
        b.disabled = false;
      }
    });
  });
  qsa(".copy-out").forEach((b) => {
    b.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const idx = Number(b.dataset.idx || "0");
      const outRaw = (lastHealth?.checks?.[idx]?.output || "").toString();
      b.disabled = true;
      try {
        await copyText(outRaw);
        b.textContent = "Copied";
        window.setTimeout(() => (b.textContent = "Copy Output"), 900);
      } finally {
        b.disabled = false;
      }
    });
  });
}

function renderSystemMap(repo) {
  const el = qs("#system-map");
  const nodes = (repo.system_map || []).slice();
  const overviewAudience = audience === "technical" ? "technical" : "laymen"; // dashboard also has "split"
  const codeAudience = audience === "laymen" ? "technical" : audience === "technical" ? "technical" : "technical";
  el.innerHTML = nodes
    .map((n) => {
      const nodeId = n.id || "";
      const uxHref = nodeId
        ? `/ux?topic=${encodeURIComponent(nodeId)}&audience=${encodeURIComponent(overviewAudience)}&tab=uiux`
        : "#";
      const uxCodeHref = nodeId
        ? `/ux?topic=${encodeURIComponent(nodeId)}&audience=${encodeURIComponent(codeAudience)}&tab=code`
        : "#";

      let links = "";
      if (lens === "ux") {
        links =
          `<a href="${safeText(uxHref)}" title="${safeText(`UI/UX: ${n.name}`)}">Overview</a>` +
          `<a href="${safeText(uxCodeHref)}" title="${safeText(`Code: ${n.name}`)}">Code</a>`;
      } else {
        if (audience === "laymen") {
          // In laymen mode, do not surface raw file anchors.
          links = `<a href="${safeText(uxHref)}" title="${safeText(`UI/UX: ${n.name}`)}">UI/UX</a>`;
        } else {
          const codeLinks = (n.links || [])
            .map((l) => `<a href="${safeText(l.href)}" title="${safeText(l.label)}">${safeText(l.label)}</a>`)
            .join("");
          links = `<a href="${safeText(uxHref)}" title="${safeText(`UI/UX: ${n.name}`)}">UI/UX</a>` + codeLinks;
        }
      }
      return `
        <div class="node">
          <div class="k">${safeText(n.name || "Component")}</div>
          <div class="d">${safeText(modeText(n.desc) || n.desc?.laymen || n.desc?.technical || "")}</div>
          <div class="l">${links}</div>
        </div>
      `;
    })
    .join("");
}

function renderRepo(repo) {
  const el = qs("#repo");
  const cards = (repo.repo_tour || []).slice();
  const top = (repo.top_level || []).slice();
  const overviewAudience = audience === "technical" ? "technical" : "laymen"; // dashboard also has "split"
  const codeAudience = audience === "laymen" ? "technical" : audience === "technical" ? "technical" : "technical";
  if (top.length) {
    const dirs = top.filter((t) => t.kind === "dir").map((t) => t.name);
    const files = top.filter((t) => t.kind === "file").map((t) => t.name);
    cards.push({
      name: "Top Level Index",
      desc: {
        laymen: `A quick map of what exists in this repo. Dirs: ${dirs.length}, files: ${files.length}.`,
        technical: `Top level entries. Dirs=${dirs.length} Files=${files.length}\n\nDirs:\n- ${dirs.join(
          "\n- "
        )}\n\nFiles:\n- ${files.join("\n- ")}`
      },
      link: { label: "Repo root", href: "/api/open?path=" }
    });
  }
  el.innerHTML = cards
    .map((c) => {
      const desc = modeText(c.desc) || c.desc?.laymen || c.desc?.technical || "";
      const tourId = c.id || "";
      const uxHref = tourId
        ? `/ux?topic=${encodeURIComponent(tourId)}&audience=${encodeURIComponent(overviewAudience)}&tab=uiux`
        : "";
      const uxCodeHref = tourId
        ? `/ux?topic=${encodeURIComponent(tourId)}&audience=${encodeURIComponent(codeAudience)}&tab=code`
        : "";

      let links = "";
      if (lens === "ux" && tourId) {
        links =
          `<a href="${safeText(uxHref)}" title="${safeText(`UI/UX: ${c.name || "Repo Item"}`)}">Overview</a>` +
          `<a href="${safeText(uxCodeHref)}" title="${safeText(`Code: ${c.name || "Repo Item"}`)}">Code</a>`;
      } else {
        const uiuxBtn = tourId
          ? `<a href="${safeText(uxHref)}" title="${safeText(`UI/UX: ${c.name || "Repo Item"}`)}">UI/UX</a>`
          : "";
        let codeLink = "";
        if (c.link) {
          if (audience === "laymen") {
            // If the card only has a raw /api/open anchor, route laymen to the Explorer UI instead.
            const href = (c.link.href || "").toString();
            const prefix = "/api/open?path=";
            let safeHref = href;
            if (href.startsWith(prefix)) {
              const enc = href.slice(prefix.length);
              const rel = decodeURIComponent(enc || "");
              // Best-effort: files -> /doc, dirs -> /open (so laymen stays CPOM-safe).
              const looksLikeFile = /\.[a-z0-9]{1,6}$/i.test(rel) && !rel.endsWith("/");
              safeHref = looksLikeFile
                ? `/doc?path=${encodeURIComponent(rel)}&audience=laymen`
                : `/open?path=${encodeURIComponent(rel)}&audience=laymen`;
            }
            codeLink = `<a href="${safeText(safeHref)}">${safeText(c.link.label || "Open")}</a>`;
          } else {
            codeLink = `<a href="${safeText(c.link.href)}">${safeText(c.link.label)}</a>`;
          }
        }
        links = uiuxBtn + codeLink;
      }
      return `
        <div class="repo-card">
          <div class="h">${safeText(c.name || "Item")}</div>
          <div class="p">${safeText(desc)}</div>
          <div class="l">${links}</div>
        </div>
      `;
    })
    .join("");
}

function render() {
  if (lastHealth) {
    renderOverall(lastHealth);
    renderKpis(lastHealth);
    renderGroups(lastHealth);
    renderChecks(lastHealth);
  }
  if (lastRepo) {
    renderSystemMap(lastRepo);
    renderRepo(lastRepo);
  }
  if (lastDelta) {
    renderDelta(lastDelta);
  }
}

async function loadRepo() {
  const res = await fetch("/api/repo");
  if (!res.ok) throw new Error(`repo fetch failed: ${res.status}`);
  lastRepo = await res.json();
  const stats = lastRepo.stats || {};
  const fp = qs("#footprint");
  if (fp) {
    fp.textContent = `Footprint: workflows=${stats.workflows_n8n_json ?? "n/a"} | runtime_py=${stats.runtime_py ?? "n/a"} | contracts=${stats.contracts_py ?? "n/a"} | scripts=${stats.scripts_total ?? "n/a"} | services=${stats.services_dirs ?? "n/a"} | mcp_servers=${stats.mcp_servers_dirs ?? "n/a"}`;
  }
  render();
}

function currentBundle() {
  const sel = qs("#bundle");
  return sel ? sel.value : "";
}

async function loadHealth(opts) {
  const deep = !!opts?.deep;
  const cached = !!opts?.cached;
  const bundle = opts?.bundle ?? currentBundle();

  const params = [];
  if (deep) params.push("deep=1");
  if (cached) params.push("cached=1");
  if (bundle) params.push(`bundle=${encodeURIComponent(bundle)}`);
  const url = "/api/health" + (params.length ? `?${params.join("&")}` : "");
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`health fetch failed: ${res.status}`);
  lastHealth = await res.json();
  render();
}

async function loadDelta(bundle) {
  const params = [];
  if (bundle) params.push(`bundle=${encodeURIComponent(bundle)}`);
  const url = "/api/delta" + (params.length ? `?${params.join("&")}` : "");
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`delta fetch failed: ${res.status}`);
  lastDelta = await res.json();
  render();
}

function init() {
  qsa(".seg-btn[data-audience]").forEach((b) => b.addEventListener("click", () => setAudience(b.dataset.audience)));
  setAudience("laymen");

  installPointerGlow();
  installRevealObserver();

  const uxBtn = qs("#lens-ux");
  const codeBtn = qs("#lens-code");
  const savedLens = window.localStorage ? window.localStorage.getItem("eve_dashboard_lens") : "";
  setLens(savedLens === "code" ? "code" : "ux");
  if (uxBtn) uxBtn.addEventListener("click", () => setLens("ux"));
  if (codeBtn) codeBtn.addEventListener("click", () => setLens("code"));

  const bundleSel = qs("#bundle");
  if (bundleSel) {
    const saved = window.localStorage ? window.localStorage.getItem("eve_dashboard_bundle") : "";
    if (saved != null && saved !== "") {
      bundleSel.value = saved;
    }
  }

  qs("#refresh").addEventListener("click", async () => {
    await loadHealth({ deep: false, cached: false, bundle: "" });
    await loadDelta(currentBundle());
  });

  const runBtn = qs("#run");
  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      const b = currentBundle();
      const deep = b !== ""; // any non-empty bundle implies deep intent
      runBtn.disabled = true;
      runBtn.textContent = "Running...";
      try {
        await loadHealth({ deep: deep, cached: false, bundle: b });
        await loadDelta(b);
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = "Run";
      }
    });
  }

  if (bundleSel) {
    bundleSel.addEventListener("change", async () => {
      if (window.localStorage) window.localStorage.setItem("eve_dashboard_bundle", currentBundle());
      await loadHealth({ deep: false, cached: true, bundle: currentBundle() });
      await loadDelta(currentBundle());
    });
  }

  // Load cached state first (instant), then refresh fast checks.
  loadHealth({ deep: false, cached: true, bundle: "" }).catch(() => {});
  loadDelta(currentBundle()).catch(() => {});

  window.setTimeout(() => {
    loadHealth({ deep: false, cached: false, bundle: "" }).catch(() => {});
  });

  loadRepo().catch((e) => {
    qs("#overall-meta").textContent = `Repo load failed: ${e.message}`;
  });
  loadHealth({ deep: false, cached: false, bundle: "" }).catch((e) => {
    qs("#overall-meta").textContent = `Health load failed: ${e.message}`;
  });

  window.setInterval(() => {
    loadHealth({ deep: false, cached: false, bundle: "" }).catch(() => {});
    loadDelta(currentBundle()).catch(() => {});
  }, 15000);
}

document.addEventListener("DOMContentLoaded", init);
