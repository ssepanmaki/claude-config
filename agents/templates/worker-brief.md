# Worker brief template (the lead fills every field; ≤5 items per worker)
```
Task: <one or two lines; for several, a Queue: <abs path> file with ≤5 items>
Owns: <absolute paths; disjoint from every live worker>
Reference: <written standard + one reference file/board/page to match; absolute paths>
Read first: <exact files/line ranges from recon; the worker does not redo recon>
Done-check: <one test file / ruff on touched files>; no background task.
Gate: <typecheck (tsc) + that one test file>. Never a full suite or build.
URL: <dev server URL, already running; started once by the lead via ~/.claude/tools/devserver.sh>
Tools: UI shots via `node ~/.claude/tools/review.mjs <url> <abs out_dir> [--sel css]... [--js expr]... [--only phone|desk] [--size WxH] [--light] [--wait ms]`; run `review.mjs --help` for flags. Fix every FAIL from its text; open an image only for a PASS shot that is new or changed.
Rules: absolute paths in every command and edit, except temp files: write them as $T/<name> in Bash; file tools (Read/Write/Edit/Glob/Grep) take the real path, since they do not expand $T. New files via Write, never a bash heredoc.
Loop until the done-check passes.
```
