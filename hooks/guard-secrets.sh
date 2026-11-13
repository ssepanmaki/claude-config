#!/usr/bin/env bash
# PreToolUse(Write|Edit): block writing secrets files or obvious credential strings.
set -u
input=$(cat)
path=$(jq -r '.tool_input.file_path // empty' <<<"$input")
body=$(jq -r '(.tool_input.content // .tool_input.new_string // empty)' <<<"$input")
case "$path" in
  *.env|*.env.*|*.pem|*.key|*id_rsa*|*credentials*.json)
    [[ $path == *.example || $path == *.sample ]] || { echo "Blocked: $path looks like a secrets file." >&2; exit 2; } ;;
esac
if grep -Eq '(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|xox[baprs]-[A-Za-z0-9-]{10,})' <<<"$body"; then
  echo "Blocked: content contains what looks like a credential. Use an env var or secret manager." >&2; exit 2
fi
exit 0
