const TOKENS = [
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
  "workflows_n8n/",
];

const TECH_HEADING = /(run|install|setup|deploy|usage|commands?|cli|env|secrets?|tokens?|workflow|docker|api|http|paths?)/i;

export function isTechnicalLine(line) {
  const lc = String(line || "").trim().toLowerCase();
  if (!lc) return false;
  if (lc.includes("`")) return true;
  if (/^[a-z]:\\/.test(lc)) return true; // windows paths
  return TOKENS.some((t) => lc.includes(t));
}

export function redactMarkdownForLaymen(mdText) {
  const s = String(mdText || "").replace(/\r\n/g, "\n");
  const lines = s.split("\n");
  const out = [];

  let inFence = false;
  for (const raw of lines) {
    const t = raw.trim();

    // Drop fenced blocks entirely.
    if (t.startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;

    if (!t) {
      out.push("");
      continue;
    }

    // Drop headings that are mostly operational.
    const h = t.match(/^(#{1,6})\s+(.*)$/);
    if (h && TECH_HEADING.test(h[2] || "")) continue;

    if (isTechnicalLine(t)) continue;
    if (/^[-*]\s+/.test(t) && /[:/]/.test(t)) continue;

    out.push(raw);
  }

  return out.join("\n").replace(/\n{4,}/g, "\n\n\n").trim();
}

