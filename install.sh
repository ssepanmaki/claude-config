#!/usr/bin/env bash
# Symlink this config into ~/.claude (backs up existing files). Hooks reference $CLAUDE_PROJECT_DIR,
# so for a user-level install they are pointed at this checkout instead.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); dest=${CLAUDE_HOME:-$HOME/.claude}
mkdir -p "$dest/skills"
link() { [ -e "$2" ] && [ ! -L "$2" ] && mv "$2" "$2.bak.$(date +%s)"; ln -sfn "$1" "$2"; echo "linked $2"; }
link "$here/CLAUDE.md" "$dest/CLAUDE.md"
for s in "$here"/skills/*/; do link "${s%/}" "$dest/skills/$(basename "$s")"; done
sed "s#\"\$CLAUDE_PROJECT_DIR\"/hooks#$here/hooks#g" "$here/settings.json" > "$dest/settings.json.new"
echo "Wrote $dest/settings.json.new — review and merge into $dest/settings.json (not overwritten automatically)."
