import { fetchJSON, fetchText } from "../lib/api.mjs";
import { redactMarkdownForLaymen } from "../lib/redaction.mjs";
import { extractToc, renderMarkdown } from "../lib/markdown.mjs";

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

function template(rel) {
  return `
    <section class="panel" id="doc-panel">
      <div class="panel-title" id="doc-title">${safeText(rel || "Document")}</div>
      <div class="panel-body">
        <div class="row" style="justify-content:space-between;align-items:center;gap:12px">
          <div class="muted mono" id="doc-meta">Loading…</div>
          <div class="row" style="gap:10px;flex-wrap:wrap" id="doc-tools">
            <button class="btn btn-quiet mono" id="doc-copy-path" type="button">Copy path</button>
            <button class="btn btn-quiet mono" id="doc-copy-raw" type="button">Copy raw</button>
            <a class="btn" id="doc-open-raw" href="#" target="_blank" rel="noreferrer">Open raw</a>
            <a class="btn" id="doc-open-tech" href="#" data-nav>Open technical</a>
            <a class="btn" id="doc-open-folder" href="#" data-nav>Explore folder</a>
          </div>
        </div>

        <div style="height:12px"></div>
        <div class="doc-grid">
          <aside class="toc">
            <div class="cap">Outline</div>
            <div class="toc-body mono" id="doc-toc">(loading)</div>
          </aside>

          <div class="doc-main">
            <div class="cardx">
              <div class="cap">Vision (CPOM-safe)</div>
              <div class="body" id="doc-vision"></div>
            </div>
            <div style="height:12px"></div>
            <div id="doc-callout"></div>
            <div id="doc-content"></div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function buildReadHtml({ aud, lens, rel, raw, fs, ux }) {
  const isText = /\.md$/i.test(rel) || /\.txt$/i.test(rel);
  const baseDir = rel.includes("/") ? rel.split("/").slice(0, -1).join("/") : "";

  const cleaned = aud === "laymen" && isText ? redactMarkdownForLaymen(raw) : raw;
  const uiuxRead = isText
    ? renderMarkdown(cleaned, { audience: aud, baseDir })
    : aud === "laymen"
      ? `<div class="callout">
           <b>Implementation file.</b>
           <div class="muted" style="margin-top:6px">This is code/config. In laymen mode we don’t render raw implementation.</div>
           <div style="height:10px"></div>
           <a class="btn btn-primary" href="/doc?path=${encodeURIComponent(rel)}&audience=technical&lens=split" data-nav>Open technical</a>
         </div>`
      : `<pre class="pre mono">${escapeHtml(raw)}</pre>`;

  const rawHtml = `<pre class="pre mono">${escapeHtml(raw)}</pre>`;
  const showUiux = lens !== "code";
  const showCode = lens !== "uiux";

  const content =
    lens === "split"
      ? `<div class="split">
          <div class="cardx">
            <div class="cap">UI/UX Read</div>
            <div class="body doc-body">${uiuxRead}</div>
          </div>
          <div class="cardx">
            <div class="cap">Code (Raw)</div>
            <div class="body">${rawHtml}</div>
          </div>
        </div>`
      : showUiux
        ? `<div class="cardx"><div class="cap">UI/UX Read</div><div class="body doc-body">${uiuxRead}</div></div>`
        : `<div class="cardx"><div class="cap">Code (Raw)</div><div class="body">${rawHtml}</div></div>`;

  const toc = isText ? extractToc(cleaned) : [];
  const tocHtml = toc.length
    ? toc.map((t) => `<a class="toc-link lvl${t.lvl}" href="#${safeText(t.id)}" data-id="${safeText(t.id)}">${safeText(t.text)}</a>`).join("")
    : `<div class="muted mono">No headings found.</div>`;

  const callout =
    aud === "laymen"
      ? `<div class="callout" style="margin-bottom:12px"><b>Laymen mode:</b> commands, file paths, and code blocks are hidden by design. Switch to <b>Technical</b> for exact ops.</div>`
      : "";

  const meta = `topic=${topicForPath(rel)} | audience=${aud} | lens=${lens} | size=${safeText(fs.size ?? "n/a")}`;
  const visionHtml = String((ux && ux.uiux_html) || "");

  return { content, tocHtml, callout, meta, visionHtml, cleaned, isText };
}

export async function renderDoc(ctx) {
  const { root, route, getState, setChrome, navigate, isActive, shared } = ctx;
  const rel = route.q.get("path") || "";
  setChrome({ sub: "Document", routeKey: "doc", showRun: false });

  if (!rel) {
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Document</div>
        <div class="panel-body"><div class="muted mono">Missing path.</div></div>
      </section>
    `;
    return () => {};
  }

  root.innerHTML = template(rel);

  const elTitle = root.querySelector("#doc-title");
  const elMeta = root.querySelector("#doc-meta");
  const elToc = root.querySelector("#doc-toc");
  const elVision = root.querySelector("#doc-vision");
  const elCallout = root.querySelector("#doc-callout");
  const elContent = root.querySelector("#doc-content");

  const btnCopyPath = root.querySelector("#doc-copy-path");
  const btnCopyRaw = root.querySelector("#doc-copy-raw");
  const aOpenRaw = root.querySelector("#doc-open-raw");
  const aOpenTech = root.querySelector("#doc-open-tech");
  const aOpenFolder = root.querySelector("#doc-open-folder");

  let fs = null;
  let raw = "";
  let topic = topicForPath(rel);
  let uxByAud = { laymen: null, technical: null };

  function setToolsForAudience(aud) {
    const parent = rel.includes("/") ? rel.split("/").slice(0, -1).join("/") : "";
    const rawHref = `/api/open?path=${encodeURIComponent(rel)}`;
    const techHref = `/doc?path=${encodeURIComponent(rel)}&audience=technical&lens=split`;
    const folderHref = `/open?path=${encodeURIComponent(parent)}`;
    if (aOpenFolder) aOpenFolder.setAttribute("href", folderHref);
    if (aOpenRaw) aOpenRaw.setAttribute("href", rawHref);
    if (aOpenTech) aOpenTech.setAttribute("href", techHref);

    // CPOM separation
    if (aud === "technical") {
      if (btnCopyRaw) btnCopyRaw.style.display = "";
      if (aOpenRaw) aOpenRaw.style.display = "";
      if (aOpenTech) aOpenTech.style.display = "none";
    } else {
      if (btnCopyRaw) btnCopyRaw.style.display = "none";
      if (aOpenRaw) aOpenRaw.style.display = "none";
      if (aOpenTech) aOpenTech.style.display = "";
    }
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

  function renderNow() {
    const st = getState();
    const aud = clampAudience(st.audience);
    const lens = clampLens(st.lens);
    const ux = uxByAud[aud];
    if (!fs) return;

    if (elTitle) elTitle.textContent = rel;
    setToolsForAudience(aud);

    const out = buildReadHtml({ aud, lens, rel, raw, fs, ux });
    if (elMeta) elMeta.textContent = out.meta;
    if (elVision) elVision.innerHTML = out.visionHtml || "";
    if (elCallout) elCallout.innerHTML = out.callout || "";
    if (elToc) elToc.innerHTML = out.tocHtml || "";
    if (elContent) elContent.innerHTML = out.content || "";
  }

  const onClick = async (e) => {
    const t = e.target;
    if (!t || !t.closest) return;

    const tocLink = t.closest("[data-id]");
    if (tocLink) {
      e.preventDefault();
      const id = tocLink.getAttribute("data-id");
      const el = id ? document.getElementById(id) : null;
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (t.closest("#doc-copy-path")) {
      e.preventDefault();
      if (!btnCopyPath) return;
      await copyText(rel);
      btnCopyPath.textContent = "Copied";
      window.setTimeout(() => (btnCopyPath.textContent = "Copy path"), 900);
      return;
    }

    if (t.closest("#doc-copy-raw")) {
      e.preventDefault();
      const st = getState();
      if (clampAudience(st.audience) !== "technical") return;
      if (!btnCopyRaw) return;
      await copyText(raw);
      btnCopyRaw.textContent = "Copied";
      window.setTimeout(() => (btnCopyRaw.textContent = "Copy raw"), 900);
      return;
    }
  };
  root.addEventListener("click", onClick);

  try {
    const fsKey = String(rel || "");
    fs = shared && shared.fsByPath ? shared.fsByPath.get(fsKey) : null;
    if (!fs) {
      fs = await fetchJSON(`/api/fs?path=${encodeURIComponent(rel)}`, { timeoutMs: 2000, ttlMs: 10000 });
      try {
        if (shared && shared.fsByPath) shared.fsByPath.set(fsKey, fs);
      } catch (_) {}
    }
    if (!fs.ok) throw new Error(fs.error || "fs error");
    if (fs.kind !== "file") {
      navigate(`/open?path=${encodeURIComponent(rel)}`);
      return () => root.removeEventListener("click", onClick);
    }

    raw = shared && shared.textByPath ? shared.textByPath.get(fsKey) : null;
    if (raw == null) {
      raw = await fetchText(`/api/open?path=${encodeURIComponent(rel)}`, { timeoutMs: 5000, ttlMs: 30000 });
      try {
        if (shared && shared.textByPath) shared.textByPath.set(fsKey, raw);
      } catch (_) {}
    }
    if (!isActive()) return () => root.removeEventListener("click", onClick);

    // Warm initial UX for current audience.
    const st0 = getState();
    const aud0 = clampAudience(st0.audience);
    await ensureUx(aud0);
    if (!isActive()) return () => root.removeEventListener("click", onClick);

    renderNow();
  } catch (e) {
    if (!isActive()) return () => root.removeEventListener("click", onClick);
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Document Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load document.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
          </div>
        </div>
      </section>
    `;
  }

  const cleanup = () => {
    root.removeEventListener("click", onClick);
  };

  cleanup.update = async (prev, next) => {
    // Audience change might require new UX payload; keep it in-place.
    try {
      const aud = clampAudience(next.audience);
      if (!uxByAud[aud]) await ensureUx(aud);
    } catch (_) {
      // ignore; keep last known UX
    }
    renderNow();
  };

  return cleanup;
}

