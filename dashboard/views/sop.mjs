import { fetchJSON } from "../lib/api.mjs";

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function attrEnc(s) {
  return encodeURIComponent(String(s == null ? "" : s));
}

function clampAudience(a) {
  return a === "technical" ? "technical" : "laymen";
}

function fmtHealthPill(health) {
  const s = (health && health.summary) || {};
  const ok = s.ok;
  const cls = ok === true ? "good" : ok === false ? "bad" : "unk";
  const txt = ok === true ? "GREEN" : ok === false ? "RED" : "UNKNOWN";
  const meta = s.generated_at_iso ? `Updated: ${s.generated_at_iso}` : "Updated: n/a";
  return `<span class="pill ${cls}"><span class="dot ${cls}"></span>${safeText(txt)}</span><span class="muted mono">${safeText(meta)}</span>`;
}

function toDocHref(path) {
  return `/doc?path=${encodeURIComponent(String(path || ""))}`;
}

function toUxHref(topic) {
  return `/ux?topic=${encodeURIComponent(String(topic || ""))}`;
}

function skeleton() {
  return `
    <section class="panel">
      <div class="panel-title">SOP</div>
      <div class="panel-body">
        <div class="grid2">
          <div class="skeleton" style="height:520px"></div>
          <div class="skeleton" style="height:520px"></div>
        </div>
      </div>
    </section>
  `;
}

function pickText(audience, obj) {
  const aud = clampAudience(audience);
  return safeText((obj && (obj[aud] || obj.laymen || obj.technical)) || "");
}

function findCheckById(checks, id) {
  const want = String(id || "").trim();
  if (!want) return null;
  for (const c of checks || []) {
    if (String(c.id || "") === want) return c;
  }
  return null;
}

function renderGateCard(audience, check) {
  if (!check) return "";
  const aud = clampAudience(audience);
  const ok = check.ok;
  const cls = ok === true ? "good" : ok === false ? "bad" : "unk";
  const statusTxt = ok === true ? "PASS" : ok === false ? "FAIL" : "UNKNOWN";

  const layPurpose = safeText(((check.purpose || {}).laymen) || "");
  const techPurpose = safeText(((check.purpose || {}).technical) || "");
  const layFix = safeText(((check.how_to_fix || {}).laymen) || "");
  const techFix = safeText(((check.how_to_fix || {}).technical) || "");
  const cmd = safeText(check.command || "");
  const timeout = check.timeout_s != null ? `timeout=${Number(check.timeout_s)}s` : "";

  // CPOM rule: laymen never sees command blocks or copy buttons.
  const showTech = aud === "technical";

  return `
    <div class="check ${ok === false ? "fail" : ""}">
      <div class="check-head" style="cursor:default">
        <span class="dot ${cls}"></span>
        <span class="ct">
          <span class="ttl">${safeText(check.name || check.id || "check")}</span>
          <span class="meta mono">${safeText([check.id, timeout].filter(Boolean).join(" | "))}</span>
        </span>
        <span class="st mono">${safeText(statusTxt)}</span>
      </div>
      <div class="check-body open" style="max-height:none;opacity:1;transform:none;padding:0 12px 12px 12px">
        <div class="cols">
          <div class="col">
            <div class="h">Purpose</div>
            <div class="p">${aud === "technical" ? `<div class="mono">${techPurpose || "<span class='muted'>(none)</span>"}</div>` : layPurpose || "<span class='muted'>(none)</span>"}</div>
            <div style="height:8px"></div>
            <div class="h">Fix</div>
            <div class="p">${aud === "technical" ? `<div class="mono">${techFix || "<span class='muted'>(none)</span>"}</div>` : layFix || "<span class='muted'>(none)</span>"}</div>
          </div>
          <div class="col">
            <div class="h">How To Run</div>
            ${
              showTech
                ? `<div class="p mono">${cmd || "<span class='muted'>(none)</span>"}</div>
                   <div style="height:10px"></div>
                   <div class="ctools">
                     <button class="btn btn-quiet mono sop-copy" data-copy-uri="${attrEnc(check.command || "")}" type="button">Copy cmd</button>
                   </div>`
                : `<div class="p muted">Use the Dashboard <b>Run</b> button to execute gates.</div>`
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderPrinciples(audience, principles) {
  const rows = (principles || []).map((p) => {
    const title = safeText(p.title || p.id || "");
    const text = pickText(audience, p.text || {});
    return `<div class="cardx"><div class="cap">${title}</div><div class="body">${text || "<span class='muted'>(none)</span>"}</div></div>`;
  });
  return `<div class="grid2">${rows.join("")}</div>`;
}

function renderDocs(audience, docs) {
  const aud = clampAudience(audience);
  return `
    <div class="cardx">
      <div class="cap">Primary Docs</div>
      <div class="body">
        <div class="muted">These are the source-of-truth runbooks and maps. In Laymen mode they open as redacted previews.</div>
        <div style="height:10px"></div>
        <div class="deck-links">
          ${(docs || [])
            .map((d) => {
              const label = safeText(d.label || d.path || "");
              const href = toDocHref(d.path || "");
              return `<a class="mlink" href="${safeText(href)}" data-nav>${label}</a>`;
            })
            .join("")}
        </div>
        ${
          aud === "technical"
            ? `<div style="height:10px"></div>
               <div class="muted mono">Tip: use ⌘K to open any file by name.</div>`
            : ""
        }
      </div>
    </div>
  `;
}

function renderMethod(audience, sop, checksIndex, selectedPhaseId) {
  const phases = sop.phases || [];
  const phase = phases.find((p) => String(p.id) === String(selectedPhaseId)) || phases[0] || null;
  if (!phase) return `<div class="muted">(no phases configured)</div>`;

  const aud = clampAudience(audience);
  const goal = pickText(aud, phase.goal || {});
  const why = pickText(aud, phase.why || {});
  const output = pickText(aud, phase.output || {});

  const steps = (phase.steps || []).map((s, idx) => {
    const title = safeText(s.title || `Step ${idx + 1}`);
    const gates = (s.gates || []).filter(Boolean);
    const links = (s.links || []).filter(Boolean);
    const commands = aud === "technical" ? (s.commands || []).filter(Boolean) : [];
    const evidence = aud === "technical" ? (s.evidence || []).filter(Boolean) : [];

    const gatesHtml = gates.length
      ? `<div class="row" style="gap:8px;flex-wrap:wrap">
           ${gates.map((g) => `<span class="code mono">${safeText(g)}</span>`).join("")}
         </div>`
      : `<div class="muted">(no gates)</div>`;

    const linksHtml = links.length
      ? `<div class="deck-links">
           ${links
             .map((l) => `<a class="mlink" href="${safeText(toDocHref(l.path || ""))}" data-nav>${safeText(l.label || l.path || "")}</a>`)
             .join("")}
         </div>`
      : `<div class="muted">(no links)</div>`;

    const commandsHtml =
      aud === "technical" && commands.length
        ? `<div class="pre mono">${safeText(commands.join("\n"))}</div>
           <div style="height:10px"></div>
           <div class="ctools">
             <button class="btn btn-quiet mono sop-copy" data-copy-uri="${attrEnc(commands.join("\n"))}" type="button">Copy block</button>
           </div>`
        : "";

    const evidenceHtml =
      aud === "technical" && evidence.length
        ? `<div class="pre mono">${safeText(evidence.join("\n"))}</div>
           <div style="height:10px"></div>
           <div class="ctools">
             <button class="btn btn-quiet mono sop-copy" data-copy-uri="${attrEnc(evidence.join("\n"))}" type="button">Copy paths</button>
           </div>`
        : "";

    // Gates expanded into cards below in "Readiness Gates".
    return `
      <div class="cardx">
        <div class="cap">Step ${idx + 1}</div>
        <div class="body">
          <div style="font-weight:600">${title}</div>
          <div style="height:10px"></div>
          <div class="cols">
            <div class="col">
              <div class="h">Readiness Gates</div>
              <div class="p">${gatesHtml}</div>
              <div style="height:10px"></div>
              <div class="h">Docs</div>
              <div class="p">${linksHtml}</div>
            </div>
            <div class="col">
              <div class="h">Commands</div>
              <div class="p">${aud === "technical" ? "Exact commands (technical view)." : "<span class='muted'>(hidden in laymen mode)</span>"}</div>
              ${commandsHtml || ""}
              <div style="height:10px"></div>
              <div class="h">Evidence</div>
              <div class="p">${aud === "technical" ? "Where proof is written/read." : "<span class='muted'>(hidden in laymen mode)</span>"}</div>
              ${evidenceHtml || ""}
            </div>
          </div>
        </div>
      </div>
    `;
  });

  // Gate cards (dedupe in phase)
  const gateIds = [];
  for (const s of phase.steps || []) for (const g of s.gates || []) if (g && !gateIds.includes(g)) gateIds.push(g);
  const gatesCards = gateIds
    .map((id) => renderGateCard(aud, checksIndex[id] || null))
    .filter(Boolean)
    .join("");

  return `
    <div class="stack">
      <div class="cardx">
        <div class="cap">${safeText(phase.name || phase.id || "Phase")}</div>
        <div class="body">
          <div class="cols">
            <div class="col">
              <div class="h">Goal</div>
              <div class="p">${goal || "<span class='muted'>(none)</span>"}</div>
            </div>
            <div class="col">
              <div class="h">Why</div>
              <div class="p">${why || "<span class='muted'>(none)</span>"}</div>
            </div>
          </div>
          <div style="height:10px"></div>
          <div class="callout">
            <b>Output</b>
            <div class="muted" style="margin-top:6px">${output || "(none)"}</div>
          </div>
        </div>
      </div>

      <div class="grid2">${steps.join("")}</div>

      <div class="panel">
        <div class="panel-title">Readiness Gates</div>
        <div class="panel-body">
          ${gatesCards || "<div class='muted'>(no gates referenced)</div>"}
        </div>
      </div>
    </div>
  `;
}

function renderComponents(audience, repo, guidanceByTopic) {
  const aud = clampAudience(audience);
  const sys = (repo && repo.system_map) || [];
  const stats = (repo && repo.stats) || {};

  const footprint = [
    ["Workflows", stats.workflows_n8n_json],
    ["Runtime (py)", stats.runtime_py],
    ["Contracts", stats.contracts_py],
    ["Scripts", stats.scripts_total],
    ["Services", stats.services_dirs],
    ["MCP Servers", stats.mcp_servers_dirs]
  ];

  const chips = footprint
    .map(([k, v]) => `<div class="chip"><div class="ck">${safeText(k)}</div><div class="cv mono">${safeText(v ?? "n/a")}</div></div>`)
    .join("");

  const cards = sys
    .map((n) => {
      const id = String(n.id || "");
      const name = safeText(n.name || id);
      const desc = pickText(aud, n.desc || {});
      const g = guidanceByTopic[id] || {};
      const fm = pickText(aud, g.failure_modes || {});
      const cs = (g.change_safely || {}) || {};
      const gates = (cs.gates || []).filter(Boolean);
      const evidence = aud === "technical" ? (cs.evidence || []).filter(Boolean) : [];

      const links = (n.links || []).filter(Boolean).map((l) => ({ label: String(l.label || ""), href: String(l.href || "") }));
      // CPOM: never expose /api/open hrefs in laymen mode.
      const linkHrefs = links
        .map((l) => {
          const label = safeText(l.label || "");
          const raw = String(l.href || "");
          if (aud === "technical") {
            // Prefer doc/explorer for reading even in technical mode; raw is available elsewhere.
            // Transform api/open into doc/open pages by mirroring server logic:
            if (raw.startsWith("/api/open")) {
              try {
                const u = new URL(raw, window.location.origin);
                const p = u.searchParams.get("path") || "";
                return { label, href: `/doc?path=${encodeURIComponent(p)}` };
              } catch (_) {
                return { label, href: raw };
              }
            }
            return { label, href: raw };
          }
          // laymen
          if (raw.startsWith("/api/open")) {
            try {
              const u = new URL(raw, window.location.origin);
              const p = u.searchParams.get("path") || "";
              return { label, href: `/doc?path=${encodeURIComponent(p)}` };
            } catch (_) {
              return { label, href: "/" };
            }
          }
          return { label, href: raw };
        })
        .filter((x) => x.label && x.href);

      return `
        <div class="cardx">
          <div class="cap">${name}</div>
          <div class="body">
            <div class="muted">${desc || "(no description)"}</div>
            <div style="height:10px"></div>
            <div class="callout">
              <b>Failure modes</b>
              <div class="muted" style="margin-top:6px">${fm || "(not specified)"}</div>
            </div>
            <div style="height:10px"></div>
            <div class="cols">
              <div class="col">
                <div class="h">Open Topic</div>
                <div class="p"><a class="mlink" href="${safeText(toUxHref(id))}" data-nav>${safeText(id)}</a></div>
                <div style="height:10px"></div>
                <div class="h">Artifacts</div>
                <div class="p">
                  ${
                    linkHrefs.length
                      ? `<div class="deck-links">${linkHrefs
                          .map((x) => `<a class="mlink" href="${safeText(x.href)}" data-nav>${safeText(x.label)}</a>`)
                          .join("")}</div>`
                      : "<span class='muted'>(none)</span>"
                  }
                </div>
              </div>
              <div class="col">
                <div class="h">Change safely</div>
                <div class="p">
                  ${
                    gates.length
                      ? `<div class="row" style="gap:8px;flex-wrap:wrap">${gates.map((g) => `<span class="code mono">${safeText(g)}</span>`).join("")}</div>`
                      : "<span class='muted'>(no gates mapped)</span>"
                  }
                </div>
                <div style="height:10px"></div>
                <div class="h">Evidence</div>
                <div class="p">
                  ${
                    aud === "technical" && evidence.length
                      ? `<div class="pre mono">${safeText(evidence.join("\n"))}</div>`
                      : "<span class='muted'>(hidden or none)</span>"
                  }
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  return `
    <div class="stack">
      <div class="cardx">
        <div class="cap">Footprint</div>
        <div class="body">
          <div class="deck-chips">${chips}</div>
        </div>
      </div>
      <div class="grid2">${cards}</div>
    </div>
  `;
}

export async function renderSop(ctx) {
  const { root, route, getState, setChrome, isActive } = ctx;

  setChrome({ sub: "SOP (methodology + runbook)", routeKey: "sop", showRun: false });

  root.innerHTML = skeleton();

  const view = (route.q.get("view") || "method").trim().toLowerCase();
  const phase = (route.q.get("phase") || "").trim();

  try {
    const [sop, checksRaw, repo, health] = await Promise.all([
      fetchJSON("/sop.json", { timeoutMs: 1800, ttlMs: 60000 }),
      fetchJSON("/checks.json", { timeoutMs: 1800, ttlMs: 60000 }),
      fetchJSON("/api/repo", { timeoutMs: 2200, ttlMs: 15000 }),
      fetchJSON("/api/health?cached=1&strict=1", { timeoutMs: 900, ttlMs: 800 }).catch(() => null),
    ]);
    if (!isActive()) return () => {};

    const checksList = (checksRaw && checksRaw.checks) || [];
    // Merge live status (strict cached) into check definitions for SOP gate cards.
    const liveById = {};
    if (health && Array.isArray(health.checks)) {
      for (const r of health.checks) liveById[String((r && r.id) || "")] = r;
    }
    const checksIndex = {};
    for (const c of checksList) {
      const id = String(c.id || "");
      const live = liveById[id] || {};
      checksIndex[id] = { ...c, ok: live.ok, output: live.output, duration_ms: live.duration_ms };
    }

    const guidanceByTopic = {};
    for (const g of (sop.component_guidance || [])) {
      if (g && g.topic) guidanceByTopic[String(g.topic)] = g;
    }

    const phases = sop.phases || [];
    const firstPhase = phases[0] ? String(phases[0].id || "") : "";
    const phaseId = phase || firstPhase;

    const tab = view === "components" ? "components" : view === "evidence" ? "evidence" : "method";

    const leftPhases = phases
      .map((p) => {
        const id = String(p.id || "");
        const name = safeText(p.name || id);
        const active = tab === "method" && id === phaseId ? "active" : "";
        const href = `/sop?view=method&phase=${encodeURIComponent(id)}`;
        return `<a class="deck-item ${active}" href="${safeText(href)}" data-nav>
          <div class="t">${name}</div>
          <div class="k mono">${safeText(id)}</div>
        </a>`;
      })
      .join("");

    const tabBtn = (id, label) => {
      const active = tab === id ? "active" : "";
      const href = id === "method" ? `/sop?view=method&phase=${encodeURIComponent(phaseId)}` : `/sop?view=${encodeURIComponent(id)}`;
      return `<a class="nav-link ${active}" href="${safeText(href)}" data-nav>${safeText(label)}</a>`;
    };

    const header = `
      <div class="deck-top">
        <div>
          <div class="deck-h1">${safeText(sop.title || "SOP")}</div>
          <div class="muted">${safeText(sop.subtitle || "")}</div>
          <div style="height:10px"></div>
          <div class="row" style="gap:10px;flex-wrap:wrap">
            ${health ? fmtHealthPill(health) : ""}
            <a class="btn btn-quiet mono" href="/" data-nav>Dashboard</a>
            <a class="btn btn-quiet mono" href="/deck" data-nav>Deck</a>
          </div>
        </div>
        <div class="deck-nav">
          <div class="nav">
            ${tabBtn("method", "Method")}
            ${tabBtn("components", "Component Map")}
            ${tabBtn("evidence", "Evidence")}
          </div>
        </div>
      </div>
    `;

    function renderDynamic(audience) {
      const aud = clampAudience(audience);
      const principles = renderPrinciples(aud, sop.principles || []);
      const docs = renderDocs(aud, sop.docs || []);

      const evidencePanel =
        aud === "technical"
        ? `<div class="panel">
            <div class="panel-title">Evidence</div>
            <div class="panel-body">
              <div class="callout">
                <b>Where proof lives</b>
                <div class="muted" style="margin-top:6px">Evidence artifacts are written under the state dir. This keeps the repo clean and avoids committing secrets.</div>
              </div>
              <div style="height:12px"></div>
              <div class="pre mono">${safeText("${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}/dashboard/health_last_*.json")}\n${safeText("${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}/acceptance/trends/last_7.json")}</div>
              <div style="height:10px"></div>
              <div class="ctools">
                <button class="btn btn-quiet mono sop-copy" data-copy-uri="${attrEnc("${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}/dashboard/health_last_*.json\n${OPENCLAW_STATE_DIR:-$HOME/.openclaw-eve}/acceptance/trends/last_7.json")}" type="button">Copy paths</button>
              </div>
            </div>
          </div>`
        : `<div class="panel"><div class="panel-title">Evidence</div><div class="panel-body"><div class="muted">Evidence paths are hidden in Laymen mode. Switch to Technical for exact locations.</div></div></div>`;

      let main = "";
      if (tab === "method") {
        main = `<div class="stack">${principles}${docs}${renderMethod(aud, sop, checksIndex, phaseId)}</div>`;
      } else if (tab === "components") {
        main = `<div class="stack">${principles}${docs}${renderComponents(aud, repo, guidanceByTopic)}</div>`;
      } else {
        main = `<div class="stack">${principles}${docs}${evidencePanel}</div>`;
      }
      return main;
    }

    root.innerHTML = `
      <section class="deck sop">
        <aside class="deck-side">
          <div class="deck-brand">
            <div class="deck-title">SOP</div>
            <div class="deck-sub muted">Operator methodology you can improve over time.</div>
          </div>
          <div class="deck-actions">
            <a class="btn btn-primary" href="/sop?view=method&phase=${safeText(encodeURIComponent(phaseId))}" data-nav>Open Method</a>
            <a class="btn" href="/sop?view=components" data-nav>Open Component Map</a>
          </div>
          <div class="deck-h mono">Phases</div>
          <div class="deck-list">${leftPhases || "<div class='muted mono'>(none)</div>"}</div>
        </aside>
        <main class="deck-main">
          ${header}
          <div style="height:14px"></div>
          <div id="sop-dynamic"></div>
        </main>
      </section>
    `;

    const dyn = root.querySelector("#sop-dynamic");
    if (dyn) dyn.innerHTML = renderDynamic(getState().audience);

    // Copy handlers (technical only; buttons are not rendered in laymen mode).
    const onClick = async (e) => {
      const t = e.target;
      const b = t && t.closest ? t.closest(".sop-copy") : null;
      if (!b) return;
      e.preventDefault();
      const audNow = clampAudience(getState().audience);
      if (audNow !== "technical") return;
      const encoded = b.getAttribute("data-copy-uri") || "";
      const txt = decodeURIComponent(encoded || "");
      const prev = b.textContent || "Copy";
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(txt);
        b.textContent = "Copied";
        window.setTimeout(() => (b.textContent = prev), 900);
      } catch (_) {
        // ignore
      }
    };
    root.addEventListener("click", onClick);

    const cleanup = () => {
      root.removeEventListener("click", onClick);
    };
    cleanup.update = async (prev, next) => {
      // Only preferences changed; re-render dynamic content in place.
      if (!dyn) return;
      const y = window.scrollY || 0;
      dyn.innerHTML = renderDynamic(next.audience);
      try {
        window.scrollTo(0, y);
      } catch (_) {}
    };
    return cleanup;
  } catch (e) {
    if (!isActive()) return () => {};
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">SOP Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load SOP.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
            <div style="height:10px"></div>
            <div class="row" style="gap:10px;flex-wrap:wrap">
              <a class="btn btn-primary" href="/sop" data-nav>Retry</a>
              <a class="btn" href="/" data-nav>Dashboard</a>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  return () => {};
}
