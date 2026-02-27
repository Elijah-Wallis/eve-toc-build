import { fetchJSON } from "../lib/api.mjs";

function safeText(s) {
  return (s == null ? "" : String(s)).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] || c));
}

function clampAudience(a) {
  return a === "technical" ? "technical" : "laymen";
}

function clampLens(l) {
  if (l === "code") return "code";
  if (l === "split") return "split";
  return "uiux";
}

function template(topic) {
  return `
    <section class="panel">
      <div class="panel-title" id="topic-title">${safeText(topic || "Topic")}</div>
      <div class="panel-body">
        <div class="row" style="justify-content:space-between;align-items:center;gap:12px">
          <div class="muted mono" id="topic-meta"></div>
          <div class="row" style="gap:10px;flex-wrap:wrap">
            <a class="btn" href="/deck" data-nav>Open Deck</a>
            <a class="btn" href="/sop" data-nav>Open SOP</a>
          </div>
        </div>
        <div style="height:12px"></div>
        <div id="topic-body"></div>
      </div>
    </section>
  `;
}

function renderCols(lens, uiux, code) {
  if (lens === "split") {
    return `<div class="split">
      <div class="cardx">
        <div class="cap">Vision</div>
        <div class="body">${uiux || ""}</div>
      </div>
      <div class="cardx">
        <div class="cap">Code</div>
        <div class="body">${code || ""}</div>
      </div>
    </div>`;
  }
  if (lens === "code") return `<div class="cardx"><div class="cap">Code</div><div class="body">${code || ""}</div></div>`;
  return `<div class="cardx"><div class="cap">Vision</div><div class="body">${uiux || ""}</div></div>`;
}

export async function renderTopic(ctx) {
  const { root, route, getState, setChrome, isActive, shared } = ctx;
  const topic = route.q.get("topic") || "capabilities_skills";
  setChrome({ sub: "UI/UX vs Code", routeKey: "topic", showRun: false });

  root.innerHTML = template(topic);

  const elTitle = root.querySelector("#topic-title");
  const elMeta = root.querySelector("#topic-meta");
  const elBody = root.querySelector("#topic-body");

  const byAud = { laymen: null, technical: null };

  async function ensure(aud) {
    const a = clampAudience(aud);
    if (byAud[a]) return byAud[a];
    const uxKey = `${a}:${String(topic).trim().toLowerCase()}`;
    let data = shared && shared.uxByKey ? shared.uxByKey.get(uxKey) : null;
    if (!data) {
      data = await fetchJSON(`/api/ux?topic=${encodeURIComponent(topic)}&audience=${encodeURIComponent(a)}`, { timeoutMs: 2500, ttlMs: 60000 });
      try {
        if (shared && shared.uxByKey) shared.uxByKey.set(uxKey, data);
      } catch (_) {}
    }
    byAud[a] = data;
    return data;
  }

  function renderNow() {
    const st = getState();
    const aud = clampAudience(st.audience);
    const lens = clampLens(st.lens);
    const data = byAud[aud];
    if (!data) return;

    if (elTitle) elTitle.textContent = String(data.title || "Topic");
    if (elMeta) elMeta.textContent = `topic=${safeText(String(data.topic || topic))} | audience=${safeText(aud)} | lens=${safeText(lens)}`;
    const uiux = data.uiux_html || "";
    const code = data.code_html || "";
    if (elBody) elBody.innerHTML = renderCols(lens, uiux, code);
  }

  try {
    const st0 = getState();
    await ensure(st0.audience);
    if (!isActive()) return () => {};
    renderNow();
  } catch (e) {
    if (!isActive()) return () => {};
    root.innerHTML = `
      <section class="panel">
        <div class="panel-title">Topic Error</div>
        <div class="panel-body">
          <div class="callout">
            <b>Could not load topic.</b>
            <div class="muted" style="margin-top:6px">${safeText(e && e.message ? e.message : e)}</div>
          </div>
        </div>
      </section>
    `;
  }

  const cleanup = () => {};

  cleanup.update = async (prev, next) => {
    try {
      const aud = clampAudience(next.audience);
      if (!byAud[aud]) await ensure(aud);
    } catch (_) {}
    renderNow();
  };

  return cleanup;
}

