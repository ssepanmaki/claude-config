#!/bin/bash
# Headless Claude Code with the long-lived token from ~/.config/claude-token. Usage: claude-p.sh <claude -p args...>
set -euo pipefail
export CLAUDE_CODE_OAUTH_TOKEN="$(cat ~/.config/claude-token)"
exec claude -p "$@"
