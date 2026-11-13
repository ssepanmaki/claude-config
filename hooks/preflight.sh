#!/bin/sh
# SessionStart preflight: one line, no network, never blocks.
H=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
if [ -n "$ANTHROPIC_API_KEY$ANTHROPIC_AUTH_TOKEN$ANTHROPIC_BASE_URL$CLAUDE_CODE_OAUTH_TOKEN" ] || [ -s "$H/.credentials.json" ]; then a=auth:ok; else a=auth:MISSING; fi
m=
for t in python3 jq git gh; do command -v "$t" >/dev/null 2>&1 || m="$m $t"; done
[ -z "$m" ] && m=ok || m="MISSING$m"
l=ok
if command -v ldconfig >/dev/null 2>&1; then
  c=$(ldconfig -p 2>/dev/null)
  for x in libnss3 libatk-1.0 libgbm; do case $c in *$x*) ;; *) l="MISSING $x"; break;; esac; done
else l=unchecked; fi
if [ "$(uname -s)" = Linux ] && [ -n "$CLAUDE_CODE_REMOTE" ]; then h=linux-cloud; else h=other-$(uname -s | tr A-Z a-z); fi
echo "preflight: $a tools:$m chrome-libs:$l host:$h"
exit 0
