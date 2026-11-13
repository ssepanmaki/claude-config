#!/usr/bin/env bash
# Puts regions of one or more boards side by side in one PNG, at one scale, labelled.
# Use it for: a frame next to its source board, a fix before/after next to the reference's
# signature frame, a whole board at a glance, or the squint test (blurred greyscale: what reads first?).
# Usage: compare.sh [-z scale] [--squint] <out.png> <spec> <spec> ...
#   spec = path/Board.dc.html:WxH#N          frame N (with its title and caption), from probe.sh's frame map
#        | path/Board.dc.html:WxH#N!         frame N only, no title or caption
#        | path/Board.dc.html:WxH@x,y,w,h    a region in board px
#        | path/Board.dc.html:WxH            the whole board
#   A spec may end with =Label to name it (default: Board #N).
# Env: BOARD_PUBLIC (default ./public), BOARD_ORIGIN (default http://localhost:5174).
set -eu
z=1; sq=0
while [ $# -gt 0 ]; do case "$1" in -z) z="$2"; shift 2 ;; --squint) sq=6; shift ;; *) break ;; esac; done
out="$1"; shift
pub="${BOARD_PUBLIC:-public}"; origin="${BOARD_ORIGIN:-http://localhost:5174}"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$pub/_tmp" "$(dirname "$out")"
cp "$here/compare.html" "$pub/_tmp/compare.html"
for spec in "$@"; do f="$(printf %s "$spec" | sed -E "s/:[0-9]+x[0-9]+([#@=].*)?$//")"; cp "$f" "$pub/_tmp/"; done
items="$(node -e '
const fs = require("fs"), [pub, ...specs] = process.argv.slice(1), path = require("path");
const list = specs.map(s => {
  let label = null; const eq = s.indexOf("="); if (eq > 0) { label = s.slice(eq + 1); s = s.slice(0, eq); }
  const m = /^(.*?):(\d+)x(\d+)(?:#(\d+)(!?)|@(\d+),(\d+),(\d+),(\d+))?$/.exec(s);
  if (!m) throw new Error("bad spec " + s);
  const b = path.basename(m[1], ".dc.html"), W = +m[2], H = +m[3];
  let x = 0, y = 0, w = W, h = H;
  if (m[4] !== undefined) {
    const p = path.join(pub, "_tmp/probe", b + ".json");
    if (!fs.existsSync(p)) throw new Error("no frame map for " + b + ": run probe.sh on it first");
    const fr = JSON.parse(fs.readFileSync(p, "utf8")).frames[+m[4]];
    if (!fr) throw new Error(b + " has no frame " + m[4]);
    [x, y, w, h] = m[5] ? fr.frame : fr.column;
    label = label || b + " #" + m[4] + " " + fr.title;
  } else if (m[6] !== undefined) [x, y, w, h] = [+m[6], +m[7], +m[8], +m[9]];
  return { u: "/_tmp/" + b + ".dc.html", W, H, x, y, w, h, label: label || b };
});
console.log(JSON.stringify(list));
' "$pub" "$@")"
size="$(node -e 'const l=JSON.parse(process.argv[1]),z=+process.argv[2];console.log(Math.max(520,Math.ceil(l.reduce((a,i)=>a+i.w*z+24,24)))+" "+Math.ceil(Math.max(...l.map(i=>i.h*z))+72))' "$items" "$z")"
enc="$(node -e 'console.log(encodeURIComponent(process.argv[1]))' "$items")"
SHOT_PUBLIC="$pub" ~/.claude/tools/shot.sh "$origin/_tmp/compare.html?z=$z&sq=$sq&items=$enc" "$out" $size light >/dev/null
echo "$out ($size)"
