#!/bin/bash
# Get a fresh long-lived Claude Code token and save it to ~/.config/claude-token (read by ~/.bashrc).
set -euo pipefail
claude setup-token
echo
echo "Copy the WHOLE token above (all wrapped lines), then:"
bash ~/.claude/tools/save-claude-token.sh
echo "Done. Now revoke the old token in your Claude account settings."
