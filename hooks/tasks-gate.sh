#!/bin/bash
# Stop hook: block ending the turn while this session has unfinished tasks.
in=$(cat); sid=$(jq -r '.session_id // empty' <<<"$in")
d=~/.claude/tasks/$sid; [ -n "$sid" ] && [ -d "$d" ] || exit 0
open=$(jq -r 'select(.status=="pending" or .status=="in_progress") | "#\(.id) \(.subject)"' "$d"/*.json 2>/dev/null)
[ -z "$open" ] && exit 0
printf 'Unfinished tasks — finish and verify them (or delete with the blocker stated) before stopping:\n%s\n' "$open" >&2
exit 2
