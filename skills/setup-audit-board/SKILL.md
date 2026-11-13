---
name: setup-audit-board
description: Audit -> approve -> fix -> prove -> ship loop for Claude Code setup or any batch of config/hook/skill fixes. Use for "run the setup audit", "audit my setup/workflows", "find what keeps failing and fix it", or "do that loop again".
disable-model-invocation: true
---

# setup-audit-board

Lead = Opus, plans and reviews only. Probes, builders, checkers = Sonnet; mechanical = Haiku. One approval gate, on the board.

1. **Collect.** setup-audit `collect.py --days 30 --scope all --out $TMPDIR/snap.json`; read with `query_snapshot.py` by section. Never by hand.
2. **Probe + intent, in parallel.** Workflows `~/.claude/workflows/setup-audit-probes.js` and `session-intent-audit.js` (digests: `~/.claude/audits/baseline-*/digest.py <outdir> <own sid>`, 7 batches).
3. **Blind check.** 2 Sonnet agents re-judge 8 sessions (mix met/partial/unmet) from raw transcripts, verdicts hidden. Under 6/8 agreement: tighten the classifier prompt, re-run.
4. **Board.** One artifact, `db` collections `steps`, `findings`, `sessions`, `workflows`. Write rows with ArtifactData `batch` + `file_path` (≤50 per call). Dat approves there, once.
5. **Stage.** Workflow `stage-build-sim-fix-verify.js`: one group per target file set (no two groups touch a file). Copies in `$TMPDIR/stage/<g>/{orig,new}`; build -> simulate (actually run it) -> ≤2 fixers -> fresh verifier tries to refute.
6. **Review.** Lead reads every diff; fixes small verifier fails directly in `new/`.
7. **Apply.** Copy only if live == `orig` (else skip, report); back up to `~/.claude/backups/<date>/`; `json.tool` / `sh -n` after.
8. **Prove.** Hooks with real inputs in a worktree, not stubs; one headless `claude -p` smoke session on the new config (permission mode, hook fires, rule followed).
9. **Ship.** Fresh worktree from `origin/main` (never the shared checkout: it's often another session's branch). Commit only own files, gate, push main, `gh run watch` in background.
10. **Baseline.** Save snapshot + session rows to `~/.claude/audits/baseline-<date>/`; Dat re-measures with `~/.claude/tools/remeasure.sh` (`audit_compare.py` old new).

## Traps
- Sandbox shows protected missing paths (`~/.claude/{workflows,loop.md,commands}`) as /dev/null char devices: that means missing, not broken.
- `.claude/{hooks,agents,skills}` and `~/.claude` need Dat's approval per item; staged copies are fine.
- Stale `.git/config.lock`: `worktree add -b` fails; add the worktree on an existing branch.
- Headless sessions turn `ask` rules into denials; that's expected.
- First-pass intent judges are lenient; judge the final state, the lower outcome when unsure.
