#!/bin/bash
cmd=$(jq -r '.tool_input.command // ""')
case "$cmd" in *"git push"*)
  b=$(git branch --show-current 2>/dev/null)
  if [[ "$b" =~ ^(main|master|claude/) ]]; then
    echo "Blocked: push from '$b'. Create a <type>/<topic> branch (e.g. fix/login) first." >&2; exit 2
  fi;;
esac
exit 0
