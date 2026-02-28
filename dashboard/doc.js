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

function escapeHtml(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function redactMarkdownForLaymen(md) {
  // CPOM separation: remove commands, paths, and code so laymen view stays vision-first.
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

function parseQuery() {
  const u = new URL(window.location.href);
  return {
    path: u.searchParams.get("path") || "",
    audience: u.searchParams.get("audience") || "laymen",
    view: u.searchParams.get("view") || ""
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
  const text = await res.text();
  return text || "";
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
      const text = escapeHtml(h[2]);
      const id = `h-${i}-${lvl}-${text.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 48)}`;
      out.push(`<h${lvl} id="${id}">${text}</h${lvl}>`);
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
    "<div class='callout'><b>Laymen mode:</b> commands, file paths, and code blocks are hidden by design. Switch to <b>Technical</b> to view exact run steps and raw source.</div>";
  if (!cleaned || cleaned.length < 120) {
    return callout + "<div style='height:10px'></div><div class='muted'>This document is primarily a builder artifact.</div>";
  }
  return callout + "<div style='height:10px'></div>" + renderMarkdown(cleaned);
}

function extractToc(md) {
  const lines = String(md || "").replace(/\r\n/g, "\n").split("\n");
  const toc = [];
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,3})\\s+(.*)$/);
    if (!m) continue;
    const lvl = m[1].length;
    const text = m[2].trim();
    const id = `h-${i}-${lvl}-${text.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 48)}`;
    toc.push({ lvl, text, id });
  }
  return toc;
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

function applyView(view) {
  const v = view === "code" ? "code" : view === "split" ? "split" : "uiux";
  const uiux = qs("#card-uiux");
  const code = qs("#card-code");
  const toc = qs("#toc-panel");
  if (uiux) uiux.style.display = v === "code" ? "none" : "block";
  if (code) code.style.display = v === "uiux" ? "none" : "block";
  if (toc) toc.style.display = v === "code" ? "none" : "block";
}

async function load() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const viewRaw = q.view || (audience === "technical" ? "split" : "uiux");
  const view = audience === "laymen" ? "uiux" : viewRaw;

  setActive(".seg-btn[data-audience]", "audience", audience);
  setActive(".seg-btn[data-view]", "view", view);
  applyView(view);

  const fs = await fetchFs(q.path);
  const topic = topicForPath(fs.path || q.path);

  qs("#topic").textContent = `topic=${topic}`;
  qs("#title").textContent = fs.path || q.path || "(document)";
  qs("#meta").textContent = `audience=${audience} | view=${view} | size=${fs.size ?? "n/a"} | mtime=${fs.mtime || "n/a"}`;
  qs("#lede").textContent = "A UI/UX-friendly reading mode that pairs the human story with the raw source of truth.";

  const raw = await fetchRaw(fs.path || q.path);
  qs("#raw").textContent = raw;
  const isMd = (fs.path || q.path || "").toLowerCase().endsWith(".md") || (fs.path || q.path || "").toLowerCase().endsWith(".txt");
  if (audience === "laymen") {
    qs("#uiux").innerHTML = renderLaymenRead(raw, isMd);
  } else {
    qs("#uiux").innerHTML = isMd ? renderMarkdown(raw) : `<pre class="mono pre">${escapeHtml(raw)}</pre>`;
  }

  // TOC
  const toc = extractToc(audience === "laymen" ? redactMarkdownForLaymen(raw) : raw);
  qs("#toc").innerHTML = toc.length
    ? toc
        .map((t) => `<a class="lvl${t.lvl}" href="#${safeText(t.id)}" data-id="${safeText(t.id)}">${safeText(t.text)}</a>`)
        .join("")
    : `<div style="color:rgba(255,255,255,0.62)">No headings found.</div>`;

  qsa("#toc a").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const id = a.dataset.id;
      const el = id ? document.getElementById(id) : null;
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // Vision panel
  try {
    const ux = await fetchUx(topic, audience);
    qs("#vision").innerHTML = audience === "technical" ? ux.code_html : ux.uiux_html;
  } catch (e) {
    qs("#vision").textContent = `Vision load failed: ${e.message}`;
  }

  // Buttons
  const rawLink = qs("#rawlink");
  const explore = qs("#explore");
  if (rawLink) rawLink.href = `/api/open?path=${encodeURIComponent(fs.path || q.path)}`;
  if (explore) {
    const parts = String(fs.path || q.path || "").split("/");
    const parent = parts.length > 1 ? parts.slice(0, -1).join("/") : "";
    explore.href = `/open?path=${encodeURIComponent(parent)}&audience=${encodeURIComponent(audience)}`;
  }

  // CPOM separation: laymen does not get raw links/copy.
  const copyRawBtn = qs("#copy-raw");
  if (audience === "laymen") {
    if (copyRawBtn) copyRawBtn.style.display = "none";
    if (rawLink) {
      rawLink.textContent = "Open Technical";
      rawLink.href = `/doc?path=${encodeURIComponent(fs.path || q.path)}&audience=technical&view=split`;
      rawLink.removeAttribute("target");
      rawLink.removeAttribute("rel");
    }
  } else {
    if (copyRawBtn) copyRawBtn.style.display = "";
    if (rawLink) {
      rawLink.textContent = "Raw";
      rawLink.href = `/api/open?path=${encodeURIComponent(fs.path || q.path)}`;
      rawLink.setAttribute("target", "_blank");
      rawLink.setAttribute("rel", "noreferrer");
    }
  }

  qs("#copy-path").addEventListener("click", async () => {
    await copyText(fs.path || q.path || "");
    qs("#copy-path").textContent = "Copied";
    window.setTimeout(() => (qs("#copy-path").textContent = "Copy Path"), 900);
  });
  if (copyRawBtn && audience !== "laymen") {
    copyRawBtn.addEventListener("click", async () => {
      await copyText(raw);
      copyRawBtn.textContent = "Copied";
      window.setTimeout(() => (copyRawBtn.textContent = "Copy Raw"), 900);
    });
  }
}

function init() {
  const q = parseQuery();
  const audience = q.audience === "technical" ? "technical" : "laymen";
  const view = audience === "laymen" ? "uiux" : q.view || (audience === "technical" ? "split" : "uiux");
  setQuery({ path: q.path || "", audience, view });

  installPointerGlow();
  loadHealthBadge().catch(() => {});

  if (audience === "laymen") {
    qsa(".seg-btn[data-view]").forEach((b) => {
      if (b.dataset.view !== "uiux") b.disabled = true;
    });
  }

  qsa(".seg-btn[data-audience]").forEach((b) => {
    b.addEventListener("click", () => {
      setQuery({ audience: b.dataset.audience, view: parseQuery().view, path: parseQuery().path });
      window.location.reload();
    });
  });
  qsa(".seg-btn[data-view]").forEach((b) => {
    b.addEventListener("click", () => {
      const cur = parseQuery();
      if ((cur.audience || "laymen") !== "technical" && b.dataset.view !== "uiux") {
        setQuery({ view: b.dataset.view, audience: "technical", path: cur.path });
      } else {
        setQuery({ view: b.dataset.view, audience: cur.audience, path: cur.path });
      }
      window.location.reload();
    });
  });

  load().catch((e) => {
    qs("#title").textContent = "Error";
    qs("#lede").textContent = e.message;
  });
}

document.addEventListener("DOMContentLoaded", init);
