---
name: board-audit
description: Audit-and-fix loop for canvas design boards (.dc.html). A Sonnet board-auditor shoots each board at 1:1 and writes findings with zoom crops; a Sonnet board-fixer patches the generator and regenerates; the auditor re-checks; the lead looks only at the final 1:1 slices. Use whenever boards are drawn, regenerated or polished, before calling them done or publishing the canvas, and when the user says "audit the boards", "review the boards" or "polish".
disable-model-invocation: true
---

# Board audit

The lead keeps no screenshots in its own context until the last step. Sonnet spots, Sonnet fixes, the lead signs off.

## Before you start
- Dev server up (Calanque: http://localhost:5174, serving `public/_tmp/`). Never start a second one.
- Know, for each board: its `.dc.html` path and size `WxH`, its generator and regen command, and the standard (Calanque: `design/canvas/BOARDS.md`) and reference board (Calanque: `design/canvas/Ecrire.dc.html`).
- Out dir: `<scratchpad>/audit/`.

## Loop (at most 3 rounds)
1. **Audit:** one `board-auditor` agent for all boards (Sonnet). Brief: the board specs `path:WxH`, the standard, the reference, the source board per frame if known, and the out dir. It critiques soul first (story, metaphor, signature, life, craft, voice; each frame scored 1–5), then runs the mechanical floor. It hands back `pass|fail`, the lowest soul score, counts and a findings path per board.
2. Every board passes → go to step 5.
3. **Fix:** one `board-fixer` agent (`model: sonnet`) with every failing findings file, each board's generator and regen command, and the art sources. Soul findings are creative briefs: the fixer may redraw the named frame. Boards with disjoint generators can go to separate fixers in parallel.
4. **Re-check:** the auditor again, in re-check mode with the findings files. Back to step 2.
5. **Sign-off (lead):** run `node ~/.claude/tools/board/shoot.mjs` with `slices:true` and `dir:<out>/final` for every board (one call) and open every final slice yourself. Also open one `compare.sh -z 0.5` of the board's signature frame next to the gold frames. This is the lead review the user's rule asks for; open each at the size that best shows it. Anything you'd still change goes to the fixer as a finding you write yourself (same format), then re-check it.
6. If any board size changed, restack the canvas layout. Then publish.

## Keep it cheap
- Never open a slice or zoom in the lead before step 5. Read the auditor's findings text instead.
- The lead doesn't patch generators. Even a one-line fix goes to the fixer, unless it's a copy typo.
- Compact after the sign-off and publish.
- Re-check only the regions with findings, not the whole board.
- Run at most 4 board agents at once; each agent makes one `shoot.mjs` call per round.

## Tools
- `node ~/.claude/tools/board/shoot.mjs <job.json|->`: zoom shots, 1:1 slices (1340x1052) and probe (floor hits, soul signals, frame map compare.sh uses) in one call. zoom.sh/slices.sh/probe.sh remain as wrappers.
- `~/.claude/tools/board/compare.sh [-z s] [--squint] <out.png> <Board:WxH#N | #N! | @x,y,w,h>[=Label] ...`: frames side by side at one scale; `--squint` blurs to greyscale to test what reads first.
- Calanque scene parts: `design/canvas/parts.mjs` (real sea art as SVG), catalogue `design/canvas/Parts.dc.html`.
- Env: `BOARD_PUBLIC` (default `./public`), `BOARD_ORIGIN` (default `http://localhost:5174`).

## Shared tool rules (auditor and fixer)
- shoot.mjs: run from project root, ONE call for all shots, slices and probes. Entry `{board:"design/canvas/X.dc.html", w, h, scheme:"light"|"dark", dir, shots:[{x,y,w,h,z,out}], slices:bool, probe:bool}`; x,y,w,h in board px, z default 2, `.jpg` out = JPEG else PNG; slices -> `<dir>/<Board>-r<row>-c<col>.png` (1340x1052, r<R>-c<C> starts at x=C*1340, y=R*1052); probe -> `<dir>/<Board>.probe.json/.md`; env BOARD_PAR default 4. Probe hits are candidates: confirm on a zoom.
- compare.sh specs: `Board:WxH#N` (frame+caption), `#N!` (frame only), `@x,y,w,h`, `=Label`.
