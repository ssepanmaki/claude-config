#!/bin/sh
# PreToolUse: block commits, PRs and comments that carry Claude attribution trailers.
in=$(cat)
if printf '%s' "$in" | grep -qiE 'Co-Authored-By: Claude|Claude-Session:|Generated (with|by) \[?Claude Code'; then
  echo 'Blocked: remove the Co-Authored-By / Claude-Session / "Generated with Claude Code" lines, then retry. Dat wants no attribution.' >&2
  exit 2
fi
