# Strictness audit of ssepanmaki/claude-code

Source reviewed: `CLAUDE.md`, `AGENTS.md`, `.claude/` (read-only access, so nothing was changed there).

## Adopted here (kept strict)
| Idea from that repo | Where |
|---|---|
| Conventional Commits | CLAUDE.md > Git |
| Zero-error typecheck as a goal | CLAUDE.md > Verification (scoped to checks that exist) |
| No `as any` in production code, ok in test mocks | CLAUDE.md > Code quality |
| Interview-before-plan skill, recommended option first | skills/interview |

## Too strict there (relaxed here; suggest the same upstream)
1. **"`bun run precheck` must pass with zero errors after ANY change"** (also a "run after every task" rule). It runs typecheck + lint *fix* + the full test suite, so a one-line doc edit pays full cost and lint-fix rewrites unrelated files. Suggest: run the narrowest relevant check per edit, full precheck once before commit/PR; CI stays the hard gate.
2. **"`biome ci` must have zero warnings"** combined with mandatory `biome-ignore` comments to settle tsc-vs-biome conflicts. Suggest: errors block, warnings are reported; ignores need a reason but not a ritual.
3. **Hard mock rules** ("must mock these 5 modules", "never double-mock", exact path conventions). Brittle and unenforceable by hand. Suggest: keep as guidance plus a lint rule if it matters.
4. **Forced Simplified Chinese** in `hello-agent` ("Respond in 简体中文") and `interview` (all text MUST be Chinese). Suggest: match the user's language.
5. **AGENTS.md and CLAUDE.md duplicate ~350 lines and have already diverged** (e.g. precheck vs bare tsc). Suggest: one source of truth, the other a one-line pointer (`@CLAUDE.md`).
6. `hello-agent` adds no behavior beyond reading CLAUDE.md; candidate for deletion.

## Too lax there (stricter here)
- No guard against force-push, `--no-verify`, or secret writes: now hooks plus deny rules (hooks/, settings.json).
- No rule against skipping/deleting tests to get green: now explicit.
- Commit message language is non-English with no enforcement; kept as repo choice, global default is English.

## Researched, not applied (revisit if wanted)
- `PostToolUse` auto-format hook: skipped because formatter choice is per-project.
- `Stop` hook that blocks until tests pass: skipped as too strict for exploratory sessions; opt-in per project.
- Sandbox/network allowlists: depend on the environment, set in the environment config rather than here.
