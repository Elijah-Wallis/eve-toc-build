const mem = new Map(); // url -> {ts, data}

function now() {
  return Date.now();
}

function makeError(message, extra) {
  const e = new Error(message);
  if (extra && typeof extra === "object") Object.assign(e, extra);
  return e;
}

async function fetchWithTimeout(url, opts) {
  const o = opts || {};
  const timeoutMs = Number(o.timeoutMs || 0) || 0;
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const id =
    controller && timeoutMs > 0
      ? window.setTimeout(() => {
          try {
            controller.abort();
          } catch (_) {}
        }, timeoutMs)
      : null;
  try {
    const res = await fetch(url, {
      method: o.method || "GET",
      cache: o.cache || "no-store",
      headers: o.headers || {},
      signal: controller ? controller.signal : undefined,
    });
    return res;
  } catch (err) {
    if (String(err && err.name) === "AbortError") {
      throw makeError("Request timed out", { url, status: 0, timeoutMs });
    }
    throw makeError("Network error", { url, status: 0, cause: err });
  } finally {
    if (id != null) window.clearTimeout(id);
  }
}

export async function fetchJSON(url, opts) {
  const o = opts || {};
  const ttlMs = Number(o.ttlMs || 0) || 0;
  if (ttlMs > 0) {
    const hit = mem.get(url);
    if (hit && now() - hit.ts <= ttlMs) return hit.data;
  }

  const res = await fetchWithTimeout(url, o);
  const text = await res.text();
  if (!res.ok) throw makeError(`HTTP ${res.status}`, { url, status: res.status, body: text });

  let data;
  try {
    data = JSON.parse(text);
  } catch (err) {
    throw makeError("Invalid JSON response", { url, status: res.status, body: text, cause: err });
  }
  if (ttlMs > 0) mem.set(url, { ts: now(), data });
  return data;
}

export async function fetchText(url, opts) {
  const o = opts || {};
  const ttlMs = Number(o.ttlMs || 0) || 0;
  if (ttlMs > 0) {
    const hit = mem.get(url);
    if (hit && now() - hit.ts <= ttlMs) return hit.data;
  }

  const res = await fetchWithTimeout(url, o);
  const text = await res.text();
  if (!res.ok) throw makeError(`HTTP ${res.status}`, { url, status: res.status, body: text });
  if (ttlMs > 0) mem.set(url, { ts: now(), data: text });
  return text;
}
