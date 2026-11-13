// Batch board shooter: one headless Edge, each board loaded once per job entry, every region/slice/probe from that page.
//   node shoot.mjs <job.json | ->            job = one entry or an array of entries (stdin with "-")
//   node shoot.mjs zoom <Board.dc.html>:<W>x<H> <x> <y> <w> <h> <out> [z=2]     (zoom.sh)
//   node shoot.mjs slices <outdir> <Board.dc.html>:<W>x<H>...                    (slices.sh)
//   node shoot.mjs probe <outdir> <Board.dc.html>:<W>x<H>...                     (probe.sh)
// Entry: {board, w, h, scheme:"light"|"dark", dir, shots:[{x,y,w,h,z,out}], slices:bool, probe:bool}
//   board: path to *.dc.html (relative to cwd). w,h: board size in px (the viewport; phones need no frame).
//   shots: board-pixel region, magnified z (default 2), written to out (.png or .jpg).
//   slices: 1340x1052 tiles at 1:1 -> <dir>/<Board>-r<row>-c<col>.png.   probe: <dir>/<Board>.probe.json + .md.
//   dir defaults to the first shot's folder, else ".".
// Env: BOARD_JOB (job name, default pid), BOARD_PUBLIC (default ./public), BOARD_ORIGIN (default http://localhost:5174),
//      BOARD_PALETTE (files whose hex colours make the probe palette), BOARD_PAR (parallel boards, default 4).
// Stdout: "<path> <KB>" per file. Files are <=200KB (PNG quantized then downscaled; JPEG q80 then downscaled).
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";

const here = dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const pub = resolve(process.env.BOARD_PUBLIC ?? "public");
const origin = process.env.BOARD_ORIGIN ?? "http://localhost:5174";
const job = process.env.BOARD_JOB ?? String(process.pid);
const jobDir = join(pub, "_tmp", job);
const SW = 1340, SH = 1052;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const t0 = Date.now(), tick = (m) => process.env.SHOOT_DEBUG && console.error(`[${Date.now() - t0}ms] ${m}`);

// ---- CLI -> entries
const argv = process.argv.slice(2);
let entries, mode = "job";
const spec = (s) => { const [f, sz] = [s.slice(0, s.lastIndexOf(":")), s.slice(s.lastIndexOf(":") + 1)]; const [w, h] = sz.split("x").map(Number); return { board: f, w, h }; };
if (argv[0] === "zoom") {
  mode = "zoom";
  const [, s, x, y, w, h, out, z = 2] = argv;
  entries = [{ ...spec(s), scheme: "light", shots: [{ x: +x, y: +y, w: +w, h: +h, z: +z, out }] }];
} else if (argv[0] === "slices" || argv[0] === "probe") {
  mode = argv[0];
  entries = argv.slice(2).map((s) => ({ ...spec(s), scheme: "light", dir: argv[1], [mode]: true }));
} else if (argv[0]) {
  const txt = argv[0] === "-" ? readFileSync(0, "utf8") : readFileSync(argv[0], "utf8");
  const j = JSON.parse(txt);
  entries = Array.isArray(j) ? j : [j];
} else { console.error("usage: shoot.mjs <job.json|-> | zoom ... | slices ... | probe ..."); process.exit(2); }
for (const e of entries) {
  if (!e.board || !(e.w > 0) || !(e.h > 0)) { console.error("each entry needs board, w, h"); process.exit(2); }
  if (!existsSync(e.board)) { console.error(`no such board: ${e.board}`); process.exit(2); }
}

// ---- Edge + CDP (one browser, flat sessions)
const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const port = 9300 + Math.floor(Math.random() * 500);
const prof = join(tmpdir(), `shoot-board-${process.pid}`);
const p = spawn(edge, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${prof}`, `--remote-debugging-port=${port}`, "about:blank"], { stdio: "ignore" });
const killEdge = () => { if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(p.pid), "/T", "/F"], { stdio: "ignore" }); else p.kill(); };
const cleanup = () => { killEdge(); rmSync(jobDir, { recursive: true, force: true }); try { rmSync(prof, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 }); } catch {} };
const maxS = Number(process.env.SHOOT_MAX_S ?? 240);
setTimeout(() => { console.error(`shoot.mjs: gave up after ${maxS}s`); cleanup(); process.exit(124); }, maxS * 1000).unref();

let ver;
for (let i = 0; i < 60 && !ver; i++) { try { ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); } catch { await sleep(200); } }
if (!ver) { console.error("Edge did not start"); cleanup(); process.exit(1); }
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map(), waiters = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pend.has(d.id)) { const { res, rej } = pend.get(d.id); pend.delete(d.id); d.error ? rej(new Error(d.error.message)) : res(d.result); }
  else if (d.method) for (const w of waiters) w(d);
};
const send = (method, params = {}, sessionId, ms = 30000) => new Promise((res, rej) => {
  const n = ++id; pend.set(n, { res, rej });
  ws.send(JSON.stringify({ id: n, method, params, sessionId }));
  setTimeout(() => { if (pend.delete(n)) rej(new Error(`${method} timed out`)); }, ms);
});
const waitEvent = (name, sessionId, ms = 30000) => new Promise((res) => {
  const t = setTimeout(() => { waiters.splice(waiters.indexOf(f), 1); res(null); }, ms);
  const f = (d) => { if (d.method === name && d.sessionId === sessionId) { clearTimeout(t); waiters.splice(waiters.indexOf(f), 1); res(d); } };
  waiters.push(f);
});

async function newTab() {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  await send("Page.enable", {}, sessionId);
  const S = (m, pa) => send(m, pa, sessionId);
  return {
    S,
    async goto(url) { const w = waitEvent("Page.loadEventFired", sessionId); await S("Page.navigate", { url }); await w; },
    async ev(expression) {
      const r = await S("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? "js error");
      return r.result.value;
    },
    close: () => send("Target.closeTarget", { targetId }).catch(() => {}),
  };
}

// ---- output helpers
const outFiles = [];
const save = (file, b64) => { mkdirSync(dirname(file), { recursive: true }); writeFileSync(file, Buffer.from(b64, "base64")); outFiles.push(file); };
async function shootClip(tab, file, clip) {
  const jpg = /\.jpe?g$/i.test(file);
  const r = await tab.S("Page.captureScreenshot", { format: jpg ? "jpeg" : "png", ...(jpg ? { quality: 80 } : {}), clip: { ...clip, scale: clip.scale ?? 1 }, captureBeyondViewport: true }, undefined, 60000);
  save(file, r.data);
}

function palette() {
  const files = (process.env.BOARD_PALETTE ?? "design/tokens.json src/styles/tokens.css src/styles/palette.css src/scene/palette.ts src/scene/sky.ts src/scene/horizon.ts design/canvas/Ecrire.dc.html").split(/\s+/);
  const set = new Set();
  for (const f of files) if (existsSync(f)) for (const m of readFileSync(f, "utf8").matchAll(/#([0-9a-f]{6}|[0-9a-f]{3})\b/gi)) set.add(m[1].toLowerCase());
  return [...set].sort().join(",");
}

function probeReport(r, prefix) {
  writeFileSync(prefix + ".probe.json", JSON.stringify(r, null, 1));
  const sev = { high: 0, med: 1, low: 2 };
  const L = [`# Probe: ${r.board} ${r.W}x${r.H} · ${r.frames.length} frames`, "",
    "| # | frame | x,y,w,h | art | biggest art | empty paper | voice line | hierarchy | centred | high/med/low |",
    "|---|---|---|---|---|---|---|---|---|---|"];
  for (const f of r.frames) {
    const c = (s) => f.issues.filter((i) => i.sev === s).length, s = f.soul;
    L.push(`| ${f.i} | ${f.title} | ${f.frame.join(",")} | ${s.artShare} | ${s.biggestArt} | ${s.emptyPaper} | ${s.voice} | ${s.hierarchy} | ${s.centredShare} | ${c("high")}/${c("med")}/${c("low")} |`);
  }
  L.push("", "Soul signals are measurements to look at, not verdicts: art < 0.15 with biggest art < 0.1 = art shrunk to icon size; empty paper > 0.55 = a mostly empty frame; voice none or < 28px on the signature frame = no voice; hierarchy < 1.6 = flat; centred > 0.5 = everything centred.", "");
  for (const f of r.frames) {
    if (!f.issues.length) continue;
    L.push(`## ${f.i} · ${f.title}`);
    for (const i of f.issues.sort((a, b) => sev[a.sev] - sev[b.sev])) L.push(`- ${i.sev} · ${i.check} · ${i.what}${i.rect ? " · at " + i.rect.join(",") : ""}`);
    L.push("");
  }
  writeFileSync(prefix + ".probe.md", L.join("\n"));
  outFiles.push(prefix + ".probe.json", prefix + ".probe.md");
  return L.join("\n");
}

// ---- one entry
let pal;
async function doEntry(e, n) {
  const B = basename(e.board).replace(/\.dc\.html$/, "");
  const dir = e.dir ?? (e.shots?.[0] ? dirname(e.shots[0].out) : ".");
  const copy = `${n}/${basename(e.board)}`; mkdirSync(join(jobDir, String(n)), { recursive: true });
  copyFileSync(e.board, join(jobDir, copy));
  const url = `/_tmp/${job}/${copy}`;
  const tab = await newTab();
  const md = [];
  try {
    await tab.S("Emulation.setDeviceMetricsOverride", { width: e.w, height: e.h, deviceScaleFactor: 1, mobile: false });
    await tab.S("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: e.scheme ?? "light" }] });
    if (e.shots?.length || e.slices) {
      tick("goto " + B); await tab.goto(origin + url); tick("loaded");
      await tab.ev("(document.fonts ? document.fonts.ready : Promise.resolve()).then(() => 1)");
      await tab.ev("document.getAnimations().forEach(a => { if (a.effect?.getTiming().iterations !== Infinity) a.finish(); })");
      tick("ready"); await sleep(400);
      for (const s of e.shots ?? []) await shootClip(tab, s.out, { x: s.x, y: s.y, width: s.w, height: s.h, scale: s.z ?? 2 });
      if (e.slices) {
        let r = 0;
        for (let y = 0; y < e.h; y += SH, r++) {
          let c = 0;
          for (let x = 0; x < e.w; x += SW, c++) await shootClip(tab, join(dir, `${B}-r${r}-c${c}.png`), { x, y, width: Math.min(SW, e.w - x), height: Math.min(SH, e.h - y) });
        }
      }
    }
    if (e.probe) {
      copyFileSync(join(here, "probe.html"), join(jobDir, "probe.html"));
      tick("slices done"); pal ??= palette();
      await tab.goto(`${origin}/_tmp/${job}/probe.html?u=${encodeURIComponent(url)}&w=${e.w}&h=${e.h}&pal=${pal}`);
      let raw = "";
      for (let i = 0; i < 40 && !raw; i++) { raw = await tab.ev("document.getElementById('out').textContent"); if (!raw) await sleep(250); }
      if (!raw) console.error(`${B}: probe produced no result (dev server up? board renders?)`);
      else {
        mkdirSync(dir, { recursive: true });
        md.push(probeReport(JSON.parse(raw), join(dir, B)));
        mkdirSync(join(pub, "_tmp", "probe"), { recursive: true });
        copyFileSync(join(dir, B + ".probe.json"), join(pub, "_tmp", "probe", B + ".json"));
      }
    }
  } catch (err) { console.error(`${B}: ${err.message}`); process.exitCode = 1; }
  finally { await tab.close(); }
  return md;
}

// ---- run
tick("entries done"); let md = [];
try {
  mkdirSync(jobDir, { recursive: true });
  tick("edge up"); const t = await newTab();
  await t.goto(`${origin}/auth/dev?today=${new Date().toISOString().slice(0, 10)}`).catch(() => {});
  await t.close();
  const par = Number(process.env.BOARD_PAR ?? 4), queue = entries.map((e, n) => [e, n]), res = [];
  await Promise.all(Array.from({ length: Math.min(par, queue.length) }, async () => { for (let q; (q = queue.shift()); ) res[q[1]] = await doEntry(...q); }));
  md = res.flat();
} finally {
  ws.close();
  cleanup();
}

// ---- fit to 200KB: PNG -> 256-colour palette then downscale; JPEG -> downscale at q80
const fit = `
import sys, os
from PIL import Image
for f in sys.argv[1:]:
    if f.endswith(('.json', '.md')) or os.path.getsize(f) <= 200000: continue
    im = Image.open(f).convert("RGB"); jpg = f.lower().endswith(('.jpg', '.jpeg'))
    def sv(i):
        if jpg: i.save(f, "JPEG", quality=80)
        else: i.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, "PNG", optimize=True)
    sv(im)
    while os.path.getsize(f) > 200000 and im.width > 100:
        im = im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.LANCZOS); sv(im)
`;
tick("browser closed"); if (outFiles.length) spawnSync("python", ["-I", "-c", fit, ...outFiles], { stdio: ["ignore", "ignore", "inherit"] });
tick("fit done"); if (mode === "zoom") console.log(outFiles[0]);
else if (mode === "slices") outFiles.forEach((f) => console.log(f));
else if (mode === "probe") md.forEach((m) => console.log(m));
else for (const f of outFiles) console.log(`${f} ${(statSync(f).size / 1024).toFixed(0)}KB`);
process.exit(process.exitCode ?? 0);
