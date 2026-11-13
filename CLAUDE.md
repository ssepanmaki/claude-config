# CLAUDE.md

## Talk
- ≤3 lines for status and routine replies; findings, plans and reviews may run longer (table or list) when the content needs it. Act on hand-backs, never relay. Casual; pro for audience.

## Think
- State assumptions; ask only if rework. Two readings → mine.
- Check premise in code; push back.
- "review" = copilot-review. "to /skill" = check only.
- Ruled-out route stays out. Edit live entry, not legacy twin.
- Foundry: new agent version per model, never repoint; diagnose first.
- New SDK → probe. Facts → lookup or "unchecked".
- Confirm retries. Same error twice (refused archive, hook block) → stop, report.
- Approval stands whole task; fix all findings unless reasoned. Reply 1: say what needs Dat/UI.
- Done = proof (merged+green / deploy+URL / UI seen); else "pushed, unverified: <what>". Handback: status, proof, unverified; subagent commits own files to branch. No push past red unless main red.

## Tools
- Preflight red (auth, libs, tools) → stop, report; never retry auth.
- No Grep/Glob: Bash grep -rn/find. Waits: run_in_background, end turn; Monitor needs until-condition.
- Batch; search first; ranges; no re-reads; narrowest check.
- `.codegraph/` → `codegraph_explore` first. Temp → `$T` (Linux: `$TMPDIR`).
- Browser: `javascript_tool{action:"javascript_exec"}`; `computer` scale ≤1.
- One call for greps; long → `timeout: 600000`.
- Deferred tools: one ToolSearch per session, all names at once.
- Scripts: Write → run; repeated → `~/.claude/tools/`.
- Blocked → change approach, never edit guard. No secrets. Never hand me steps.

## Work
- Small: do, check, ship. Sizeable: Opus plans once (`Decisions`), runs `ship-batch`, wakes for result only.
- Delegate: fresh custom Agent (scout/worker; never general-purpose: all tools, +22% cost), tight brief + standard + reference; ≤20 steps + maxTurns; Haiku mechanical, Sonnet edits. `start_session` only when asked; brief: `~/.claude/agents/templates/worker-brief.md`.
- Change → copies first: build, run it for real, fresh agent refutes; then live, backed up.
- Own numbers: blind-check a sample before reporting. Lead reads indexes, never dumps.
- Multi-step: one approval gate (board artifact), then drive to end; slip → revert, say so.
- Ship: fresh worktree off origin/main, own files only, CI watched in background.
- Own repos only; else commit local + ask. Ask before creds, money, deletes, prod.
- Gate (narrow test + ruff) → push main. CI fix: touched test, push, stop. PRs: auto-merge squash + archive.
- Recon: codegraph or built-in `Explore`. Cost: `tools/audit/tool_cost.py`.
- Audit names consumer first. Plan State once per hand-back. One session, one outcome. No full suite if suite.lock or load>cores; use lead's result. Sessions: list_sessions first, send_message needs session_id, archive idle/done only, never re-archive a refused one. New session ~300 msgs; handoff → status file.
- MetsoOutotec issues: draft for my review, never posted by subagent.

## Compact
Keep: request, decisions, agent ids, files/shas, verified vs not, artifact URLs, next step. Summary ≤1,500 tokens: no code bodies, no message log, no restating CLAUDE.md.
Drop: tool/test/CI output, re-readable file contents, image descriptions, subagent transcripts (keep verdicts), abandoned approaches (one line why).

## Code
- Smallest change: skip unasked → reuse → stdlib → dep → min code. No speculative abstraction, unasked config, impossible-error handling.
- Bug: fix root once, all callers. Never cut validation, data-loss handling, security.
- Touch only needed; repo style. Remove own orphans; flag old dead code. No duplicates. Short names; recreate = same name. Shortening → show cuts.
- Commits: `type(scope): subject`, no attribution.
