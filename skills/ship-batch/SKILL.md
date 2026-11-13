---
name: ship-batch
description: Run a plan file's tasks as build -> audit -> fix loops, then gate, commit and push once. Use for sizeable planned work.
disable-model-invocation: true
---

# ship-batch

## Default path (from the main loop): same-agent loop
True same-agent reuse (kept context and cache) needs the Agent tool plus SendMessage. Workflow scripts have neither.

1. Lead spawns one builder per task via Agent (agentType worker, model sonnet), brief = task + Owns + Done-check.
2. Lead spawns the auditor via Agent (agentType Explore, model haiku), read-only, returns {ok, missing}.
3. On findings, lead sends them verbatim to the SAME builder with SendMessage. Do not spawn a fresh fixer.
4. Cost guard: max 3 fix rounds per task; the same finding twice -> stop and report; if the builder's context is over ~150k tokens or spend is high, spawn a fresh fixer with a compact brief (handback + git diff + findings).
5. Run phases sequentially when the plan says P1 -> P6; parallel only for disjoint Owns.
6. Ship: spawn `shipper` once (gate, commit, push); then watch CI with `gh run watch --exit-status` in the background.

## Workflow path: `~/.claude/workflows/stage-build-sim-fix-verify.js`
Run with Workflow `scriptPath`, args `{fdir, stage, groups}`. A repo may override with its own workflow (e.g. obsidian-ext-vault build-verify); prefer the repo's when it has one.
- Runtime offers agent(), pipeline(), phase(), log(); no resume/continue/sessionId option, no SendMessage.
- Without the workflow file, use the default same-agent path above.
