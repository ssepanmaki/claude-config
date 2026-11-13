#!/bin/bash
f=$(jq -r '.tool_input.file_path // empty'); [ -f "$f" ] || exit 0
d=$(git -C "$(dirname "$f")" rev-parse --show-toplevel 2>/dev/null) || exit 0
if [ -x "$d/node_modules/.bin/biome" ]; then "$d/node_modules/.bin/biome" format --write "$f" >/dev/null 2>&1
elif [ -x "$d/node_modules/.bin/prettier" ]; then "$d/node_modules/.bin/prettier" --write "$f" >/dev/null 2>&1; fi
exit 0
