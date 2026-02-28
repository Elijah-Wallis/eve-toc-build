function qs(id) {
  return document.getElementById(id);
}

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function score(query, text) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return 1;
  const t = String(text || "").toLowerCase();
  if (!t) return -1;
  if (t === q) return 1000;
  if (t.startsWith(q)) return 800 - t.length;
  const idx = t.indexOf(q);
  if (idx >= 0) return 500 - idx * 8 - t.length * 0.2;
  // weak fuzzy: all chars in order
  let j = 0;
  for (let i = 0; i < t.length && j < q.length; i++) if (t[i] === q[j]) j++;
  if (j === q.length) return 120 - t.length * 0.2;
  return -1;
}

export function initPalette(opts) {
  const o = opts || {};
  const el = qs("palette");
  const input = qs("palette-input");
  const list = qs("palette-list");
  const foot = qs("palette-foot");

  if (!el || !input || !list) throw new Error("palette DOM missing");

  let open = false;
  let staticItems = [];
  let dynamicItems = [];
  let activeIdx = 0;
  let lastQuery = "";
  let debounceId = null;

  function setItems(items) {
    staticItems = Array.isArray(items) ? items.slice() : [];
  }

  function currentItems(query) {
    const q = String(query || "").trim();
    const all = staticItems.concat(dynamicItems);
    const rows = all
      .map((it) => {
        const s = Math.max(score(q, it.title), score(q, it.subtitle));
        return { it, s };
      })
      .filter((r) => r.s >= 0)
      .sort((a, b) => b.s - a.s)
      .map((r) => r.it);
    return rows.slice(0, 42);
  }

  function render() {
    const q = String(input.value || "");
    const items = currentItems(q);
    activeIdx = clamp(activeIdx, 0, Math.max(0, items.length - 1));

    // Group by section.
    const by = {};
    for (const it of items) {
      const g = it.group || "Actions";
      if (!by[g]) by[g] = [];
      by[g].push(it);
    }

    const parts = [];
    const groups = Object.keys(by);
    groups.sort((a, b) => a.localeCompare(b));

    let idx = 0;
    for (const g of groups) {
      parts.push(`<div class="pgroup">${safeText(g)}</div>`);
      for (const it of by[g]) {
        const active = idx === activeIdx ? "active" : "";
        parts.push(
          `<div class="pitem ${active}" data-idx="${idx}">` +
            `<div>` +
            `<div class="t">${safeText(it.title || "")}</div>` +
            (it.subtitle ? `<div class="s">${safeText(it.subtitle || "")}</div>` : "") +
            `</div>` +
            (it.key ? `<div class="k mono">${safeText(it.key)}</div>` : `<div class="k mono"></div>`) +
            `</div>`
        );
        idx++;
      }
    }

    list.innerHTML = parts.join("");
    Array.from(list.querySelectorAll(".pitem")).forEach((row) => {
      row.addEventListener("mousemove", () => {
        const n = Number(row.dataset.idx || "0");
        activeIdx = Number.isFinite(n) ? n : 0;
        render();
      });
      row.addEventListener("click", async () => {
        const n = Number(row.dataset.idx || "0");
        const items2 = currentItems(input.value || "");
        const it = items2[n];
        if (!it) return;
        await pick(it);
      });
    });
  }

  async function pick(item) {
    close();
    try {
      if (o.onPick) await o.onPick(item);
    } catch (e) {
      // Ignore palette action errors; main UI should render errors where relevant.
      if (foot) foot.textContent = `Action failed: ${e && e.message ? e.message : e}`;
    }
  }

  function close() {
    open = false;
    el.hidden = true;
    input.value = "";
    dynamicItems = [];
    activeIdx = 0;
    lastQuery = "";
  }

  function show() {
    open = true;
    el.hidden = false;
    window.setTimeout(() => input.focus(), 0);
    render();
  }

  function toggle() {
    if (open) close();
    else show();
  }

  function onKeyDown(e) {
    if (!open) {
      const isK = (e.key || "").toLowerCase() === "k";
      if ((e.metaKey || e.ctrlKey) && isK) {
        e.preventDefault();
        show();
      }
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIdx += 1;
      render();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIdx -= 1;
      render();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const items = currentItems(input.value || "");
      const it = items[activeIdx];
      if (it) pick(it);
      return;
    }
  }

  function scheduleQuery() {
    if (debounceId != null) window.clearTimeout(debounceId);
    debounceId = window.setTimeout(async () => {
      debounceId = null;
      const q = String(input.value || "").trim();
      if (q === lastQuery) return;
      lastQuery = q;
      if (!q || q.length < 2) {
        dynamicItems = [];
        render();
        return;
      }
      if (!o.onQuery) return;
      try {
        const items = await o.onQuery(q);
        dynamicItems = Array.isArray(items) ? items : [];
      } catch (_) {
        dynamicItems = [];
      }
      activeIdx = 0;
      render();
    }, 140);
  }

  // Events
  window.addEventListener("keydown", onKeyDown);
  input.addEventListener("input", scheduleQuery);
  el.addEventListener("click", (e) => {
    const t = e.target;
    if (t && t.hasAttribute && t.hasAttribute("data-palette-close")) close();
  });

  return { setItems, open: show, close, toggle, render };
}

