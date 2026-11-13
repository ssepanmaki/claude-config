#!/bin/sh
# PreToolUse(Bash) for every session and subagent: no sleeping, timeout wrappers or polling loops.
# Waiting in a command burns wall time (and tokens when polled); the harness already notifies when background work ends.
cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0
raw=$cmd
# Match commands only: drop heredoc bodies and quoted strings, so a script that merely mentions `sleep` isn't denied.
cmd=$(printf '%s\n' "$cmd" | awk '
  t != "" { if ($0 ~ "^[ \t]*" t "[ \t]*$") t = ""; next }
  { if (match($0, /<<-?[ \t]*["'\'']?[A-Za-z_][A-Za-z0-9_]*/)) { t = substr($0, RSTART, RLENGTH); sub(/^<<-?[ \t]*["'\'']?/, "", t) } print }' |
  sed "s/'[^']*'//g; s/\"[^\"]*\"//g")
s='(^|[;&|(`]|\$\(|then|do|else)[[:space:]]*'
deny() { jq -n --arg r "$1" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'; exit 0; }
if printf '%s' "$cmd" | grep -Eq "${s}(sleep[[:space:]]+(1[2-9][0-9]|[2-9][0-9]{2}|[0-9]{4,})|g?timeout|watch)([[:space:]]|[;&|)]|$)|tail[[:space:]]+(-[a-zA-Z]*[fF]|--follow)"; then
  deny "No sleep of 120 s or more, timeout, watch or tail -f. Over ~2 min: run it with run_in_background and end the turn; you are notified when it exits. Need a time limit: the Bash tool timeout parameter. Waiting for a condition: Monitor."
fi
# `pkill -f node` matches this shell's own argv and kills the call (exit 143/144). A bracketed first letter can't match itself.
if printf '%s' "$cmd" | grep -Eq "${s}(pkill|pgrep)[[:space:]]+(-[a-zA-Z]*[[:space:]]+)*-[a-zA-Z]*f" && ! printf '%s' "$raw" | grep -Eq '(pkill|pgrep)[^;&|]*-[a-zA-Z]*f[a-zA-Z]*[[:space:]]+["'\'']?\['; then
  deny "pkill -f would match its own shell and kill this call. Bracket the first letter: pkill -f '[n]ode --test'."
fi
exit 0
