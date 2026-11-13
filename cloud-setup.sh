#!/bin/bash
# Cloud environment setup script: installs Dat's ~/.claude config from ssepanmaki/claude-config.
# Preferred: add ssepanmaki/claude-config as a repo of the session/environment; the
# script copies from that checkout (no token to renew). Fallbacks: clone via the GitHub
# proxy, then GH_TOKEN if set. Network: github.com reachable (default allowlist).
set -euo pipefail
REPO="${CLAUDE_CONFIG_REPO:-ssepanmaki/claude-config}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# deps first: hooks need python3 + jq
need=""; for b in python3 jq rsync git; do command -v $b >/dev/null || need="$need $b"; done
[ -n "$need" ] && { (apt-get update -qq && apt-get install -y -qq $need) >/dev/null 2>&1 || echo "warn: could not install$need"; }

# 1) attached checkout: any */claude-config dir holding settings.json + hooks/
ATT=1
SRC=$(find "$HOME" /workspace /workspaces /repos /home -maxdepth 4 -type d -name "${REPO#*/}" 2>/dev/null \
  | while read -r d; do [ -f "$d/settings.json" ] && [ -d "$d/hooks" ] && { echo "$d"; break; }; done || true)
if [ -z "$SRC" ]; then
  SRC="$T/cfg"; ATT=
  # 2) plain clone (cloud GitHub proxy may authorize it); 3) GH_TOKEN via env-config header
  if ! GIT_TERMINAL_PROMPT=0 git clone -q --depth 1 "https://github.com/$REPO.git" "$SRC" 2>/dev/null; then
    # never fail the session: warn and start without the config
    [ -n "${GH_TOKEN:-}" ] || { echo "warn: $REPO not attached to this environment; config skipped"; exit 0; }
    B64=$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraheader GIT_CONFIG_VALUE_0="Authorization: Basic $B64" \
      git clone -q --depth 1 "https://github.com/$REPO.git" "$SRC"
  fi
fi
echo "config source: $SRC"

mkdir -p ~/.claude ~/.claude/lean-start.dump  # dump dir: lean-start writes exact startup-context breakdown here
cp "$SRC/settings.json" ~/.claude/
# CLAUDE.md is never copied to ~/.claude: the attached repo loads it as a project file (a copy doubled it)
rm -f ~/.claude/CLAUDE.md
for d in rules agents skills hooks output-styles tools mods; do
  # skills: no --delete, so built-in skills already in ~/.claude/skills survive
  del=--delete; [ "$d" = skills ] && del=
  [ -d "$SRC/$d" ] && rsync -a $del --exclude '__pycache__' --exclude '.trash' --exclude 'synced' --exclude 'windows.md' "$SRC/$d/" ~/.claude/"$d"/
done
# strip Claude attribution trailers from every commit, any repo
git config --global core.hooksPath ~/.claude/hooks/git

# cloud overrides: drop local-only plugin marketplace and TUI setting
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home() / ".claude/settings.json"
d = json.loads(p.read_text())
for k in ("extraKnownMarketplaces", "enabledPlugins", "tui"):
    d.pop(k, None)
p.write_text(json.dumps(d, indent=2))
EOF

# some hooks/tools hardcode /home/OMISTAJA; alias it to this HOME and give the vault inbox a home
if [ "$HOME" != /home/OMISTAJA ] && [ ! -e /home/OMISTAJA ]; then
  ln -s "$HOME" /home/OMISTAJA 2>/dev/null || sudo ln -s "$HOME" /home/OMISTAJA 2>/dev/null || echo "warn: no /home/OMISTAJA alias"
fi
mkdir -p ~/obsidian-vault/wiki 2>/dev/null || true

echo "claude config installed: $(ls ~/.claude | tr '\n' ' ')"
