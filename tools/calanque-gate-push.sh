#!/usr/bin/env bash
# Gate calanque, then commit the given paths and push main.
# Usage: calanque-gate-push.sh "type(scope): subject" path...
set -euo pipefail
msg="$1"; shift
cd /c/Users/OMISTAJA/calanque
npm run typecheck >/dev/null
npm test 2>&1 | grep -E "^# (pass|fail)"
npm run build >/dev/null 2>&1
node design/tools/cards.mjs check | tail -1
node design/tools/canvas.mjs check | tail -1
git add -- "$@"
git commit -qm "$msg"
git push -q origin main
git log -1 --format=%h origin/main
