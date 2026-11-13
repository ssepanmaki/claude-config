#!/usr/bin/env bash
# Ship box commits to develop as ONE clean squashed commit.
# Usage: gp-ship.sh [--dry-run] -m "type(scope): msg" <commit|range>...
#   e.g. gp-ship.sh -m "fix(report): x" abc123 def456   or   develop..box~3
# Runs in a throwaway worktree off origin/develop, so the box checkout is untouched.
# Refuses: box-only paths, ADO refs / attc / claude in the message, non-ff push.
set -euo pipefail

REPO="${GP_REPO:-/c/Users/OMISTAJA/Growth Platform}"
BOX_ONLY='^(CLAUDE\.md|database/local/|\.claude/|\.codegraph/)'
DRY=0; MSG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    -m) MSG="$2"; shift 2 ;;
    *) break ;;
  esac
done
die() { echo "gp-ship: $*" >&2; exit 1; }
[[ $# -gt 0 ]] || die "no commits given"
[[ "$MSG" =~ ^[a-z]+(\([a-z0-9-]+\))?:\ .+ ]] || die "message must be one line 'type(scope): msg'"
[[ "$MSG" != *$'\n'* ]] || die "message must be one line"
grep -qiE '#[0-9]+|attc|claude|co-authored' <<<"$MSG" && die "message has ADO ref / attc / claude"

cd "$REPO"
git fetch -q origin
if [[ "$*" == *..* ]]; then COMMITS=$(git rev-list --reverse --no-merges "$@")
else COMMITS=$(for c in "$@"; do git rev-parse --verify -q "$c^{commit}" || die "bad commit $c"; done); fi
[[ -n "$COMMITS" ]] || die "no commits resolved from: $*"

WT=$(mktemp -d)/ship
git worktree add -q --detach "$WT" origin/develop
trap 'git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT
cd "$WT"
for c in $COMMITS; do
  git cherry-pick --no-commit "$c" >/dev/null || die "conflict picking $c; resolve on box (rebase box on origin/develop) and retry"
done
git diff --cached --quiet && die "nothing to ship (already on develop?)"

BAD=$(git diff --cached --name-only | grep -E "$BOX_ONLY" || true)
[[ -z "$BAD" ]] || die "box-only paths in change:"$'\n'"$BAD"
LEAK=$(git diff --cached -U0 | grep -E '^\+' | grep -iE '\battc\b|ado\.mjs|obsidian-vault' || true)
[[ -z "$LEAK" ]] || die "box material in added lines:"$'\n'"$LEAK"

git -c core.hooksPath=/dev/null commit -q -m "$MSG"
echo "--- shipping onto origin/develop:"; git log --oneline -1; git diff --stat HEAD~1 | tail -1
if [[ $DRY -eq 1 ]]; then echo "dry run: not pushed"; exit 0; fi

git push -q origin HEAD:refs/heads/develop || die "push rejected (develop moved?) — rerun"
NEW=$(git rev-parse HEAD)
cd "$REPO"
git fetch -q origin
if [[ "$(git branch --show-current)" == develop ]]; then git merge -q --ff-only origin/develop; else git branch -f develop origin/develop; fi
if [[ "$(git branch --show-current)" == box ]]; then
  git merge -q --no-edit origin/develop || echo "gp-ship: box merge needs manual resolve"
fi
echo "pushed $NEW to develop"
