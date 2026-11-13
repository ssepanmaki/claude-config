#!/bin/bash
# Local install: run from this repo when it is (or is about to become) ~/.claude.
#   git clone https://github.com/ssepanmaki/claude-config ~/.claude && ~/.claude/install.sh
# Idempotent. Checks deps, wires git hooks, runs the guard tests and a hook smoke test.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0; ok() { echo "ok   $*"; }; bad() { echo "FAIL $*"; fail=1; }; warn() { echo "warn $*"; }

for b in python3 jq git sh; do command -v "$b" >/dev/null && ok "$b" || bad "$b missing (apt/brew install $b)"; done
for b in ruff pytest node; do command -v "$b" >/dev/null && ok "$b" || warn "$b missing (optional: gates/tests; pip install ruff pytest)"; done

if [ "$DIR" = "$HOME/.claude" ]; then
  git config --global core.hooksPath "$DIR/hooks/git" && ok "git hooksPath -> hooks/git (strips attribution trailers in every repo)"
  if [ ! -e /home/OMISTAJA ] && [ "$HOME" != /home/OMISTAJA ]; then
    ln -s "$HOME" /home/OMISTAJA 2>/dev/null && ok "/home/OMISTAJA alias" || warn "no /home/OMISTAJA alias (some tools hardcode it; sudo ln -s \"$HOME\" /home/OMISTAJA)"
  fi
else
  warn "$DIR is not ~/.claude: hooks in settings.json point at ~/.claude, so clone it there or symlink it"
fi
chmod +x "$DIR"/hooks/*.sh "$DIR"/hooks/git/* 2>/dev/null
mkdir -p "$DIR/hooks/guard"/. && ok "dirs"

python3 -c "import json;json.load(open('$DIR/settings.json'))" && ok "settings.json parses" || bad "settings.json invalid"

# smoke: the gates must block what they claim to, and pass a harmless call
out=$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"git commit -m x -m \"Co-Authored-By: Claude <a@b.c>\""}}' | sh "$DIR/hooks/no-attrib.sh" 2>&1); [ $? -eq 2 ] && ok "no-attrib blocks trailers" || bad "no-attrib did not block"
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"echo hi"}}' | sh "$DIR/hooks/no-attrib.sh" >/dev/null 2>&1 && ok "no-attrib passes echo" || bad "no-attrib blocked echo"
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"tail -f x"}}' | sh "$DIR/hooks/no-wait.sh" | grep -q deny && ok "no-wait blocks tail -f" || bad "no-wait did not block"
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"ls"},"session_id":"s","transcript_path":""}' | python3 -I "$DIR/hooks/guard/pretool.py" >/dev/null 2>&1 && ok "pretool.py runs" || bad "pretool.py crashed"

if command -v pytest >/dev/null; then
  (cd "$DIR/hooks/guard" && HOME="${HOME}" pytest -q -p no:cacheprovider tests 2>&1 | tail -1 | grep -q passed) && ok "guard tests pass" || bad "guard tests fail (run: cd hooks/guard && pytest -q tests)"
fi
find "$DIR" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
[ $fail -eq 0 ] && echo "ready" || { echo "NOT ready"; exit 1; }
