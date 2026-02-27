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

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function parseQuery() {
  const u = new URL(window.location.href);
  return {
    path: u.searchParams.get("path") || "",
    sel: u.searchParams.get("sel") || "",
    audience: u.searchParams.get("audience") || "laymen",
    mode: u.searchParams.get("mode") || "read"
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

async function loadHealthBadge() {
  try {
    const res = await fetch("/api/health?cached=1", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const ok = data && data.summary ? data.summary.ok : null;
    if (document.body && document.body.dataset) {
      document.body.dataset.health = ok === true ? "good" : ok === false ? "bad" : "unk";
    }
  } catch (_) {}
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

async function fetchFs(path) {
  const res = await fetch(`/api/fs?path=${encodeURIComponent(path || "")}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`fs fetch failed: ${res.status}`);
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "fs error");
  return data;
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

async function fetchRaw(path) {
  const res = await fetch(`/api/open?path=${encodeURIComponent(path)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`raw fetch failed: ${res.status}`);
  const ct = res.headers.get("Content-Type") || "";
  // treat as text; if it's binary, this will look ugly but still safe.
  const text = await res.text();
  return { text, contentType: ct };
}

function humanSize(n) {
  if (n == null) return "";
  const v = Number(n);
  if (!Number.isFinite(v)) return "";
  if (v < 1024) return `${v}B`;
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)}KB`;
  return `${(v / (1024 * 1024)).toFixed(1)}MB`;
}

function crumbsHtml(path, audience) {
  const parts = (path || "").replace(/^\/+/, "").split("/").filter(Boolean);
  const items = [];
  const aud = audience === "technical" ? "technical" : "laymen";
  items.push(`<a href="/open?path=&audience=${encodeURIComponent(aud)}">repo</a>`);
  let acc = "";
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p;
    items.push(
      `<span class="sep">/</span> <a href="/open?path=${encodeURIComponent(acc)}&audience=${encodeURIComponent(aud)}">${safeText(p)}</a>`
    );
  }
  return items.join(" ");
}

function iconClass(entry) {
  if (entry.kind === "dir") return "icon dir";
  const name = (entry.name || "").toLowerCase();
  if (name.endsWith(".md") || name.endsWith(".txt")) return "icon md";
  if (/\.(py|js|ts|sh|sql|json|yaml|yml|toml|css|html)$/.test(name)) return "icon code";
  return "icon file";
}

function renderList(entries, filterText) {
  const el = qs("#list");
  const ft = (filterText || "").trim().toLowerCase();
  const shown = entries.filter((e) => (!ft ? true : (e.name || "").toLowerCase().includes(ft)));
  if (!shown.length) {
    el.innerHTML = `<div class="mono" style="color:rgba(255,255,255,0.62)">No matches.</div>`;
    return;
  }
  el.innerHTML = shown
    .map((e) => {
      const meta = e.kind === "dir" ? "dir" : `${humanSize(e.size)}  ${e.mtime || ""}`.trim();
      return `
        <div class="item" data-rel="${safeText(e.rel || "")}" data-kind="${safeText(e.kind || "")}">
          <div class="${iconClass(e)}"></div>
          <div class="name">${safeText(e.name || "")}</div>
          <div class="meta">${safeText(meta)}</div>
        </div>
      `;
    })
    .join("");
}

function escapeHtml(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function redactMarkdownForLaymen(md) {
  let s = String(md || "").replace(/\r\n/g, "\n");
  s = s.replace(/```[\s\S]*?```/g, "\n\n");

  const lines = s.split("\n");
  const out = [];
  const technicalTokens = [
    "/users/",
    "127.0.0.1",
    "localhost",
    "python3 ",
    "python ",
    "bash ",
    "zsh ",
    "npm ",
    "yarn ",
    "pnpm ",
    "pip ",
    "pip3 ",
    "curl ",
    "wget ",
    "git ",
    "docker ",
    "kubectl ",
    "terraform ",
    "supabase",
    ".env",
    "scripts/",
    "workflows_n8n/"
  ];
  function isTechnicalLine(t) {
    const lc = String(t || "").toLowerCase();
    if (/^[a-z]:\\\\/.test(lc)) return true; // windows paths
    return technicalTokens.some((tok) => lc.includes(tok));
  }
  const technicalHeading = /(run|install|setup|deploy|usage|commands?|cli|env|secrets?|tokens?|workflow|docker|api|http|paths?)/i;

  for (const raw of lines) {
    const t = raw.trim();
    if (!t) {
      out.push("");
      continue;
    }
    if (t.includes("`")) continue;
    if (isTechnicalLine(t)) continue;
    const h = t.match(/^(#{1,6})\\s+(.*)$/);
    if (h && technicalHeading.test(h[2] || "")) continue;
    if (/^[-*]\\s+/.test(t) && (isTechnicalLine(t) || /[:/]/.test(t))) continue;
    out.push(raw);
  }
  return out.join("\n").replace(/\n{4,}/g, "\n\n\n").trim();
}

function renderMarkdown(md) {
  const lines = String(md || "").replace(/\r\n/g, "\n").split("\n");
  let out = [];
  let inCode = false;
  let listOpen = false;

  function closeList() {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.replace(/\t/g, "  ");

    if (line.startsWith("```")) {
      if (!inCode) {
        closeList();
        inCode = true;
        out.push("<pre class='mono pre'><code>");
      } else {
        inCode = false;
        out.push("</code></pre>");
      }
      continue;
    }
    if (inCode) {
      out.push(escapeHtml(raw));
      continue;
    }

    const h = line.match(/^(#{1,3})\\s+(.*)$/);
    if (h) {
      closeList();
      const lvl = h[1].length;
      out.push(`<h${lvl}>${escapeHtml(h[2])}</h${lvl}>`);
      continue;
    }

    const li = line.match(/^\\s*[-*]\\s+(.*)$/);
    if (li) {
      if (!listOpen) {
        closeList();
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${escapeHtml(li[1])}</li>`);
      continue;
    } else {
      closeList();
    }

    const bq = line.match(/^>\\s?(.*)$/);
    if (bq) {
      out.push(`<blockquote>${escapeHtml(bq[1])}</blockquote>`);
      continue;
    }

    if (line.trim() === "") {
      out.push("<div style='height:8px'></div>");
      continue;
    }

    // inline code + bold (very small subset)
    let p = escapeHtml(line);
    p = p.replace(/\\*\\*(.+?)\\*\\*/g, "<b>$1</b>");
    p = p.replace(/`([^`]+)`/g, "<span class='code'>$1</span>");
    out.push(`<p>${p}</p>`);
  }
  if (listOpen) out.push("</ul>");
  if (inCode) out.push("</code></pre>");
  return out.join("\n");
}

function renderLaymenRead(raw, isMd) {
  const cleaned = isMd ? redactMarkdownForLaymen(raw) : "";
  const callout =
    "<div class='callout'><b>Laymen mode:</b> commands, file paths, and code blocks are hidden. Switch to <b>Technical</b> to view raw.</div>";
  if (!cleaned || cleaned.length < 120) return callout;
  return callout + "<div style='height:10px'></div>" + renderMarkdown(cleaned);
}

async function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

async function load() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const modeRaw = q.mode === "raw" ? "raw" : "read";
  const mode = audience === "laymen" ? "read" : modeRaw;

  setActive(".seg-btn[data-audience]", "audience", audience);
  setActive(".seg-btn[data-mode]", "mode", mode);

  const fs0 = await fetchFs(q.path);
  // If user points directly at a file, keep the navigator on the parent directory and select the file.
  const isFile = fs0.kind === "file";
  const dirPath = isFile ? (q.path || "").replace(/\/[^/]+$/, "") : (q.path || "");
  const selPath = q.sel || (isFile ? (fs0.path || "") : "");
  const fs = await fetchFs(dirPath);
  const crumbs = qs("#crumbs");
  const lede = qs("#lede");
  const meta = qs("#meta");
  const focusTag = qs("#focus-tag");

  crumbs.innerHTML = crumbsHtml(fs.path || dirPath || "", audience);

  const topic = topicForPath(fs.path || dirPath || "");
  focusTag.textContent = `topic=${topic}`;

  lede.textContent =
    fs.kind === "dir"
      ? `Browsing ${fs.path || "(repo root)"}`
      : `Viewing ${fs.path || "(file)"}`;

  meta.textContent = fs.kind === "dir" ? `${fs.entries?.length || 0} items` : `size=${humanSize(fs.size)}  mtime=${fs.mtime || ""}`;

  // Vision panel
  const vision = qs("#vision");
  try {
    const ux = await fetchUx(topic, audience);
    vision.innerHTML = audience === "technical" ? ux.code_html : ux.uiux_html;
  } catch (e) {
    vision.textContent = `Vision load failed: ${e.message}`;
  }

  // Navigator list
  const entries = (fs.entries || []).slice();
  const filter = qs("#filter");
  renderList(entries, filter ? filter.value : "");

  // Focus raw defaults
  const readEl = qs("#read");
  const readCard = qs("#read-card");
  const rawEl = qs("#raw");
  const openRaw = qs("#open-raw");
  const copyRaw = qs("#copy-raw");
  const rawCard = qs("#raw-card");
  const modeToggle = qs("#mode-toggle");

  if (readCard) readCard.style.display = mode === "raw" ? "none" : "block";
  if (rawCard) rawCard.style.display = audience === "laymen" ? "none" : "block";
  if (modeToggle) modeToggle.style.display = audience === "laymen" ? "none" : "";

  function clearActive() {
    qsa(".item").forEach((it) => it.classList.remove("active"));
  }

  async function preview(rel) {
    if (!rel) return;
    if (openRaw) {
      openRaw.href =
        audience === "laymen"
          ? `/doc?path=${encodeURIComponent(rel)}&audience=technical&view=split`
          : `/api/open?path=${encodeURIComponent(rel)}`;
    }
    try {
      const r = await fetchRaw(rel);
      const text = r.text || "";
      if (readEl && mode !== "raw") {
        if (audience === "laymen") {
          const isMd = rel.toLowerCase().endsWith(".md") || rel.toLowerCase().endsWith(".txt");
          readEl.innerHTML = renderLaymenRead(text, isMd);
        } else {
          if (rel.toLowerCase().endsWith(".md") || rel.toLowerCase().endsWith(".txt")) readEl.innerHTML = renderMarkdown(text);
          else readEl.innerHTML = `<pre class="mono pre">${escapeHtml(text)}</pre>`;
        }
      }
      if (audience !== "laymen") {
        rawEl.textContent = text;
        copyRaw.onclick = async () => {
          await copyText(text);
          copyRaw.textContent = "Copied";
          window.setTimeout(() => (copyRaw.textContent = "Copy"), 900);
        };
      }
    } catch (e) {
      if (readEl && mode !== "raw") readEl.textContent = `Preview failed: ${e.message}`;
      if (rawEl) rawEl.textContent = `Preview failed: ${e.message}`;
    }
  }

  qsa(".item").forEach((it) => {
    it.addEventListener("click", async () => {
      const kind = it.dataset.kind || "";
      const rel = it.dataset.rel || "";
      clearActive();
      it.classList.add("active");
      if (kind === "dir") {
        window.location.href = `/open?path=${encodeURIComponent(rel)}&audience=${encodeURIComponent(audience)}&mode=${encodeURIComponent(mode)}`;
      } else {
        setQuery({ path: dirPath, sel: rel, audience, mode });
        await preview(rel);
      }
    });
  });

  if (filter) {
    filter.addEventListener("input", () => renderList(entries, filter.value));
  }

  // Copy path
  const copyPath = qs("#copy-path");
  if (copyPath) {
    copyPath.addEventListener("click", async () => {
      await copyText(fs.path || "");
      copyPath.textContent = "Copied";
      window.setTimeout(() => (copyPath.textContent = "Copy Path"), 900);
    });
  }

  // If current URL points to a file, auto-preview it; otherwise preview the first markdown file if available.
  const chosen = selPath
    ? entries.find((e) => e.rel === selPath)
    : entries.find((e) => e.kind === "file" && /\.md$/i.test(e.name || "")) || entries.find((e) => e.kind === "file");
  if (chosen && chosen.rel) {
    clearActive();
    const hit = qsa(".item").find((x) => x.dataset.rel === chosen.rel);
    if (hit) hit.classList.add("active");
    await preview(chosen.rel);
  }
}

function init() {
  const q = parseQuery();
  setQuery({
    path: q.path || "",
    sel: q.sel || "",
    audience: q.audience || "laymen",
    mode: (q.audience || "laymen") === "laymen" ? "read" : q.mode || "read"
  });

  installPointerGlow();
  loadHealthBadge().catch(() => {});

  qsa(".seg-btn[data-audience]").forEach((b) => {
    b.addEventListener("click", async () => {
      setQuery({ audience: b.dataset.audience, mode: parseQuery().mode, path: parseQuery().path });
      window.location.reload();
    });
  });
  qsa(".seg-btn[data-mode]").forEach((b) => {
    b.addEventListener("click", async () => {
      const cur = parseQuery();
      if ((cur.audience || "laymen") !== "technical" && b.dataset.mode === "raw") {
        setQuery({ mode: "raw", audience: "technical", path: cur.path });
      } else {
        setQuery({ mode: b.dataset.mode, audience: cur.audience, path: cur.path });
      }
      window.location.reload();
    });
  });

  load().catch((e) => {
    qs("#lede").textContent = "Error";
    qs("#meta").textContent = e.message;
  });
}

document.addEventListener("DOMContentLoaded", init);
