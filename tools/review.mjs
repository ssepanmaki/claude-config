// Lead review harness: shoots local pages at the sizes that best show them, so a review never relies on thumbnails.
// node review.mjs <url | @routes.txt> <out_dir> [--sel "css"]... [--js "expr"]... [--only phone|desk] [--size WxH] [--light] [--wait ms]
//   @routes.txt: one "slug url" per line (# comments ok); one Edge, one sign-in, a subfolder + sheet per route.
//   Always: phone 390x844 and desk 1280x860 viewport shots (the app's two layouts, split at 1024px).
//   Each --sel: a 2x crop of that element (24px margin) at each size where it is visible, for details.
//   --js runs in order after load (awaited, 400ms apart), e.g. to open a sheet before shooting.
// Waits until the page is settled (no in-flight fetch/XHR for 600ms, no visible spinner/skeleton/aria-busy), max 20s;
//   a shot taken unsettled is flagged UNSETTLED and the run exits 3, so a loading screen never passes as a review.
// Audits each shot: truncated text (ellipsis/clipped), horizontal page overflow, text under 11px, console/HTTP errors.
//   One line per shot on stdout; full detail in <slug>-audit.json.
// Verdict per shot, so nobody looks at a screen to find these: FAIL on a truncated heading/label/button, controls that
//   partly overlap, a squeezed text field, a native <select>, a control clipped by its container, a raw i18n key,
//   a broken image, a blank page, horizontal overflow or a console/HTTP error. --allow and --ignore accept intended cases.
// Each shot has a layout fingerprint. --approve records the passing ones after a look; a later run reports them
//   "same as approved" and they need no second look. Look only at PASS shots that are new or changed.
// Signs in through the dev door (/auth/dev) on its own profile, or with --cookie. Local URLs only.
// Prints the contact sheet path per route (~1000px JPEG, <200KB when feasible); full-size JPEGs (q80, each <=150KB) stay in out_dir.
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";

const a = process.argv.slice(2);
if (a.includes("--help") || a.includes("-h")) {
  console.log(`review.mjs <url | @routes.txt> <out_dir> [flags]
  <url>        local page (http://localhost|127.0.0.1:PORT/...); signs in via /auth/dev
  @routes.txt  batch: "slug url" per line; out_dir/<slug>/ per route, one browser
  <out_dir>    where JPEGs (each <=150KB), audits and contact sheets go
  --sel CSS    extra 2x crop of that element (repeatable)
  --js EXPR    run after load, in order, awaited, 400ms apart (repeatable)
  --only phone|desk   one layout instead of both (phone 390x844, desk 1280x860)
  --size WxH   one custom viewport instead of phone + desk
  --light      light scheme (default dark)
  --wait MS    extra wait after the page settles (default 500)
  --cookie STR sign in with "name=value; name2=value2" (or REVIEW_COOKIE) instead of /auth/dev
  --allow LIST checks that may not fail the shot: headtrunc,overlap,squeezed,native,clipped,rawkeys,brokenimg,blank,overflow,errors
  --ignore TXT drop findings containing TXT, for a known intended case (repeatable)
  --approve    record the passing shots as looked-at in <out_dir>/review-state.json
  --help       this text
stdout per shot: PASS or FAIL with the failed checks, and new | CHANGED since approved | same as approved.
Last line: how many to fix, how many to look at once, how many to skip. Look only at PASS shots that are not "same as approved".
Exit 3 = a shot was unsettled, 4 = a check failed. Browser: Edge on Windows, else Playwright's chrome-headless-shell (REVIEW_BROWSER overrides).`);
  process.exit(0);
}
const [target, outRoot] = a;
if (!target || !outRoot) { console.error("usage: review.mjs <url | @routes.txt> <out_dir> [--sel css]... [--js expr]... [--only phone|desk] [--size WxH] [--light] [--wait ms]"); process.exit(2); }
const slugOf = (u) => new URL(u).pathname.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "home";
const routes = target.startsWith("@")
  ? readFileSync(target.slice(1), "utf8").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#")).map((l) => {
      const [s, u] = l.split(/\s+/);
      return u ? { slug: s, url: u, dir: join(outRoot, s) } : { slug: slugOf(s), url: s, dir: join(outRoot, slugOf(s)) };
    })
  : [{ slug: slugOf(target), url: target, dir: outRoot }];
if (!routes.length) { console.error("no routes"); process.exit(2); }
const origin = new URL(routes[0].url).origin;
for (const r of routes) if (new URL(r.url).origin !== origin || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin)) { console.error(`local URLs on one origin only: ${r.url}`); process.exit(2); }
const sels = [], js = [];
let only = null, size = null, scheme = "dark", wait = 500, cookie = process.env.REVIEW_COOKIE ?? "", approve = false;
const allow = new Set(), ignore = [];
for (let i = 2; i < a.length; i++) {
  if (a[i] === "--sel") sels.push(a[++i]);
  else if (a[i] === "--cookie") cookie = a[++i];
  else if (a[i] === "--allow") a[++i].split(",").forEach((c) => allow.add(c.trim()));
  else if (a[i] === "--approve") approve = true;
  else if (a[i] === "--ignore") ignore.push(a[++i].toLowerCase());
  else if (a[i] === "--js") js.push(a[++i]);
  else if (a[i] === "--only") only = a[++i];
  else if (a[i] === "--size") size = a[++i];
  else if (a[i] === "--light") scheme = "light";
  else if (a[i] === "--wait") wait = Number(a[++i]);
}
const SIZES = { phone: [390, 844], desk: [1280, 860] };
const wh = size && /^(\d{2,5})x(\d{2,5})$/i.exec(size);
if (size && !wh) { console.error("--size wants WxH, e.g. 820x1000"); process.exit(2); }
const sizes = wh ? [[size, [Number(wh[1]), Number(wh[2])]]] : Object.entries(SIZES).filter(([k]) => !only || k === only);

function browser() {
  if (process.env.REVIEW_BROWSER) return process.env.REVIEW_BROWSER;
  if (process.platform === "win32") return "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
  try {
    const base = join(homedir(), ".cache/ms-playwright");
    const d = readdirSync(base).filter((x) => x.startsWith("chromium_headless_shell")).sort().pop();
    const inner = readdirSync(join(base, d)).find((x) => x.startsWith("chrome"));
    return join(base, d, inner, "chrome-headless-shell");
  } catch {}
  for (const b of ["google-chrome", "chromium", "chromium-browser", "microsoft-edge"]) if (spawnSync("which", [b]).status === 0) return b;
  console.error("no browser: set REVIEW_BROWSER"); process.exit(2);
}
const edge = browser();
const PY = process.platform === "win32" ? "python" : "python3";
const port = 9800 + Math.floor(Math.random() * 400);
// one profile per run: a shared profile makes a second Edge hand off to the first and exit without a debug port
const prof = process.env.SHOT_PROFILE ?? `${homedir()}/.claude/tools/.shot-review-${port}`;
const p = spawn(edge, [...(edge.includes("headless-shell") ? [] : ["--headless=new"]), ...(process.platform === "win32" ? [] : ["--no-sandbox"]), "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${prof}`, `--remote-debugging-port=${port}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function killEdge() {
  // p.kill() leaves Edge's renderer/GPU children alive on Windows; kill the whole tree
  if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(p.pid), "/T", "/F"], { stdio: "ignore" });
  else p.kill();
}
const maxS = Number(process.env.REVIEW_MAX_S ?? 150) * routes.length;
setTimeout(() => { console.error(`review.mjs: gave up after ${maxS}s`); killEdge(); process.exit(124); }, maxS * 1000).unref();
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (targets.find((t) => t.type === "page")) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map();
// in-flight requests (long-lived streams excluded) and errors of the current shot
const inflight = new Map(); let lastNet = Date.now(); let logs = [];
const LONG = new Set(["EventSource", "WebSocket", "Ping"]);
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); return; }
  const P = d.params;
  if (d.method === "Network.requestWillBeSent" && !LONG.has(P.type)) { inflight.set(P.requestId, [P.request.url, Date.now()]); lastNet = Date.now(); }
  else if (d.method === "Network.loadingFinished" || d.method === "Network.loadingFailed") {
    if (inflight.delete(P.requestId)) lastNet = Date.now();
    if (d.method === "Network.loadingFailed" && !P.canceled) logs.push(`net failed: ${P.errorText}`);
  }
  else if (d.method === "Network.responseReceived" && P.response.status >= 400) logs.push(`HTTP ${P.response.status} ${P.response.url.replace(origin, "")}`);
  else if (d.method === "Runtime.consoleAPICalled" && P.type === "error") logs.push(`console: ${P.args.map((x) => x.value ?? x.description ?? "").join(" ").slice(0, 200)}`);
  else if (d.method === "Runtime.exceptionThrown") logs.push(`exception: ${(P.exceptionDetails.exception?.description ?? P.exceptionDetails.text).split("\n")[0].slice(0, 200)}`);
};
const send = (method, params = {}, ms = 0) => new Promise((r, j) => {
  const n = ++id; pend.set(n, r); ws.send(JSON.stringify({ id: n, method, params }));
  if (ms) setTimeout(() => { if (pend.delete(n)) j(new Error(`${method} timed out`)); }, ms);
});
const capture = async (params) => { try { return await send("Page.captureScreenshot", params, 15000); } catch { await sleep(500); return await send("Page.captureScreenshot", params, 15000); } };
const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result;
const LOADERS = `[aria-busy="true"],.animate-spin,.animate-pulse,[data-slot="skeleton"],[class*="skeleton" i],[class*="spinner" i],[data-loading="true"]`;
const loadersJs = `[...document.querySelectorAll(${JSON.stringify(LOADERS)})].filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.bottom > 0 && b.top < innerHeight; }).length`;
async function settle() {
  const t0 = Date.now(); let loaders = 0;
  // a request open >5s is a stream or a lost event (Vite deps, HMR), not loading data
  const live = () => [...inflight.values()].filter(([, t]) => Date.now() - t < 5000);
  while (Date.now() - t0 < 20000) {
    loaders = (await evaluate(loadersJs)).result?.value ?? 0;
    if (!live().length && Date.now() - lastNet > 600 && !loaders) return { ok: true, ms: Date.now() - t0 };
    await sleep(250);
  }
  return { ok: false, loaders, requests: live().map(([u]) => u.replace(origin, "")).slice(0, 5) };
}
// layout audit, run in the page
const auditJs = `(() => {
  // visible to a reader: not sr-only (1px/clipped), not aria-hidden, not transparent
  const vis = (e) => { const b = e.getBoundingClientRect(); if (b.width < 4 || b.height < 4 || e.closest('[aria-hidden="true"],[inert],.sr-only')) return false; const s = getComputedStyle(e); return s.visibility !== "hidden" && s.opacity !== "0" && s.clip !== "rect(0px, 0px, 0px, 0px)" && s.clipPath !== "inset(50%)"; };
  const own = (e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  const truncated = [], tiny = [];
  for (const e of document.body.querySelectorAll("*")) {
    if (!vis(e)) continue;
    const s = getComputedStyle(e);
    if (own(e) && parseFloat(s.fontSize) < 11) tiny.push(e.textContent.trim().slice(0, 30) + " (" + s.fontSize + ")");
    const clipX = e.scrollWidth > e.clientWidth + 1 && (s.textOverflow === "ellipsis" || s.overflowX === "hidden" || s.overflowX === "clip");
    const clamp = s.webkitLineClamp && s.webkitLineClamp !== "none" && e.scrollHeight > e.clientHeight + 1;
    if ((clipX || clamp) && e.textContent.trim() && e.children.length < 3) truncated.push(e.textContent.trim().replace(/\\s+/g, " ").slice(0, 40));
  }
  const overflowX = document.documentElement.scrollWidth - innerWidth;
  // mechanical defect checks: each list is empty on a healthy screen
  const label = (e) => (e.getAttribute("aria-label") || e.placeholder || e.textContent || e.name || "").trim().replace(/\\s+/g, " ").slice(0, 30) || e.tagName.toLowerCase();
  const headtrunc = [];
  for (const e of document.body.querySelectorAll("*")) {
    if (!vis(e) || !e.textContent.trim() || e.children.length >= 3) continue;
    const s = getComputedStyle(e);
    const cut = (e.scrollWidth > e.clientWidth + 1 && (s.textOverflow === "ellipsis" || s.overflowX === "hidden" || s.overflowX === "clip")) || (s.webkitLineClamp && s.webkitLineClamp !== "none" && e.scrollHeight > e.clientHeight + 1);
    if (cut && e.closest('h1,h2,h3,h4,h5,h6,label,button,th,dt,legend,[role="tab"],[data-slot$="title"]')) headtrunc.push(label(e));
  }
  const inter = [...document.querySelectorAll('button,a[href],input,select,textarea,[role="button"],[role="combobox"],[role="tab"],[contenteditable="true"]')].filter(vis);
  const pinned = (e) => { for (let n = e; n && n !== document.body; n = n.parentElement) { const p = getComputedStyle(n).position; if (p === "fixed" || p === "sticky") return n; } return null; };
  const R = inter.map((e) => [e, e.getBoundingClientRect(), pinned(e)]);
  const overlap = [];
  for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++) {
    const [x, a, pa] = R[i], [y, b, pb] = R[j];
    if (pa !== pb || x.contains(y) || y.contains(x)) continue;
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left), iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ix <= 4 || iy <= 4) continue;
    // one sitting wholly inside the other is an adornment (clear button in an input), not a collision
    const inside = (m, n) => m.left >= n.left - 1 && m.right <= n.right + 1 && m.top >= n.top - 1 && m.bottom <= n.bottom + 1;
    if (!inside(a, b) && !inside(b, a)) overlap.push(label(x) + " x " + label(y));
  }
  const squeezed = [], native = [], clipped = [];
  for (const [e, b] of R) {
    const t = e.tagName, ty = (e.getAttribute("type") || "text").toLowerCase();
    if ((t === "TEXTAREA" || e.isContentEditable) && b.width < 160) squeezed.push(label(e) + " (" + Math.round(b.width) + "px)");
    else if (t === "INPUT" && ["text", "search", "email", "url", "password"].includes(ty) && b.width < 48) squeezed.push(label(e) + " (" + Math.round(b.width) + "px)");
    if (t === "SELECT") native.push(label(e.labels?.[0] ?? e));
    for (let n = e.parentElement; n && n !== document.documentElement; n = n.parentElement) {
      const o = getComputedStyle(n).overflowX;
      if (o === "auto" || o === "scroll") break;
      if (o === "hidden" || o === "clip") { const c = n.getBoundingClientRect(); if (b.right > c.right + 4 || b.left < c.left - 4) clipped.push(label(e)); break; }
    }
  }
  const rawkeys = [];
  const EXT = /\\.(com|org|net|io|dev|ai|app|json|tsx?|jsx?|mjs|md|png|jpe?g|svg|csv|pdf|txt|ya?ml|sh|py|html|css)$/i;
  for (const e of document.body.querySelectorAll("*")) {
    if (!own(e) || !vis(e) || e.closest("code,pre,kbd,textarea,input")) continue;
    const t = [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").trim();
    if (/^[a-z][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*){1,4}$/.test(t) && !EXT.test(t)) rawkeys.push(t.slice(0, 40));
  }
  const brokenimg = [...document.images].filter((i) => vis(i) && i.complete && !i.naturalWidth).map((i) => (i.alt || i.src).slice(-40));
  const blank = document.body.innerText.trim().length < 20 ? ["page has under 20 characters of text"] : [];
  // layout fingerprint: same value = same screen, so an approved screen needs no second look
  const fp = [];
  for (const e of document.body.querySelectorAll("*")) {
    if (!vis(e) || !(own(e) || inter.includes(e) || e.tagName === "IMG" || e.tagName === "svg")) continue;
    const b = e.getBoundingClientRect(), q = (n) => Math.round(n / 2) * 2;
    fp.push([e.tagName, q(b.x), q(b.y), q(b.width), q(b.height), own(e) ? e.textContent.trim().slice(0, 60) : ""].join("|"));
  }
  const u = (l) => [...new Set(l)];
  return { truncated: [...new Set(truncated)], tiny: [...new Set(tiny)], overflowX: overflowX > 1 ? overflowX : 0, height: document.documentElement.scrollHeight,
    checks: { headtrunc: u(headtrunc), overlap: u(overlap), squeezed: u(squeezed), native: u(native), clipped: u(clipped), rawkeys: u(rawkeys), brokenimg: u(brokenimg), blank }, fp: fp.join("\\n") };
})()`;
let code = 0;
// approved fingerprints per shot; --approve records the passing ones after someone has looked
const stateFile = join(target.startsWith("@") ? outRoot : join(outRoot, ".."), "review-state.json");
let state = {}; try { state = JSON.parse(readFileSync(stateFile, "utf8")); } catch {}
const next = {}, tally = [];
async function shoot({ slug, url, dir }) {
  mkdirSync(dir, { recursive: true });
  const files = [], audit = {};
  const save = (name, data) => { const f = join(dir, name); writeFileSync(f, Buffer.from(data, "base64")); files.push(f); };
  for (const [size, [w, h]] of sizes) {
    await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 700 });
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
    logs = []; inflight.clear();
    for (let t = 0; t < 2; t++) {
      await send("Page.navigate", { url });
      let ok = false;
      for (let k = 0; k < 40 && !ok; k++) { await sleep(500); ok = (await evaluate("document.readyState")).result?.value === "complete"; }
      if (ok) break;
    }
    // calanque applies the account's theme pref on startup, over prefers-color-scheme
    await evaluate(`document.documentElement.dataset.theme = "${scheme}"`);
    const st = await settle();
    for (const e of js) {
      const r = await evaluate(e);
      if (r?.exceptionDetails) { console.error(`js error (${size}):`, e, r.exceptionDetails.exception?.description); code = code || 1; }
      await sleep(400);
    }
    if (js.length) await settle();
    await sleep(wait);
    await evaluate("document.getAnimations().forEach(a => { if (a.effect?.getTiming().iterations !== Infinity) a.finish(); })");
    await sleep(200);
    const au = (await evaluate(auditJs)).result?.value ?? {};
    const key = `${slug}-${size}-${scheme}`, hash = createHash("sha1").update(au.fp ?? "").digest("hex").slice(0, 16);
    delete au.fp;
    const checks = { ...(au.checks ?? {}), unsettled: st.ok ? [] : ["page never settled"], overflow: au.overflowX ? [`${au.overflowX}px wider than the viewport`] : [], errors: [...new Set(logs)] };
    for (const k in checks) checks[k] = checks[k].filter((t) => !ignore.some((g) => String(t).toLowerCase().includes(g)));
    const fails = Object.entries(checks).filter(([k, v]) => v.length && !allow.has(k));
    const seen = state[key] === hash ? "same as approved" : state[key] ? "CHANGED since approved" : "new";
    const verdict = fails.length ? "FAIL" : "PASS";
    tally.push({ key, verdict, seen, file: join(dir, `${slug}-${size}.jpg`) });
    if (!fails.length) next[key] = hash;
    console.log(`${slug} ${size}: ${verdict}${fails.length ? ` [${fails.map(([k, v]) => `${k} ${v.length}`).join(", ")}]` : ""} · ${seen}`);
    for (const [k, v] of fails) console.log(`    ${k}: ${v.slice(0, 3).map((t) => JSON.stringify(t)).join(", ")}${v.length > 3 ? ` +${v.length - 3}` : ""}`);
    au.verdict = verdict; au.fails = Object.fromEntries(fails); au.hash = hash;
    audit[size] = { settled: st, ...au, logs: [...new Set(logs)] };
    if (!st.ok) code = 3; else if (fails.length) code = code || 4;
    const shot = await capture({ format: "jpeg", quality: 80, clip: { x: 0, y: 0, width: w, height: h, scale: Math.min(1, 1200 / Math.max(w, h)) } });
    save(`${slug}-${size}.jpg`, shot.result.data);
    const tr = au.truncated ?? [], lg = audit[size].logs;
    console.log(`    ${st.ok ? `settled ${st.ms}ms` : `UNSETTLED (${st.loaders} loaders, ${st.requests.length} requests ${st.requests.join(" ")})`} · ${tr.length} truncated${tr.length ? ` (${tr.slice(0, 4).map((t) => JSON.stringify(t)).join(", ")}${tr.length > 4 ? " …" : ""})` : ""} · overflow-x ${au.overflowX ?? "?"}px · ${au.tiny?.length ?? 0} tiny · ${lg.length} errors${lg.length ? ` (${lg.slice(0, 2).join("; ")})` : ""} · page ${au.height}px`);
    for (const [i, sel] of sels.entries()) {
      const r = (await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null; e.scrollIntoView({ block: "center" }); const b = e.getBoundingClientRect(); return b.width && b.height ? [b.x, b.y, b.width, b.height] : null; })()`))?.result?.value;
      if (!r) { console.error(`no visible ${sel} at ${size}`); continue; }
      await sleep(300);
      const m = 24, x = Math.max(0, r[0] - m), y = Math.max(0, r[1] - m);
      const clip = { x, y, width: Math.min(w - x, r[2] + 2 * m), height: Math.min(h - y, r[3] + 2 * m), scale: 2 };
      const crop = await capture({ format: "jpeg", quality: 80, clip, captureBeyondViewport: false });
      save(`${slug}-${size}-sel${i + 1}.jpg`, crop.result.data);
    }
  }
  writeFileSync(join(dir, `${slug}-audit.json`), JSON.stringify({ url, ...audit }, null, 2));
  return files;
}
const done = [];
try {
  await send("Page.enable");
  await send("Network.enable");
  await send("Runtime.enable");
  if (cookie) {
    for (const pair of cookie.split(/;\s*/).filter(Boolean)) { const eq = pair.indexOf("="); await send("Network.setCookie", { name: pair.slice(0, eq), value: pair.slice(eq + 1), domain: new URL(origin).hostname, path: "/" }); }
  } else {
    await send("Page.navigate", { url: `${origin}/auth/dev?today=${new Date().toISOString().slice(0, 10)}` });
    await sleep(1500);
  }
  for (const r of routes) {
    try { done.push([r, await shoot(r)]); } catch (e) { console.log(`${r.slug}: FAILED ${e.message}`); code = code || 1; }
  }
} finally {
  ws.close();
  killEdge();
  // Edge can hold profile files a moment after taskkill; a leftover temp profile is harmless
  if (!process.env.SHOT_PROFILE) try { rmSync(prof, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 }); } catch {}
}
const fit = `
import sys, os
from PIL import Image
for f in sys.argv[1:]:
    im = Image.open(f).convert("RGB")
    while os.path.getsize(f) > 150000 and im.width > 100:
        im = im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.LANCZOS)
        im.save(f, "JPEG", quality=80)
`;
const py = `
import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]
W, H = 1000, 380
ims = [Image.open(f).convert("RGB") for f in files]
ims = [i.resize((max(1, round(i.width * H / i.height)), H), Image.LANCZOS) if i.height > H else i for i in ims]
rows, row, x = [], [], 0
for i in ims:
    if row and x + i.width > W: rows.append(row); row, x = [], 0
    row.append(i); x += i.width + 8
rows.append(row)
sheet = Image.new("RGB", (W, sum(max(i.height for i in r) + 8 for r in rows)), (128, 128, 128))
y = 0
for r in rows:
    x = 0
    for i in r: sheet.paste(i, (x, y)); x += i.width + 8
    y += max(i.height for i in r) + 8
for q in (80, 65, 50, 40):
    sheet.save(out, "JPEG", quality=q)
    if __import__("os").path.getsize(out) < 200000: break
`;
const all = done.flatMap(([, f]) => f);
const pil = spawnSync(PY, ["-I", "-c", "import PIL"], { stdio: "ignore" }).status === 0;
if (!pil) console.error("no Pillow: shots are not shrunk and there is no contact sheet");
if (all.length && pil) spawnSync(PY, ["-I", "-c", fit, ...all], { stdio: ["ignore", "ignore", "inherit"] });
if (routes.length === 1) {
  for (const f of all) console.error(`${f} ${(statSync(f).size / 1024).toFixed(0)} KB`);
  console.error(`crop: node ${process.argv[1].split("\\").join("/")} ${routes[0].url} ${outRoot} --sel "<css>"${only ? ` --only ${only}` : ""}${size ? ` --size ${size}` : ""}`);
}
for (const [r, files] of done) {
  if (!files.length || !pil) continue;
  const sheet = join(r.dir, `${r.slug}-sheet.jpg`);
  const res = spawnSync(PY, ["-I", "-c", py, sheet, ...files], { stdio: ["ignore", "ignore", "inherit"] });
  if (res.status === 0) console.log(sheet); else { console.error("contact sheet failed; full-size files:"); files.forEach((f) => console.log(f)); }
}
const fail = tally.filter((t) => t.verdict === "FAIL"), skip = tally.filter((t) => t.verdict === "PASS" && t.seen === "same as approved"), look = tally.filter((t) => t.verdict === "PASS" && t.seen !== "same as approved");
if (approve) { mkdirSync(outRoot, { recursive: true }); writeFileSync(stateFile, JSON.stringify({ ...state, ...next }, null, 1)); }
console.log(`REVIEW ${tally.length} shots: ${fail.length} FAIL (fix, no need to look), ${look.length} pass but not yet approved (look once${approve ? ", now recorded as approved" : ", then rerun with --approve"}), ${skip.length} unchanged since approved (skip)`);
if (look.length && !approve) console.log(`look: ${look.map((t) => t.file).join(" ")}`);
process.exit(code);
