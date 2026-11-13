#!/bin/bash
r=$(git remote get-url origin 2>/dev/null | sed -E 's#\.git$##; s#.*[/:]([^/:]+/[^/]+)$#\1#')
[ -n "$r" ] || exit 0
out=$(timeout 15 gh api -X GET search/issues -f q="repo:$r is:issue is:open" --jq '.items[:10][]|"#\(.number) \(.title)"' 2>/dev/null)
[ -n "$out" ] && printf 'Open issues in %s (cross-session task list):\n%s\n' "$r" "$out"
exit 0
