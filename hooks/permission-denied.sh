#!/bin/sh
# PermissionDenied: auto mode denied a call. A plain read-only command is safe to retry; anything else stays denied.
cmd=$(jq -r 'select(.tool_name == "Bash") | .tool_input.command // empty')
case "$cmd" in
  *[\;\&\|\>\<\`\$\(]*|*"
"*) exit 0 ;;
esac
if printf '%s' "$cmd" | grep -Eq '^(git (status|diff|log|show)|ls|pwd|cat|grep|head|wc)( |$)'; then
  jq -n '{hookSpecificOutput: {hookEventName: "PermissionDenied", retry: true}}'
fi
exit 0
