// node cdpshot.mjs <url> <out.png> <w> <h> [light|dark] [--js "expr" ...] [--wait ms]
// Headless Edge via CDP, signed in through the w2 profile. --js runs in order (awaited, 400ms apart).
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { homedir } from "node:os";

const a = process.argv.slice(2);
const [url, out, w, h, scheme = "light"] = a;
const js = [];
let wait = 1500;
for (let i = 5; i < a.length; i++) { if (a[i] === "--js") js.push(a[++i]); else if (a[i] === "--wait") wait = Number(a[++i]); }
const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const prof = process.env.SHOT_PROFILE ?? `${homedir()}/.claude/tools/.shot-w2`;
const port = 9300 + Math.floor(Math.random() * 500);
const p = spawn(edge, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${prof}`, `--remote-debugging-port=${port}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (targets.find((t) => t.type === "page")) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } };
const send = (method, params = {}) => new Promise((r) => { const n = ++id; pend.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
try {
  await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 700 });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
  await send("Page.enable");
  await send("Page.navigate", { url });
  await sleep(wait + 1500);
  for (const e of js) { const r = await send("Runtime.evaluate", { expression: e, awaitPromise: true }); if (r.result?.result?.value !== undefined) console.log("=>", JSON.stringify(r.result.result.value)); if (r.result?.exceptionDetails) console.error("js error:", e, JSON.stringify(r.result.exceptionDetails.exception?.description)); await sleep(500); }
  await sleep(500);
  const clip = process.env.CLIP?.split(",").map(Number);
  const s = await send("Page.captureScreenshot", { format: "png", ...(clip ? { clip: { x: clip[0], y: clip[1], width: clip[2], height: clip[3], scale: clip[4] ?? 1 } } : {}) });
  writeFileSync(out, Buffer.from(s.result.data, "base64"));
  console.log(out);
} finally { ws.close(); p.kill(); }
