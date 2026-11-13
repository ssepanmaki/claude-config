#!/bin/sh
# PostToolUse (global): one line per tool call to <project>/.tmp/progress/<sid>.log when the project has .tmp/, else ~/.claude/progress/<sid>.log. Follow with
#   tail -f .tmp/progress/*.log        (or: node tools/agent/verify.mjs is unaffected)
# If PROGRESS_WEBHOOK_URL is set, the same line is also POSTed there (best effort, 2 s cap). Never blocks the tool.
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // empty' 2>/dev/null)
[ -n "$sid" ] || sid=${CLAUDE_CODE_SESSION_ID:-shared}
line=$(printf '%s' "$in" | jq -r '"\(now|strftime("%H:%M:%S")) \(.tool_name) " + ((.tool_input.file_path // .tool_input.command // .tool_input.description // .tool_input.pattern // "") | tostring | gsub("\n";" ") | .[0:160])' 2>/dev/null)
[ -n "$line" ] || exit 0
d=${CLAUDE_PROJECT_DIR:-.}/.tmp; [ -d "$d" ] || d=$HOME/.claude; mkdir -p "$d/progress"
printf '%s\n' "$line" >> "$d/progress/$sid.log"
if [ -n "$PROGRESS_WEBHOOK_URL" ]; then
  curl -s -m 2 -X POST -H 'content-type: text/plain' --data "$sid $line" "$PROGRESS_WEBHOOK_URL" >/dev/null 2>&1 &
fi
exit 0
