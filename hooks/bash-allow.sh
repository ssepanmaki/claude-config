#!/bin/sh
# Global PreToolUse hook for one agent's Bash calls (not registered in settings; agents use it in frontmatter): denies any command that does not match the allowlist.
# Usage in agent frontmatter: command: 'sh ~/.claude/hooks/bash-allow.sh "<extended regex>"'
# A denied call costs the agent one short message instead of a long, off-task command output.
allow="$1"
cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0
# Accept the usual spellings of an allowed command: absolute project paths, `git -C <dir>`, a trailing `; echo "-> exit $?"`.
root=${CLAUDE_PROJECT_DIR:-$(pwd)}
cmd=$(printf '%s' "${cmd%%; echo*}" | sed "s#$root/##g; s#git -C [^ ]* #git #")
# Read-only output filters are fine: `allowed 2>&1 | grep x | head -20` checks as `allowed` (the main deny reason in transcripts).
f='[[:space:]]*\|[[:space:]]*(grep|head|tail|wc|sort|uniq|cut)([[:space:]]+[^|;&<>`$()]*)?'
cmd=$(printf '%s' "$cmd" | sed -E "s/[[:space:]]+2>&1//g; :a; s/$f\$//; ta")
# Chained or piped commands must match too: reject separators outright so `allowed && anything` can't slip through.
case "$cmd" in
  *'&&'*|*'||'*|*';'*|*'|'*|*'`'*|*'$('*|*'>'*|*'<'*) reason="one command per call, no chaining, pipes or redirects" ;;
  *) printf '%s' "$cmd" | grep -Eq "^($allow)" && exit 0; reason="not on this agent's allowlist: $allow" ;;
esac
jq -n --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
exit 0
