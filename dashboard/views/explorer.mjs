import { fetchJSON, fetchText } from "../lib/api.mjs";
import { redactMarkdownForLaymen } from "../lib/redaction.mjs";
import { renderMarkdown } from "../lib/markdown.mjs";

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] || c));
}

function escapeHtml(s) {
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

function humanSize(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "";
  if (v < 1024) return `${v}B`;
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)}KB`;
  return `${(v / (1024 * 1024)).toFixed(1)}MB`;
}

function topicForPath(p) {
  const path = (p || "").replace(/^\/+/, "");
  const lc = path.toLowerCase();
  if (lc === "" || lc === ".") return "tour_readme";
  if (lc.startsWith("business_code")) return "tour_business_code";
  if (lc.startsWith("workflows_n8n")) return "workflows_n8n";
  if (lc.startsWith("src/runtime")) return "runtime_core";
  if (lc.startsWith("tests/contracts")) return "acceptance_gates";
  if (lc.startsWith("scripts/acceptance")) return "acceptance_gates";
  if (lc.startsWith("openclaw_workspace_template")) return "identity_constraints";
  if (lc.startsWith("supabase")) return "storage_schema";
  if (lc.startsWith("docker") || lc.startsWith("ops")) return "ops_deploy";
  if (lc === "skills.md" || lc.startsWith(".agents/skills")) return "capabilities_skills";
  if (lc === "soul.md" || lc.endsWith("/soul.md")) return "identity_constraints";
  return "tour_readme";
}

function icon(entry) {
  if (entry.kind === "dir") return "dir";
  const n = String(entry.name || "").toLowerCase();
  if (n.endsWith(".md") || n.endsWith(".txt")) return "md";
  if (/\.(py|mjs|js|ts|sh|sql|json|yaml|yml|toml|css|html)$/.test(n)) return "code";
  return "file";
}

async function copyText(text) {
  const t = String(text || "");
  if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(t);
  const ta = document.createElement("textarea");
  ta.value = t;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

function template() {
  return `
    <section class="panel" id="exp-panel">
      <div class="panel-title">Explorer</div>
      <div class="panel-body">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px">
          <div>
            <div class="h1" id="exp-title">(loading)</div>
            <div class="muted mono" id="exp-meta"></div>
          </div>
          <div class="row" style="gap:10px;flex-wrap:wrap">
            <button class="btn btn-quiet mono" id="exp-copy-path" type="button">Copy path</button>
            <a class="btn" href="/open?path=" data-nav>Repo root</a>
          </div>
        </div>
        <div style="height:12px"></div>

        <section class="grid2">
          <div class="panel" style="box-shadow:none;background:transparent;border:0">
            <div class="panel">
              <div class="panel-title row" style="justify-content:space-between;gap:10px">
                <span>Navigator</span>
                <input class="filter" id="exp-filter" placeholder="Filter…" />
              </div>
              <div class="panel-body">
                <div class="list" id="exp-list"></div>
              </div>
            </div>
          </div>

          <div class="panel" style="box-shadow:none;background:transparent;border:0">
            <div class="stack">
              <div class="cardx">
                <div class="cap">Vision (CPOM-safe)</div>
                <div class="body" id="exp-vision"></div>
              </div>
              <div class="cardx">
                <div class="cap">Read</div>
                <div class="body doc-body" id="exp-read">(select a file)</div>
              </div>
              <div class="cardx" id="exp-raw-card">
                <div class="cap row" style="justify-content:space-between;align-items:center;gap:10px">
                  <span>Raw</span>
                  <span class="row" style="gap:10px">
                    <button class="btn btn-quiet mono" id="exp-copy-raw" type="button">Copy</button>
                    <a class="btn" id="exp-open-raw" href="#" target="_blank" rel="noreferrer">Open raw</a>
                  </span>
                </div>
                <div class="body" id="exp-raw"></div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  `;
}

export async function renderExplorer(ctx) {
  const { root, route, getState, setChrome, navigate, isActive, shared } = ctx;
  setChrome({ sub: "Explorer", routeKey: "open", showRun: false });

  const wantPath = route.q.get("path") || "";
  const wantSel = route.q.get("sel") || "";

  root.innerHTML = `
    <section class="panel">
      <div class="panel-title">Explorer</div>
      <div class="panel-body">
        <div class="row" style="justify-content:space-between;align-items:center;gap:12px">
          <div class="skeleton" style="width:52%;height:18px"></div>
          <div class="skeleton" style="width:160px;height:34px"></div>
        </div>
        <div style="height:12px"></div>
        <div class="grid2">
          <div class="skeleton" style="height:320px"></div>
          <div class="skeleton" style="height:320px"></div>
        </div>
      </div>
    </section>
  `;

  let fsDir = null;
  let entries = [];
  let topic = "tour_readme";
  let uxByAud = { laymen: null, technical: null };
  let selRel = "";
  let selRaw = "";
  let selIsText = false;

  // DOM refs (populated after template mount)
  let elTitle = null;
  let elMeta = null;
  let elVision = null;
  let elList = null;
  let elFilter = null;
  let elRead = null;
  let elRawCard = null;
  let elRaw = null;
  let aOpenRaw = null;
  let btnCopyRaw = null;
  let btnCopyPath = null;

  function rawCardHidden(aud, lens) {
    return aud !== "technical" || lens === "uiux";
  }

  async function ensureUx(aud) {
    const a = clampAudience(aud);
    if (uxByAud[a]) return uxByAud[a];
    const uxKey = `${a}:${topic}`;
    let ux = shared && shared.uxByKey ? shared.uxByKey.get(uxKey) : null;
    if (!ux) {
      ux = await fetchJSON(`/api/ux?topic=${encodeURIComponent(topic)}&audience=${encodeURIComponent(a)}`, { timeoutMs: 2500, ttlMs: 60000 });
      try {
        if (shared && shared.uxByKey) shared.uxByKey.set(uxKey, ux);
      } catch (_) {}
    }
    uxByAud[a] = ux;
    return ux;
  }

  function renderList() {
    const ft = String(elFilter && elFilter.value ? elFilter.value : "").trim().toLowerCase();
    const shown = entries.filter((e) => (!ft ? true : String(e.name || "").toLowerCase().includes(ft)));
    if (!shown.length) {
      elList.innerHTML = `<div class="muted mono">No matches.</div>`;
      return;
    }
    elList.innerHTML = shown
      .map((e) => {
        const rel = e.rel || "";
        const meta2 = e.kind === "dir" ? "dir" : `${humanSize(e.size)} ${e.mtime || ""}`.trim();
        const active = rel && rel === selRel ? "active" : "";
        return `
          <button class="item ${active}" type="button" data-rel="${safeText(rel)}" data-kind="${safeText(e.kind)}">
            <span class="ico ${safeText(icon(e))}"></span>
            <span class="nm">${safeText(e.name || "")}</span>
            <span class="mt mono">${safeText(meta2)}</span>
          </button>
        `;
      })
      .join("");
  }

  function renderPreviewFromSelection() {
    const st = getState();
    const aud = clampAudience(st.audience);
    const lens = clampLens(st.lens);

    // Vision block
    const ux = uxByAud[aud];
    if (elVision) elVision.innerHTML = String((ux && ux.uiux_html) || "");

    // Raw card visibility
    const hideRaw = rawCardHidden(aud, lens);
    if (elRawCard) elRawCard.style.display = hideRaw ? "none" : "";

    if (!selRel) {
      if (elRead) elRead.innerHTML = "(select a file)";
      if (elRaw) elRaw.innerHTML = "";
      return;
    }

    if (aud === "laymen" && !selIsText) {
      if (elRead) {
        elRead.innerHTML = `
          <div class="callout">
            <b>Implementation file.</b>
            <div class="muted" style="margin-top:6px">In laymen mode we don’t render raw code/config in the Explorer.</div>
            <div style="height:10px"></div>
            <a class="btn btn-primary" href="/doc?path=${encodeURIComponent(selRel)}&audience=technical&lens=split" data-nav>Open technical</a>
          </div>
        `;
      }
    } else {
      const baseDir = selRel.includes("/") ? selRel.split("/").slice(0, -1).join("/") : "";
      const cleaned = aud === "laymen" && selIsText ? redactMarkdownForLaymen(selRaw) : selRaw;
      if (elRead) elRead.innerHTML = selIsText ? renderMarkdown(cleaned, { audience: aud, baseDir }) : `<pre class="pre mono">${escapeHtml(selRaw)}</pre>`;
    }

    if (aOpenRaw) aOpenRaw.href = `/api/open?path=${encodeURIComponent(selRel)}`;
    if (!hideRaw && elRaw) elRaw.innerHTML = `<pre class="pre mono">${escapeHtml(selRaw)}</pre>`;
  }

  async function preview(rel) {
    if (!rel) return;
    const it = entries.find((x) => x.rel === rel);
    if (!it || it.kind !== "file") return;

    // Persist selection (replaceState) without triggering a rerender.
    const u = new URL(window.location.href);
    u.searchParams.set("sel", rel);
    window.history.replaceState({}, "", u.toString());

    selRel = rel;
    selIsText = /\.md$/i.test(rel) || /\.txt$/i.test(rel);

    const relKey = String(rel || "");
    let raw = shared && shared.textByPath ? shared.textByPath.get(relKey) : null;
    if (raw == null) {
      raw = await fetchText(`/api/open?path=${encodeURIComponent(rel)}`, { timeoutMs: 5000, ttlMs: 30000 });
      try {
        if (shared && shared.textByPath) shared.textByPath.set(relKey, raw);
      } catch (_) {}
    }
    if (!isActive()) return;
    selRaw = String(raw || "");

    renderList();
    renderPreviewFromSelection();
  }

  const onInput = () => renderList();

  const onClick = async (e) => {
    const t = e.target;
    if (!t || !t.closest) return;

    const item = t.closest(".item");
    if (item && elList && elList.contains(item)) {
      const rel = item.getAttribute("data-rel") || "";
      const kind = item.getAttribute("data-kind") || "";
      if (kind === "dir") {
        navigate(`/open?path=${encodeURIComponent(rel)}`);
        return;
      }
      await preview(rel);
      return;
    }

    if (t.closest("#exp-copy-path")) {
      e.preventDefault();
      if (!btnCopyPath) return;
      await copyText((fsDir && fsDir.path) || "");
      btnCopyPath.textContent = "Copied";
      window.setTimeout(() => (btnCopyPath.textContent = "Copy path"), 900);
      return;
    }

    if (t.closest("#exp-copy-raw")) {
      e.preventDefault();
      const st = getState();
      if (clampAudience(st.audience) !== "technical") return;
      if (!btnCopyRaw) return;
      await copyText(selRaw);
      btnCopyRaw.textContent = "Copied";
      window.setTimeout(() => (btnCopyRaw.textContent = "Copy"), 900);
      return;
    }
  };

  try {
    const wantKey = String(wantPath || "");
    let fs0 = shared && shared.fsByPath ? shared.fsByPath.get(wantKey) : null;
    if (!fs0) {
      fs0 = await fetchJSON(`/api/fs?path=${encodeURIComponent(wantPath)}`, { timeoutMs: 2500, ttlMs: 10000 });
      try {
        if (shared && shared.fsByPath) shared.fsByPath.set(wantKey, fs0);
      } catch (_) {}
    }
    if (!fs0.ok) throw new Error(fs0.error || "fs error");

    const isFile = fs0.kind === "file";
    const dirPath = isFile ? String(wantPath || "").replace(/\/[^/]+$/, "") : wantPath;
    selRel = wantSel || (isFile ? fs0.path || "" : "");

    const dirKey = String(dirPath || "");
    fsDir = shared && shared.fsByPath ? shared.fsByPath.get(dirKey) : null;
    if (!fsDir) {
      fsDir = await fetchJSON(`/api/fs?path=${encodeURIComponent(dirPath)}`, { timeoutMs: 2500, ttlMs: 10000 });
      try {
        if (shared && shared.fsByPath) shared.fsByPath.set(dirKey, fsDir);
      } catch (_) {}
    }
    if (!fsDir.ok) throw new Error(fsDir.error || "fs error");
    if (fsDir.kind !== "dir") throw new Error("expected directory");
    if (!isActive()) return () => {};

    entries = (fsDir.entries || []).slice();
    topic = topicForPath(fsDir.path || dirPath || "");

    // Mount stable DOM.
    root.innerHTML = template();
    elTitle = root.querySelector("#exp-title");
    elMeta = root.querySelector("#exp-meta");
    elVision = root.querySelector("#exp-vision");
    elList = root.querySelector("#exp-list");
    elFilter = root.querySelector("#exp-filter");
    elRead = root.querySelector("#exp-read");
    elRawCard = root.querySelector("#exp-raw-card");
    elRaw = root.querySelector("#exp-raw");
    aOpenRaw = root.querySelector("#exp-open-raw");
    btnCopyRaw = root.querySelector("#exp-copy-raw");
    btnCopyPath = root.querySelector("#exp-copy-path");

    const crumbs = (fsDir.path || dirPath || "").replace(/^\/+/, "");
    const meta = `${entries.length} items`;
    if (elTitle) elTitle.textContent = crumbs || "(repo root)";
    if (elMeta) {
      const st = getState();
      const aud = clampAudience(st.audience);
      const lens = clampLens(st.lens);
      elMeta.textContent = `topic=${topic} | audience=${aud} | lens=${lens} | ${meta}`;
    }

    // Warm UX for current audience.
    const st0 = getState();
    await ensureUx(st0.audience);
    if (!isActive()) return () => {};

    if (elFilter) elFilter.addEventListener("input", onInput);
    root.addEventListener("click", onClick);

    renderList();

    // Auto preview
    const chosen =
      selRel ? entries.find((e) => e.rel === selRel) : entries.find((e) => e.kind === "file" && /\.md$/i.test(e.name || "")) || entries.find((e) => e.kind === "file");
    if (chosen && chosen.rel) await preview(chosen.rel);
    renderPreviewFromSelection();
  } catch (e) {
    if (!isActive()) return () => {};
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Explorer Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load explorer.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
          </div>
        </div>
      </section>
    `;
  }

  const cleanup = () => {
    try {
      if (elFilter) elFilter.removeEventListener("input", onInput);
    } catch (_) {}
    try {
      root.removeEventListener("click", onClick);
    } catch (_) {}
  };

  cleanup.update = async (prev, next) => {
    // Update meta, UX, and preview rendering without remounting (prevents scroll reset).
    try {
      const aud = clampAudience(next.audience);
      if (!uxByAud[aud]) await ensureUx(aud);
    } catch (_) {}

    if (elMeta) {
      const aud = clampAudience(next.audience);
      const lens = clampLens(next.lens);
      const meta2 = `${entries.length} items`;
      elMeta.textContent = `topic=${topic} | audience=${aud} | lens=${lens} | ${meta2}`;
    }
    renderPreviewFromSelection();
  };

  return cleanup;
}

