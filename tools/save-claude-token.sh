#!/bin/bash
# Save a `claude setup-token` token to ~/.config/claude-token (read by ~/.bashrc). Accepts a wrapped multi-line paste.
set -euo pipefail
f=~/.config/claude-token
echo "Paste the token (wrapped lines are fine), then press Enter and Ctrl-D:"
t=$(cat | tr -d "[:space:]\"'")
t=${t#export}
t=${t#CLAUDE_CODE_OAUTH_TOKEN=}
case "$t" in sk-ant-oat*) ;; *) echo "not a setup-token token (should start with sk-ant-oat); nothing saved"; exit 1 ;; esac
[ ${#t} -ge 80 ] || { echo "only ${#t} characters - looks cut off; nothing saved"; exit 1; }
mkdir -p ~/.config
umask 077
printf '%s\n' "$t" > "$f"
echo "saved ${#t} characters to $f"
