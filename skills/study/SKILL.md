---
name: study
description: Study -> test -> simulate -> verdict for a problem, in a throwaway worktree, then stop for approval and hand the verdict plan to ship-batch. Use before sizeable fixes, CI failures, or any change where the root cause is unproven.
disable-model-invocation: true
---

# study

Cheap and fast: Haiku reads, Sonnet runs, the lead only writes the verdict. The same steps work on Windows and claude-box. Run them where the repo and its branch actually live.

## 1. Study (parallel, Haiku, read-only)
Spawn 2 or 3 `Explore` agents (model haiku) at once, each with a narrow question:
- code: where the symptom comes from (path:line)
- evidence: CI logs (`gh run view <id> --log-failed | grep -E "not ok|Error"`) and failing test names
- history: prior plans in `~/.claude/plans/`, related issues, the last commits on the paths involved
Each returns at most 10 lines and marks anything it hasn't checked as "unchecked".

## 2. Test + simulate (Sonnet, isolated worktree)
Spawn one `worker` (model sonnet) with `isolation: "worktree"` off the target branch:
- Reproduce: run only the failing test files and record the failure.
- Simulate: apply the candidate fix, rerun the same files and record the result.
- Try at most 2 candidate fixes. The same failure twice means stop.
- It never commits or pushes. The worktree gets thrown away.
Hand-back: the command, the result before and after, and the diff size.

## 3. Verdict (lead writes, Haiku checks)
Write `~/.claude/plans/<slug>.md`:
- `## Problem`: the symptom, with evidence links
- `## Root cause`: path:line, proven by the repro
- `## Decisions`: the chosen fix and the ruled-out options, with reasons
- `## Tasks`: one per change, each with `Owns:` and a `Done-check:` command
- `## Risk`: what the simulation did not cover

Then spawn an `Explore` agent (model haiku) to check each claim in the verdict against the code and logs. It returns {ok, wrong}. Fix any wrong claim once.

## 4. Approve (stop)
Show the verdict path and a 3-line summary. Ask with wrap_up: "Ship this plan?" Implement nothing before the user says yes.

## 5. Implement
On approval, run `ship-batch` with `plan: <path>`. Its `shipper` gates and pushes once; then watch CI with `gh run watch --exit-status` in the background.

## Guards
- Study and simulate are read-only on the real checkout. Writes happen only in the worktree.
- Budget: 3 Explore agents, 1 simulator, and 1 verdict check per study.
- If the simulation can't reproduce the problem, the verdict says so and gets no Tasks.
