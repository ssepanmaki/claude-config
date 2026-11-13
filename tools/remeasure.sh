#!/bin/sh
# One-shot re-measure of the 2026-11-08 setup-audit fixes. Runs a headless Claude session that
# collects the last N days, re-runs the session-intent workflow and compares with the baseline.
D=$(date +%F); OUT=$HOME/.claude/audits/remeasure-$D; mkdir -p "$OUT"
cd "$HOME" && claude -p "Re-measure the Claude Code setup-audit fixes applied on 2026-11-08 (baseline: ~/.claude/audits/baseline-2026-11-08).
1. Run: python3 \$(ls -d ~/.claude/remote/plugins/*/*/skills/setup-audit/scripts | head -1)/collect.py --days 7 --scope all --out $OUT/snapshot.json
2. Build digests: python3 ~/.claude/audits/baseline-2026-11-08/digest.py $OUT/dig <your own session id prefix> (mkdir $OUT/dig first); keep only sessions that started after 2026-11-08T16:00Z.
3. Run the saved workflow ~/.claude/workflows/session-intent-audit.js via the Workflow tool with scriptPath, args {dig: '$OUT/dig', batches: <session ids split into batches of about 7>}. Write each returned session row to $OUT/sessions/<sid>.json.
4. Run: python3 ~/.claude/tools/audit_compare.py ~/.claude/audits/baseline-2026-11-08 $OUT and save the output to $OUT/compare.txt.
5. Write $OUT/summary.md: for each fix (Grep failures, SubagentHandback errors, sleep/Monitor blocks, stop-hook nags, commit-gate ui/app.html blocks, pkill exit 143/144, permission denials, Bash timeouts, intent met-rate) say moved / not moved, with numbers. Fixes that didn't move: propose the next mechanism (rule -> hook -> skill). Do not edit any config.
6. Post the summary as one step row to the artifact https://claude.ai/artifact/XPY9kbDEGKUNsgDAKjP5aS with ArtifactData set collection steps doc_id R1 {order:8,key:'R1',title:'Re-measure $D',model:'Sonnet',agent:'scheduled',questions:[2,4],covers:'7-day re-measure vs baseline',status:'done',result:<3-line summary>}." --max-turns 60 > "$OUT/run.log" 2>&1
