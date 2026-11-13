#!/bin/sh
# SessionStart: tells the session its own claude.ai link so the first message of a thread can include it.
id=${CLAUDE_CODE_REMOTE_SESSION_ID:-$CLAUDE_CODE_SESSION_ID}
[ -n "$id" ] && echo "Session link (put it in your first thread message): https://claude.ai/code/$id"
exit 0
