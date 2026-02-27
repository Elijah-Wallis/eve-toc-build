function escapeHtml(s) {
  return (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function rewriteApiOpen(href, opts) {
  const h = String(href || "").trim();
  if (!h.startsWith("/api/open")) return h;
  const audience = opts && opts.audience === "technical" ? "technical" : "laymen";
  if (audience !== "laymen") return h;
  try {
    const u = new URL(h, window.location.origin);
    const p = u.searchParams.get("path") || "";
    return `/doc?path=${encodeURIComponent(p)}`;
  } catch (_) {
    return h;
  }
}

function resolveRelativeHref(href, baseDir) {
  const raw = String(href || "").trim();
  if (!raw) return "";
  if (raw.startsWith("#")) return raw;
  if (raw.startsWith("http://") || raw.startsWith("https://") || raw.startsWith("/")) return raw;

  const parts = raw.split("#");
  const pathPart = parts[0] || "";
  const hash = parts.length > 1 ? `#${parts.slice(1).join("#")}` : "";

  const base = String(baseDir || "").replace(/^\/+/, "").replace(/\/+$/, "");
  const joined = (base ? `${base}/${pathPart}` : pathPart).replace(/\\/g, "/");

  const segs = joined.split("/").filter((s) => s !== "");
  const out = [];
  for (const s of segs) {
    if (s === ".") continue;
    if (s === "..") {
      out.pop();
      continue;
    }
    out.push(s);
  }
  const rel = out.join("/");
  if (!rel) return hash || "";
  return `/doc?path=${encodeURIComponent(rel)}${hash}`;
}

function safeHref(href, opts) {
  const baseDir = (opts && opts.baseDir) || "";
  const h0 = resolveRelativeHref(href, baseDir);
  const h = rewriteApiOpen(h0, opts);
  if (!h) return "";
  if (h.startsWith("http://") || h.startsWith("https://") || h.startsWith("/") || h.startsWith("#")) return h;
  return "";
}

function inline(mdLine, opts) {
  let s = escapeHtml(mdLine);
  // links: [text](href)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, href) => {
    const u = safeHref(href, opts);
    if (!u) return escapeHtml(text);
    const ext = u.startsWith("http://") || u.startsWith("https://");
    return `<a class="mlink" href="${escapeHtml(u)}" ${ext ? `target="_blank" rel="noreferrer"` : "data-nav"}>${escapeHtml(text)}</a>`;
  });
  // bold + inline code
  s = s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  s = s.replace(/`([^`]+)`/g, "<span class='code'>$1</span>");
  return s;
}

export function renderMarkdown(mdText, opts) {
  const o = opts || {};
  const lines = String(mdText || "").replace(/\r\n/g, "\n").split("\n");
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

    if (line.trim().startsWith("```")) {
      if (!inCode) {
        closeList();
        inCode = true;
        out.push("<pre class='pre mono'><code>");
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

    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      closeList();
      const lvl = h[1].length;
      const text = String(h[2] || "");
      const id = `h-${i}-${lvl}-${text.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 52)}`;
      out.push(`<h${lvl} id="${escapeHtml(id)}" class="mhd">${inline(text, o)}</h${lvl}>`);
      continue;
    }

    const li = line.match(/^\s*[-*]\s+(.*)$/);
    if (li) {
      if (!listOpen) {
        closeList();
        out.push("<ul class='mlist'>");
        listOpen = true;
      }
      out.push(`<li>${inline(li[1], o)}</li>`);
      continue;
    } else {
      closeList();
    }

    const bq = line.match(/^>\s?(.*)$/);
    if (bq) {
      out.push(`<blockquote class="mquote">${inline(bq[1], o)}</blockquote>`);
      continue;
    }

    if (line.trim() === "") {
      out.push("<div style='height:10px'></div>");
      continue;
    }

    out.push(`<p class="mp">${inline(line, o)}</p>`);
  }
  closeList();
  if (inCode) out.push("</code></pre>");
  return out.join("\n");
}

export function extractToc(mdText) {
  const lines = String(mdText || "").replace(/\r\n/g, "\n").split("\n");
  const toc = [];
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,3})\s+(.*)$/);
    if (!m) continue;
    const lvl = m[1].length;
    const text = (m[2] || "").trim();
    const id = `h-${i}-${lvl}-${text.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 52)}`;
    toc.push({ lvl, text, id });
  }
  return toc;
}
