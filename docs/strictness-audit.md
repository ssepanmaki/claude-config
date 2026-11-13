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

## Left strict on purpose
Opus-agent ban, `general-purpose` auto-rewrite to `worker`, curl-needs-timeout, heredoc file-write ban, no attribution trailers, rule-deletion refusal, hand-back hedge refusal, suppression (`noqa`, `type: ignore`) nudge, `rm -rf`/force-push gates.

## Conflicts found, not changed (need a decision)
1. `CLAUDE.md` says "Opus plans once" but `pretool.py` bans Opus agents (`NO_OPUS`): a plan by an Opus *agent* is refused. Intended meaning is probably the main session on Opus.
2. `CLAUDE.md` says "No Grep/Glob: use Bash grep" but `pretool.py` suggests "use the Glob tool" in the `find` refusal and counts Grep/Glob in the read streak.
3. `hooks/no-wait.sh` denies sleep >=120 s, `pretool.py` denies >30 s: the shell hook is now redundant for sleeps (it still covers `timeout`, `watch`, `tail -f`, `pkill -f`).
4. `AskUserQuestion` is denied in `settings.json`, yet the `Stop` hook and `CLAUDE.md` still say "ask only if rework".
5. `cloud-setup.sh` defaults to `dattruongtuan/claude-config`; this repo is `ssepanmaki/claude-config`. Set `CLAUDE_CONFIG_REPO` or change the default.
6. `settings.json` has the placeholder path `/home/OMISTAJA/claude-mods` (marketplace) and `tools/slot.py` path in `pretool.py`.
