#!/usr/bin/env bash
# Kill any node process running obsidian-view.js, then start it again in the foreground.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { \$_.CommandLine -like '*obsidian-view.js*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
sleep 1
exec node "/home/OMISTAJA/AppData/Roaming/Claude/Claude Extensions/local.mcpb.vault.vault-for-claude/server/obsidian-view.js" 4750 9222
