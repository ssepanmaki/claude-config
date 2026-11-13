#!/bin/sh
# Keeps working state across compaction, one file per session (<project>/.tmp/state/<sid>.md, else ~/.claude/state/<sid>.md).
#   save: PreCompact hook. Branch, last commit, changed files, newest plan; suite lock and last build-verify result if present.
#   show: SessionStart hook with matcher "compact". Prints it, so the compacted context gets it verbatim.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
sid=$(jq -r '.session_id // empty' 2>/dev/null)
[ -n "$sid" ] || sid=${CLAUDE_CODE_SESSION_ID:-shared}
if [ -d .tmp ]; then d=.tmp/state; else d=$HOME/.claude/state; fi
f=$d/$sid.md
case "$1" in
  save)
    mkdir -p "$d"
    {
      echo "# Session state before compaction ($(date -u +%Y-%m-%dT%H:%MZ))"
      echo "Branch: $(git branch --show-current 2>/dev/null)"
      echo "Last commit: $(git log -1 --format='%h %s' 2>/dev/null)"
      if [ -f .tmp/suite.lock ]; then
        echo "Suite lock held: token $(cat .tmp/suite.lock), heartbeat $(stat -c %y .tmp/suite.lock | cut -c12-19) UTC. Do not start another full suite."
      fi
      echo "## Changed files (git status --short -uno, first 30)"
      git status --short -uno 2>/dev/null | head -30
      if [ -f .tmp/build-verify-last.json ]; then echo "## Last build-verify result"; head -c 1500 .tmp/build-verify-last.json; echo; fi
      p=$(ls -t "$HOME"/.claude/plans/*.md 2>/dev/null | head -1)
      [ -n "$p" ] && echo "Plan file: $p"
    } > "$f"
    ;;
  show)
    [ -f "$f" ] && { echo "Restored from $f (written just before compaction):"; cat "$f"; }
    ;;
esac
exit 0
