#!/usr/bin/env bash
# Headless Edge screenshot of a local page, signed in through the dev door.
# Usage: shot.sh <url> <out.png> [width] [height] [light|dark]
# Widths under 500 px are framed in an iframe, since headless Edge won't lay out narrower.
# Framing needs the project's public/ folder: set SHOT_PUBLIC (default: ./public).
set -euo pipefail
url="$1"; out="$2"; w="${3:-390}"; h="${4:-844}"; scheme="${5:-light}"
edge="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
prof="${SHOT_PROFILE:-}"
if [ -z "$prof" ]; then
  # One Edge per profile: parallel runs on one profile segfault. Take a free slot, steal one locked >90 s.
  base="$HOME/.claude/tools/.shot-profile"
  for _ in $(seq 120); do
    for i in 0 1 2 3 4 5 6 7; do
      lock="$base-$i.lock"
      if mkdir "$lock" 2>/dev/null || [ -n "$(find "$lock" -maxdepth 0 -mmin +1.5 2>/dev/null)" ]; then
        touch "$lock"; prof="$base-$i"; trap 'rmdir "$lock" 2>/dev/null' EXIT; break 2
      fi
    done
    sleep 1
  done
  [ -n "$prof" ] || { echo "all 8 shot profiles busy for 2 min" >&2; exit 1; }
fi
origin="$(printf '%s' "$url" | sed -E 's#^(https?://[^/]+).*#\1#')"
case "$origin" in http://localhost:*|http://127.0.0.1:*) ;; *) echo "local URLs only" >&2; exit 2 ;; esac
pref=1; [ "$scheme" = dark ] && pref=0
if [ ! -d "$prof" ]; then
  timeout 60 "$edge" --headless=new --disable-gpu --user-data-dir="$prof" --dump-dom "$origin/auth/dev?today=$(date +%F)" >/dev/null 2>&1 || true
fi
target="$url"; ww="$w"
if [ "$w" -lt 500 ]; then
  pub="${SHOT_PUBLIC:-public}"; mkdir -p "$pub/_tmp"
  cat > "$pub/_tmp/frame.html" <<'EOF'
<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#888}iframe{border:0;display:block}</style>
<script>const q=new URLSearchParams(location.search);document.write('<iframe src="'+q.get('u')+'" width="'+q.get('w')+'" height="'+q.get('h')+'"></iframe>')</script>
EOF
  path="${url#"$origin"}"
  target="$origin/_tmp/frame.html?w=$w&h=$h&u=$(printf '%s' "$path" | sed 's/&/%26/g; s/?/%3F/g')"
  ww=500
fi
timeout 60 "$edge" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="$prof" \
  --blink-settings="preferredColorScheme=$pref" --virtual-time-budget=5000 \
  --window-size="$ww,$h" --screenshot="$out" "$target" >/dev/null 2>&1 || true
[ -s "$out" ] && echo "$out" || { echo "no screenshot" >&2; exit 1; }
