# Strictness audit

## Relaxed (this PR)
| Rule | Before | After | Why |
|---|---|---|---|
| Read/Grep/Glob streak refusal (`READ_STREAK_LIMIT`) | refuse the 6th in a row | refuse the 9th | Normal investigation needs more than 5 reads before the first edit |
| Lead call cap (`LEAD_CALL_CAP` / `LEAD_WARN_AT`) | hard stop at 15, warn at 12 per request | 25 / 22 | Medium tasks hit the cap and were forced into a `ship-batch` plan |
| Foreground sleep (`SLEEP_MAX_S`) | >10 s banned | >30 s banned | Short settle waits are cheap; polling loops stay banned |
| `CLAUDE.md` Talk | "≤3 lines" always | ≤3 lines for status; findings/plans/reviews may be longer | A 3-line cap truncates review findings and proofs |
| `rules/engineering.md` comments | "No comments" | none that restate code; one-line *why* or spec link allowed | A hidden constraint or workaround deserves its reason |

Guard tests now read these thresholds from `pretool.*` instead of hard-coding them (152 pass).

## Applied from research (verified with `claude -p` 2.1.323)
| Change | Verified how |
|---|---|
| `curl` with no timeout is now rewritten (`updatedInput`, adds `-m 30`) instead of refused | Real harness + real `pretool.py` hook: a fake `curl` on PATH received `-m 30 http://example.invalid/x` |
| `onFailure: "block"` on the `pretool.py` and `no-attrib.sh` hooks | Crashing hook (`exit 1`): without the field the Bash call ran; with it the call was blocked |

| Hook `if` filters on `no-wait.sh` (6 entries) and `no-attrib.sh` (Bash entries) | Probe: `if: "Bash(*sleep *)"` ran only for commands containing `sleep`, also inside `a; b` / `a && b`. Full settings: `echo` spawned neither script; `sleep 200`, `timeout 5 ls` and a `Co-Authored-By: Claude` commit were still blocked |
| `autoMode` block (`$defaults` + allow for test scratch/pytest, environment note that this repo is the config) | Schema keys read from the 2.1.323 binary; classifier behavior itself unverified (needs a real auto-mode denial) |
| `PermissionDenied` hook `permission-denied.sh`: retry only plain read-only commands | Unit-tested by piping JSON (`git status`, `ls` retry; chains, redirects, `rm`, non-Bash do not); not fired by a real denial |

`if` takes one rule, so each script has one entry per pattern, with a distinct trailing arg so identical commands are not merged. `no-attrib.sh` keeps an unfiltered `mcp__github__.*` entry.

Not applied, with reason:
- `sandbox.failIfUnavailable`: probed here, the session refuses to start (no bwrap/socat), so it would brick cloud sessions.
- `permissions.blockWrites/ReadsOutsideWorkingDirectories`: the ship flow works in fresh worktrees and cloud-setup writes `~/.claude`, both outside the working directory.
- `sandbox.network.allowedDomains`: needs a domain list and cannot be tested without bwrap.
- `autoMode.classifyAllShell`: sends every shell call to the classifier, the opposite of fewer denials.
- `PostCompact`, `SubagentStop`, `PostToolBatch`, `InstructionsLoaded`: no job yet (`SessionStart:compact` already re-injects state).
- Moving guard regexes to `permissions.deny`: the rules carry exceptions (`HEREDOC_OK`, `-maxdepth`, bracketed `pkill`) that a deny glob cannot express.
- `onFailure` on Stop/PostToolUse hooks: a crashing guard there would trap or stall the session.

## Left strict on purpose
Opus-agent ban, `general-purpose` auto-rewrite to `worker`, curl-needs-timeout, heredoc file-write ban, no attribution trailers, rule-deletion refusal, hand-back hedge refusal, suppression (`noqa`, `type: ignore`) nudge, `rm -rf`/force-push gates.

## Conflicts: resolved
1. Opus agents/workflows allowed only with an `OPUS WHY: <4+ words>` line; the refusal steers hard to Sonnet (edits, judgment) and Haiku (mechanical, search).
2. Grep/Glob vs Bash grep: left as is (Grep gets an auto `head_limit`; bash `grep -rn` has no cap). Crude check: one search was 6.3 KB as `grep -rn` vs 0.3 KB as a file list. Token cost of the tool schemas is unmeasured.
3. `no-wait.sh` sleep check removed; `pretool.py` owns sleep (cap 30 s, longer: background + notification).
4. `AskUserQuestion` allowed again for the main session; `pretool.py` denies it for subagents and sub-sessions.
5. `cloud-setup.sh` default repo is now `ssepanmaki/claude-config`.
6. `/home/OMISTAJA` is aliased to `$HOME` by `cloud-setup.sh`, and `tools/slot.py` ships in this repo: left as is.
7. `sandbox.network.allowedDomains` skipped; relaxing the other repo skipped.

## Token-saving tips list (3 agents, binary + repo checked)
- Applied: `effort: low` on `scout` and `shipper` (haiku, mechanical). The agent still loads in a scratch HOME with the field; the effect on tokens is unmeasured.
- Already done: Grep head_limit, Bash output spill (30000 chars), tool search on, 1h cache TTL, redundant-Read block, all skills `disable-model-invocation`, per-agent models, lean CLAUDE.md (551 words), statusline with ctx and cost.
- Refuted or skipped: RTK-style Bash output rewriting (hides output, harness already spills); GitHub MCP rule line (the server injects it already); `MAX_MCP_OUTPUT_TOKENS=10000` (default 25000, no bloat seen); `GOAL_CHECKIN_MINUTES=0` (also stops background check-ins); fix-loop cap (looser than "same error twice"); llm-router, ccusage, extra statusline tools (duplicate `tools/statusline.py`); `Explore` override (`scout` covers it); CI action tips (no `.github/`); `autoCompactWindow` per agent (lower bound unverified); `effort` on `vault` (it edits).
