import { fetchJSON } from "../lib/api.mjs";

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function clampAudience(a) {
  return a === "technical" ? "technical" : "laymen";
}

function clampLens(l) {
  if (l === "code") return "code";
  if (l === "split") return "split";
  return "uiux";
}

function prettyHrefForOpen(href) {
  const h = String(href || "");
  if (!h.startsWith("/api/open")) return h;
  try {
    const u = new URL(h, window.location.origin);
    const p = u.searchParams.get("path") || "";
    return `/doc?path=${encodeURIComponent(p)}`;
  } catch (_) {
    return h;
  }
}

function slideOrder(repo) {
  const tour = (repo && repo.repo_tour) || [];
  const sys = (repo && repo.system_map) || [];
  const out = [];
  for (const x of tour) if (x && x.id) out.push(String(x.id));
  for (const x of sys) if (x && x.id) out.push(String(x.id));
  // de-dupe, keep order
  const seen = new Set();
  return out.filter((id) => (seen.has(id) ? false : (seen.add(id), true)));
}

export async function renderDeck(ctx) {
  const { root, route, getState, setChrome, navigate, isActive, shared } = ctx;
  setChrome({ sub: "Pitch Deck (CPOM-safe)", routeKey: "deck", showRun: false });

  root.innerHTML = `
    <section class="panel">
      <div class="panel-title">Deck</div>
      <div class="panel-body">
        <div class="grid2">
          <div class="skeleton" style="height:520px"></div>
          <div class="skeleton" style="height:520px"></div>
        </div>
      </div>
    </section>
  `;

  try {
    const repo = await fetchJSON("/api/repo", { timeoutMs: 2500, ttlMs: 4000 });
    if (!isActive()) return () => {};

    const tour = (repo && repo.repo_tour) || [];
    const sys = (repo && repo.system_map) || [];
    const order = slideOrder(repo);

    const chosen = route.q.get("id") || route.q.get("topic") || (tour[0] && tour[0].id) || (sys[0] && sys[0].id) || "tour_readme";

    const idx = Math.max(0, order.indexOf(chosen));
    const prevId = idx > 0 ? order[idx - 1] : null;
    const nextId = idx < order.length - 1 ? order[idx + 1] : null;

    const topicKey = String(chosen || "").trim().toLowerCase();
    const uxByAud = { laymen: null, technical: null };

    async function ensureUx(aud) {
      const a = clampAudience(aud);
      if (uxByAud[a]) return uxByAud[a];
      const cacheKey = `${a}:${topicKey}`;
      let ux = shared && shared.uxByKey ? shared.uxByKey.get(cacheKey) : null;
      if (!ux) {
        ux = await fetchJSON(`/api/ux?topic=${encodeURIComponent(String(chosen))}&audience=${encodeURIComponent(a)}`, { timeoutMs: 2500, ttlMs: 60000 });
        try {
          if (shared && shared.uxByKey) shared.uxByKey.set(cacheKey, ux);
        } catch (_) {}
      }
      uxByAud[a] = ux;
      return ux;
    }

    await ensureUx(getState().audience);
    if (!isActive()) return () => {};

    const stats = (repo && repo.stats) || {};
    const footprint = [
      ["Workflows", stats.workflows_n8n_json],
      ["Runtime (py)", stats.runtime_py],
      ["Contracts", stats.contracts_py],
      ["Scripts", stats.scripts_total],
      ["Services", stats.services_dirs],
      ["MCP Servers", stats.mcp_servers_dirs],
    ];

    function computeSlideHtml(aud, lens, ux) {
      const a = clampAudience(aud);
      const l = a === "laymen" ? "uiux" : clampLens(lens);
      const uiux = String((ux && ux.uiux_html) || "");
      const code = String((ux && ux.code_html) || "");
      if (a === "laymen") {
        return `<div class="cardx deck-slide"><div class="cap">Vision</div><div class="body">${uiux || "<div class='muted'>(no content)</div>"}</div></div>`;
      }
      if (l === "split") {
        return `<div class="split">
          <div class="cardx deck-slide"><div class="cap">Vision</div><div class="body">${uiux || "<div class='muted'>(no content)</div>"}</div></div>
          <div class="cardx deck-slide"><div class="cap">Code</div><div class="body">${code || "<div class='muted'>(no content)</div>"}</div></div>
        </div>`;
      }
      if (l === "code") return `<div class="cardx deck-slide"><div class="cap">Code</div><div class="body">${code || "<div class='muted'>(no content)</div>"}</div></div>`;
      return `<div class="cardx deck-slide"><div class="cap">Vision</div><div class="body">${uiux || "<div class='muted'>(no content)</div>"}</div></div>`;
    }

    function computeRunHtml(aud) {
      const a = clampAudience(aud);
      return a === "laymen"
        ? `<div class="muted">Green means checks passed. Red means something is failing or missing. Use the Dashboard for the 10-second health signal.</div>`
        : `<div class="row" style="gap:10px;flex-wrap:wrap">
            <span class="code">eve</span>
            <span class="muted">or</span>
            <span class="code">python3 scripts/dashboard/health_server.py --open --quiet</span>
          </div>`;
    }

    function computeArtifactsHtml(ux) {
      const links = (ux && ux.code_links ? ux.code_links : [])
        .map((l) => ({ label: String(l.label || ""), href: prettyHrefForOpen(String(l.href || "")) }))
        .filter((x) => x.label && x.href);
      if (!links.length) return `<div class="muted mono">(no links)</div>`;
      return `<div class="deck-links">${links.map((l) => `<a class="mlink" href="${safeText(l.href)}" data-nav>${safeText(l.label)}</a>`).join("")}</div>`;
    }

    const sidebarSection = (label, items) => {
      const rows = (items || [])
        .map((x) => {
          const id = String(x.id || "");
          const name = String(x.name || x.id || "");
          const active = id === chosen ? "active" : "";
          return `<a class="deck-item ${active}" href="/deck?id=${encodeURIComponent(id)}" data-nav>
              <div class="t">${safeText(name)}</div>
              <div class="k mono">${safeText(id)}</div>
            </a>`;
        })
        .join("");
      return `
        <div class="deck-group">
          <div class="deck-h mono">${safeText(label)}</div>
          <div class="deck-list">${rows || "<div class='muted mono'>No items.</div>"}</div>
        </div>
      `;
    };

    const st0 = getState();
    const aud0 = clampAudience(st0.audience);
    const lens0 = clampLens(st0.lens);
    const ux0 = uxByAud[aud0];
    const title0 = String((ux0 && ux0.title) || chosen);

    root.innerHTML = `
      <section class="deck">
        <aside class="deck-side">
          <div class="deck-brand">
            <div class="deck-title">Eve</div>
            <div class="deck-sub muted">A reality-grounded system map you can pitch in 60 seconds.</div>
          </div>

          <div class="deck-actions">
            <a class="btn btn-primary" href="/ux?topic=${encodeURIComponent(String(chosen))}" data-nav>Open Topic</a>
            <a class="btn" href="/sop" data-nav>Open SOP</a>
            <a class="btn" href="/open?path=" data-nav>Explore Repo</a>
          </div>

          <div class="deck-stats">
            <div class="deck-h mono">Footprint</div>
            <div class="deck-chips">
              ${footprint
                .map(([k, v]) => `<div class="chip"><div class="ck">${safeText(k)}</div><div class="cv mono">${safeText(v ?? "n/a")}</div></div>`)
                .join("")}
            </div>
          </div>

          ${sidebarSection("Repo Tour", tour)}
          ${sidebarSection("System Map", sys)}
        </aside>

        <main class="deck-main">
          <div class="deck-top">
            <div>
              <div class="deck-h1" id="deck-title">${safeText(title0)}</div>
              <div class="muted mono" id="deck-meta">audience=${safeText(aud0)} | lens=${safeText(lens0)} | id=${safeText(String(chosen))}</div>
            </div>
            <div class="deck-nav">
              <button class="btn btn-quiet mono" id="prev" type="button" ${prevId ? "" : "disabled"}>Prev</button>
              <button class="btn btn-quiet mono" id="next" type="button" ${nextId ? "" : "disabled"}>Next</button>
            </div>
          </div>

          <div style="height:14px"></div>
          <div id="deck-slide">${computeSlideHtml(aud0, lens0, ux0)}</div>

          <div style="height:14px"></div>
          <div class="deck-bottom">
            <div class="cardx">
              <div class="cap">Run</div>
              <div class="body" id="deck-run">${computeRunHtml(aud0)}</div>
            </div>

            <div class="cardx">
              <div class="cap">Artifacts</div>
              <div class="body" id="deck-artifacts">${computeArtifactsHtml(ux0)}</div>
            </div>
          </div>
        </main>
      </section>
    `;

    const prev = root.querySelector("#prev");
    const next = root.querySelector("#next");
    if (prev && prevId) prev.addEventListener("click", () => navigate(`/deck?id=${encodeURIComponent(prevId)}`));
    if (next && nextId) next.addEventListener("click", () => navigate(`/deck?id=${encodeURIComponent(nextId)}`));

    const elTitle = root.querySelector("#deck-title");
    const elMeta = root.querySelector("#deck-meta");
    const elSlide = root.querySelector("#deck-slide");
    const elRun = root.querySelector("#deck-run");
    const elArtifacts = root.querySelector("#deck-artifacts");

    const cleanup = () => {};
    cleanup.update = async (prevSt, nextSt) => {
      const a = clampAudience(nextSt.audience);
      const l = clampLens(nextSt.lens);
      if (!uxByAud[a]) await ensureUx(a);
      const ux = uxByAud[a] || uxByAud.laymen || uxByAud.technical || {};
      const ttl = String((ux && ux.title) || chosen);

      if (elTitle) elTitle.textContent = ttl;
      if (elMeta) elMeta.textContent = `audience=${a} | lens=${a === "laymen" ? "uiux" : l} | id=${String(chosen)}`;
      if (elSlide) elSlide.innerHTML = computeSlideHtml(a, l, ux);
      if (elRun) elRun.innerHTML = computeRunHtml(a);
      if (elArtifacts) elArtifacts.innerHTML = computeArtifactsHtml(ux);
    };

    return cleanup;
  } catch (e) {
    if (!isActive()) return () => {};
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Deck Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load deck.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
            <div style="height:10px"></div>
            <a class="btn btn-primary" href="/" data-nav>Back to Dashboard</a>
          </div>
        </div>
      </section>
    `;
  }

  return () => {};
}
