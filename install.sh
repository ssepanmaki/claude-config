#!/bin/bash
# Installs this repo as ~/.claude. Safe to re-run; never fails.
src=$(cd "$(dirname "$0")" && pwd); C=~/.claude
mkdir -p $C ~/.githooks
cp "$src"/CLAUDE.md "$src"/settings.json $C/ 2>/dev/null
for d in hooks agents output-styles skills; do mkdir -p $C/$d; cp -r "$src"/$d/. $C/$d/; done
cp "$src"/githooks/* ~/.githooks/; chmod +x $C/hooks/*.sh ~/.githooks/*
git config --global core.hooksPath ~/.githooks
exit 0
