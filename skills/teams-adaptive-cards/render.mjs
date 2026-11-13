// Loaded on https://adaptivecards.microsoft.com/designer.html from serve.py:
//   const { render } = await import("http://127.0.0.1:8765/.claude/skills/teams-adaptive-cards/render.mjs");
//   await render("teams/strategy-compass/cards/welcome.json", { theme: "dark" });
// `card` is a card object or a path served by serve.py.

const ORIGIN = new URL(import.meta.url).origin;

const DESIGNER_CHUNKS = ["1344", "6060", "5302", "4839"];

async function bundle() {
  if (window.__ac?.teamsConfig) return window.__ac;
  let req;
  window.webpackChunkac_react_tool_app.push([[Symbol()], {}, (r) => { req = r; }]);
  await Promise.all(DESIGNER_CHUNKS.map((id) => req.e(id).catch(() => null)));
  const find = (test) => {
    for (const id of Object.keys(req.m)) {
      try {
        const m = req(id);
        for (const v of [m, ...Object.values(m || {})]) if (test(v)) return v;
      } catch {}
    }
    return null;
  };
  const named = (name) => (v) =>
    (typeof v === "function" || typeof v === "object") && v !== null && (v.displayName === name || v.name === name);
  window.__ac = {
    dom: find((v) => typeof v?.createRoot === "function"),
    react: find((v) => typeof v?.createElement === "function" && typeof v?.useState === "function"),
    card: find((v) => named("AdaptiveCard")(v) && typeof v.prototype?.parse === "function"),
    provider: find(named("FluentProvider")),
    hostConfig: find(named("HostConfig")),
    teamsConfig: find(named("getTeamsWebHostConfig")),
    light: find((v) => v?.colorNeutralBackground1 === "#ffffff" && v?.colorBrandForeground1),
    dark: find((v) => v?.colorNeutralBackground1 === "#292929" && v?.colorBrandForeground1),
  };
  return window.__ac;
}

function holder(theme, width) {
  document.querySelectorAll('[role="dialog"]').forEach((d) => d.remove());
  let overlay = document.getElementById("__ov");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "__ov";
    overlay.innerHTML = '<div id="__holder"></div>';
    document.body.appendChild(overlay);
  }
  overlay.style.cssText = `position:fixed;inset:0;z-index:99999;overflow:auto;padding:16px;background:${theme === "dark" ? "#1f1f1f" : "#f5f5f5"}`;
  const box = document.getElementById("__holder");
  box.style.cssText = `max-width:${width}px;margin:0 auto`;
  return box;
}

async function payload(card) {
  if (typeof card !== "string") return card;
  const response = await fetch(new URL(card, `${ORIGIN}/`), { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} fetching ${card}`);
  return response.json();
}

export async function render(card, { theme = "light", width = 520 } = {}) {
  const ac = await bundle();
  const json = await payload(card);
  const parsed = new ac.card();
  parsed.hostConfig = new ac.hostConfig(ac.teamsConfig(theme === "dark" ? 1 : 0));
  parsed.parse(json);
  const box = holder(theme, width);
  window.__acRoot?.unmount();
  window.__acRoot = ac.dom.createRoot(box);
  window.__acRoot.render(
    ac.react.createElement(ac.provider, { theme: theme === "dark" ? ac.dark : ac.light, style: { borderRadius: 8 } }, parsed.render()),
  );
  await new Promise((r) => setTimeout(r, 800));
  return box.innerText.slice(0, 300);
}
