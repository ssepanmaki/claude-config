// Design-system guard: lists bare HTML controls in JSX outside the kit, so screens use the repo's components.
// node dsguard.mjs <src_dir> [--kit dir]... [--tags a,b,...] [--files f...]
//   --kit: dirs (relative to src_dir) that may use bare tags; default components/ui and pages/design-system.
//   --tags: default button,input,select,textarea,table,label,a,dialog,form,progress.
//   --files: check only these files (e.g. a worker's changed files).
//   A line (or the line above) holding `ds-allow: <reason>` is exempt; the reason is required.
// stdout: file:line <tag> per hit, then a count per tag. Exit 1 when any hit.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const a = process.argv.slice(2);
if (!a.length || a.includes("--help")) {
  console.log("dsguard.mjs <src_dir> [--kit dir]... [--tags a,b] [--files f...]  (exit 1 on any bare tag outside the kit)");
  process.exit(a.length ? 0 : 2);
}
const root = resolve(a[0]);
const kit = [], files = [];
let tags = "button,input,select,textarea,table,label,a,dialog,form,progress".split(",");
for (let i = 1; i < a.length; i++) {
  if (a[i] === "--kit") kit.push(a[++i]);
  else if (a[i] === "--tags") tags = a[++i].split(",");
  else if (a[i] === "--files") while (a[i + 1] && !a[i + 1].startsWith("--")) files.push(resolve(a[++i]));
}
if (!kit.length) kit.push("components/ui", "pages/design-system");
const kitAbs = kit.map((k) => resolve(root, k) + sep);
const walk = (d) => readdirSync(d).flatMap((n) => {
  const f = join(d, n);
  if (n === "node_modules" || n.startsWith(".")) return [];
  return statSync(f).isDirectory() ? walk(f) : /\.(tsx|jsx)$/.test(n) ? [f] : [];
});
const list = (files.length ? files.filter((f) => /\.(tsx|jsx)$/.test(f)) : walk(root)).filter((f) => !kitAbs.some((k) => f.startsWith(k)));
const re = new RegExp(`<(${tags.join("|")})(?=[\\s>/])`, "g");
const counts = {};
let hits = 0;
for (const f of list) {
  const lines = readFileSync(f, "utf8").split("\n");
  lines.forEach((line, i) => {
    if (/ds-allow:\s*\S/.test(line) || /ds-allow:\s*\S/.test(lines[i - 1] ?? "")) return;
    if (/^\s*(\/\/|\*)/.test(line)) return;
    for (const m of line.matchAll(re)) {
      console.log(`${relative(process.cwd(), f).split(sep).join("/")}:${i + 1} <${m[1]}>`);
      counts[m[1]] = (counts[m[1]] ?? 0) + 1;
      hits++;
    }
  });
}
console.log(hits ? `${hits} bare: ${Object.entries(counts).sort((x, y) => y[1] - x[1]).map(([t, n]) => `${t} ${n}`).join(", ")}` : "0 bare");
process.exit(hits ? 1 : 0);
