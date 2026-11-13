#!/usr/bin/env bash
# PreToolUse(Bash): block clearly destructive commands. Exit 2 = block, stderr shown to Claude.
set -u
cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$cmd" ] && exit 0
block() { echo "Blocked by guard-bash: $1. Ask the user if this is really intended." >&2; exit 2; }
shopt -s nocasematch
[[ $cmd =~ rm[[:space:]]+-[a-z]*r[a-z]*f?[[:space:]]+(/|~|\$HOME)([[:space:]]|$|/\*) ]] && block "recursive delete of / or home"
[[ $cmd =~ git[[:space:]]+push.*(--force|[[:space:]]-f([[:space:]]|$)) && ! $cmd =~ force-with-lease ]] && block "force push (use --force-with-lease on your own branch, after asking)"
[[ $cmd =~ git[[:space:]]+push[[:space:]]+[^[:space:]]+[[:space:]]+(HEAD:)?(main|master)([[:space:]]|$) ]] && block "direct push to main/master"
[[ $cmd =~ (--no-verify|--no-gpg-sign) ]] && block "bypassing git hooks/signing"
[[ $cmd =~ (curl|wget).*\|[[:space:]]*(sudo[[:space:]]+)?(ba|z)?sh ]] && block "piping a download into a shell"
[[ $cmd =~ (drop[[:space:]]+(table|database)|truncate[[:space:]]+table) ]] && block "destructive SQL"
exit 0
