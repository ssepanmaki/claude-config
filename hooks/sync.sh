#!/bin/bash
# Pull latest config at session start so changes apply without editing the setup script.
R=~/.claude-config; [ -d $R/.git ] || exit 0
timeout 10 git -C $R pull -q --ff-only 2>/dev/null && bash $R/install.sh
exit 0
