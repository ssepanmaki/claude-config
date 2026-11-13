#!/usr/bin/env bash
# Vite dev server per repo: fixed port, own cache dir, pid file, idempotent.
# Usage: devserver.sh start|status|stop <calanque|gp|mylifeos>
# Env: DEVSERVER_PORT overrides the port, DEVSERVER_CACHE overrides the cache dir.
set -euo pipefail
cmd="${1:-status}"; repo="${2:-}"
case "$repo" in
  calanque) dir="/home/OMISTAJA/calanque"; cfg=vite.config.ts; dflt=5174 ;;  # config sets no port; 5174 is what the shot scripts use
  gp) dir="/home/OMISTAJA/Growth Platform/app"; cfg=vite.config.ts; dflt=5173 ;;
  mylifeos) dir="/home/OMISTAJA/mylifeos/web"; cfg=vite.config.js; dflt=5173 ;;
  *) echo "usage: devserver.sh start|status|stop <calanque|gp|mylifeos>" >&2; exit 2 ;;
esac
port=$(sed -nE 's/^[[:space:]]*port:[[:space:]]*([0-9]+).*/\1/p' "$dir/$cfg" | head -1)
port="${DEVSERVER_PORT:-${port:-$dflt}}"
state="$HOME/.claude/tools/.devserver/$repo"; mkdir -p "$state"
pidf="$state/pid"; url="http://localhost:$port"
alive() { [ -f "$pidf" ] && tasklist //FI "PID eq $(cat "$pidf")" 2>/dev/null | grep -q "$(cat "$pidf")"; }
up() { curl -s -o /dev/null --max-time 2 "$url/"; }
case "$cmd" in
  status)
    if alive; then echo "up $url pid $(cat "$pidf")"
    elif up; then echo "port $port busy, not started by devserver.sh"
    else echo "down $url"; fi ;;
  start)
    if alive; then echo "$url"; exit 0; fi
    if up; then echo "port $port already in use by another process" >&2; exit 1; fi
    # vite has no cacheDir CLI flag: a wrapper config merges it over the repo's config
    printf '%s\n' \
      'import { pathToFileURL } from "node:url";' \
      "const v = await import(pathToFileURL(\"$dir/node_modules/vite/dist/node/index.js\").href);" \
      'export default async (env) => {' \
      "  const { config } = await v.loadConfigFromFile(env, \"$dir/$cfg\", \"$dir\");" \
      '  const c = typeof config === "function" ? await config(env) : config;' \
      "  return v.mergeConfig(c, { cacheDir: process.env.DEVSERVER_CACHE || \"$state/cache\" });" \
      '};' > "$state/vite.wrap.mjs"
    (cd "$dir" && nohup node node_modules/vite/bin/vite.js "$dir" --config "$state/vite.wrap.mjs" --port "$port" --strictPort > "$state/log" 2>&1 &); rm -f "$pidf"
    for _ in $(seq 40); do
      if up; then  # record the listener's own Windows pid, so stop kills only this server
        netstat -ano | awk -v p=":$port" '$2 ~ p"$" && $4 == "LISTENING" {print $5; exit}' > "$pidf"
        echo "$url"; exit 0
      fi
      sleep 0.5
    done
    echo "not up after 20s; see $state/log" >&2; exit 1 ;;
  stop)
    if alive; then taskkill //PID "$(cat "$pidf")" //T //F >/dev/null; rm -f "$pidf"; echo stopped
    else rm -f "$pidf"; echo "nothing to stop"; fi ;;
  *) echo "usage: devserver.sh start|status|stop <repo>" >&2; exit 2 ;;
esac
