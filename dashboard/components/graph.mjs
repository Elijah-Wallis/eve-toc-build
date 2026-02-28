function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function dpr() {
  return Math.max(1, Math.min(2, window.devicePixelRatio || 1));
}

function hashHue(s) {
  const str = String(s || "");
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h % 360;
}

function hex(h, s, l) {
  // hsl to rgba string
  return `hsl(${Math.round(h)}, ${Math.round(s)}%, ${Math.round(l)}%)`;
}

export function mountGraph(container, opts) {
  const o = opts || {};
  const nodesIn = Array.isArray(o.nodes) ? o.nodes : [];
  const edgesIn = Array.isArray(o.edges) ? o.edges : [];
  const onSelect = typeof o.onSelect === "function" ? o.onSelect : null;
  let reducedMotion = o.reducedMotion === true;
  let tooltipTextFn = typeof o.tooltipText === "function" ? o.tooltipText : null;

  const wrap = document.createElement("div");
  wrap.className = "graph";
  wrap.innerHTML = `
    <canvas class="graph-canvas"></canvas>
    <div class="graph-tip" hidden></div>
  `;
  container.appendChild(wrap);

  const canvas = wrap.querySelector("canvas");
  const tip = wrap.querySelector(".graph-tip");
  const ctx = canvas.getContext("2d");

  function cssVar(name, fallback) {
    try {
      const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v || fallback;
    } catch (_) {
      return fallback;
    }
  }

  const byId = {};
  const nodes = nodesIn
    .filter((n) => n && n.id)
    .map((n, idx) => {
      const id = String(n.id);
      const hue = hashHue(id);
      const node = {
        id,
        name: String(n.name || id),
        desc: n.desc || {},
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        r: 18 + Math.min(10, Math.max(0, (String(n.name || "").length - 10) * 0.15)),
        hue,
        idx,
      };
      byId[id] = node;
      return node;
    });

  const edges = edgesIn
    .map((e) => {
      if (!Array.isArray(e) || e.length < 2) return null;
      const a = byId[String(e[0] || "")];
      const b = byId[String(e[1] || "")];
      if (!a || !b) return null;
      return { a, b };
    })
    .filter(Boolean);

  let w = 300;
  let h = 220;
  let raf = null;
  let running = false;
  let settleAt = 0;
  let lastInteractionAt = 0;
  let hovered = null;
  let lastMouse = { x: -1, y: -1 };

  function nowMs() {
    return (typeof performance !== "undefined" && performance.now ? performance.now() : Date.now());
  }

  function startLoop() {
    if (reducedMotion) return;
    if (running) return;
    running = true;
    // Let the graph feel alive briefly, then settle to a static layout.
    settleAt = nowMs() + 7200;
    raf = window.requestAnimationFrame(loop);
  }

  function stopLoop() {
    running = false;
    if (raf != null) window.cancelAnimationFrame(raf);
    raf = null;
  }

  function resize() {
    const rect = wrap.getBoundingClientRect();
    w = Math.max(240, Math.floor(rect.width));
    h = Math.max(220, Math.floor(rect.height));
    const scale = dpr();
    canvas.width = Math.floor(w * scale);
    canvas.height = Math.floor(h * scale);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(scale, 0, 0, scale, 0, 0);

    // initialize positions
    if (nodes.every((n) => n.x === 0 && n.y === 0)) {
      const cx = w / 2;
      const cy = h / 2;
      const ring = Math.min(w, h) * 0.32;
      for (let i = 0; i < nodes.length; i++) {
        const t = (i / Math.max(1, nodes.length)) * Math.PI * 2;
        nodes[i].x = cx + Math.cos(t) * ring + (Math.random() - 0.5) * 22;
        nodes[i].y = cy + Math.sin(t) * ring + (Math.random() - 0.5) * 22;
      }
    }
    draw();
    lastInteractionAt = nowMs();
    // If the container resizes, restart briefly so nodes can re-center.
    if (!reducedMotion) startLoop();
  }

  const ro = new ResizeObserver(resize);
  ro.observe(wrap);

  function findNode(mx, my) {
    let best = null;
    let bestD = Infinity;
    for (const n of nodes) {
      const dx = mx - n.x;
      const dy = my - n.y;
      const d = Math.sqrt(dx * dx + dy * dy);
      const hitR = Math.max(18, n.r);
      if (d <= hitR + 6 && d < bestD) {
        best = n;
        bestD = d;
      }
    }
    return best;
  }

  function showTip(n, mx, my) {
    if (!tip) return;
    if (!n) {
      tip.hidden = true;
      return;
    }
    tip.hidden = false;
    const tt = tooltipTextFn ? tooltipTextFn(n) : "";
    tip.innerHTML = `<div class="t">${safeText(n.name)}</div><div class="s">${safeText(String(tt || ""))}</div>`;
    const pad = 14;
    const tx = clamp(mx + 16, pad, w - pad - 240);
    const ty = clamp(my + 14, pad, h - pad - 120);
    tip.style.left = `${tx}px`;
    tip.style.top = `${ty}px`;
  }

  function onMove(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    lastMouse = { x: mx, y: my };
    const n = findNode(mx, my);
    hovered = n;
    canvas.style.cursor = n ? "pointer" : "default";
    showTip(n, mx, my);
    draw();
    lastInteractionAt = nowMs();
    if (!running) startLoop();
  }

  function onLeave() {
    hovered = null;
    showTip(null, 0, 0);
    canvas.style.cursor = "default";
    draw();
    lastInteractionAt = nowMs();
  }

  function onClick() {
    if (hovered && onSelect) onSelect(hovered);
    lastInteractionAt = nowMs();
    if (!running) startLoop();
  }

  canvas.addEventListener("mousemove", onMove, { passive: true });
  canvas.addEventListener("mouseleave", onLeave, { passive: true });
  canvas.addEventListener("click", onClick);

  function step() {
    if (reducedMotion) return;

    const cx = w / 2;
    const cy = h / 2;

    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const d = Math.sqrt(d2);
        const f = 850 / d2;
        const nx = dx / d;
        const ny = dy / d;
        a.vx -= nx * f;
        a.vy -= ny * f;
        b.vx += nx * f;
        b.vy += ny * f;
      }
    }

    // Springs (edges)
    for (const e of edges) {
      const a = e.a;
      const b = e.b;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const target = 140;
      const k = 0.010;
      const f = (d - target) * k;
      const nx = dx / d;
      const ny = dy / d;
      a.vx += nx * f;
      a.vy += ny * f;
      b.vx -= nx * f;
      b.vy -= ny * f;
    }

    // Centering
    for (const n of nodes) {
      const dx = cx - n.x;
      const dy = cy - n.y;
      n.vx += dx * 0.0007;
      n.vy += dy * 0.0007;
    }

    // Integrate
    for (const n of nodes) {
      n.vx *= 0.88;
      n.vy *= 0.88;
      n.x += n.vx;
      n.y += n.vy;
      n.x = clamp(n.x, 24, w - 24);
      n.y = clamp(n.y, 24, h - 24);
    }
  }

  function draw() {
    const edgeStroke = cssVar("--graph-edge", "rgba(246,248,252,0.10)");
    const labelFill = cssVar("--graph-label", "rgba(246,248,252,0.78)");
    const core = cssVar("--graph-node-core", "rgba(255,255,255,0.92)");
    const glow = cssVar("--graph-node-glow", "rgba(110,231,255,0.22)");
    const stroke = cssVar("--graph-node-stroke", "rgba(246,248,252,0.18)");
    const strokeHot = cssVar("--graph-node-stroke-hot", "rgba(110,231,255,0.55)");

    ctx.clearRect(0, 0, w, h);

    // Edges
    ctx.lineWidth = 1;
    ctx.strokeStyle = edgeStroke;
    for (const e of edges) {
      ctx.beginPath();
      ctx.moveTo(e.a.x, e.a.y);
      ctx.lineTo(e.b.x, e.b.y);
      ctx.stroke();
    }

    // Nodes
    for (const n of nodes) {
      const isHot = hovered && hovered.id === n.id;
      const r = n.r + (isHot ? 3 : 0);

      const g = ctx.createRadialGradient(n.x - r * 0.2, n.y - r * 0.2, 2, n.x, n.y, r);
      g.addColorStop(0, core);
      g.addColorStop(1, glow);

      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = isHot ? strokeHot : stroke;
      ctx.lineWidth = isHot ? 2 : 1;
      ctx.stroke();

      // Label
      ctx.font = "12px " + getComputedStyle(document.documentElement).getPropertyValue("--sans");
      ctx.fillStyle = labelFill;
      ctx.textBaseline = "middle";
      ctx.fillText(n.name, n.x + r + 10, n.y);
    }
  }

  function loop() {
    if (!running) return;
    step();
    draw();
    const t = nowMs();
    const recentlyActive = t - lastInteractionAt < 1400;
    if (t > settleAt && !hovered && !recentlyActive) {
      stopLoop();
      return;
    }
    raf = window.requestAnimationFrame(loop);
  }

  resize();
  if (!reducedMotion) {
    // Defer any simulation work until after first paint.
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => startLoop()));
  }

  const dispose = () => {
    try {
      ro.disconnect();
    } catch (_) {}
    stopLoop();
    canvas.removeEventListener("mousemove", onMove);
    canvas.removeEventListener("mouseleave", onLeave);
    canvas.removeEventListener("click", onClick);
    wrap.remove();
  };

  // Allow the host view to update behavior without remounting (perf).
  dispose.setTooltipText = (fn) => {
    tooltipTextFn = typeof fn === "function" ? fn : null;
    // Re-render tip immediately if visible.
    if (hovered && !tip.hidden) showTip(hovered, lastMouse.x, lastMouse.y);
  };
  dispose.setReducedMotion = (rm) => {
    const next = rm === true;
    if (next === reducedMotion) return;
    reducedMotion = next;
    showTip(null, 0, 0);
    if (reducedMotion) stopLoop();
    else startLoop();
  };

  return dispose;
}
