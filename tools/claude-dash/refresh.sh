#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:?usage: refresh.sh <dir>}"
mkdir -p "$out"
python "$here/collect.py" 90 > "$out/local.json"
ssh claude-box python3 - 90 < "$here/collect.py" > "$out/vm.json"
python "$here/build_data.py" "$out" "$out/ds"
ssh claude-box python3 - < "$here/board.py" > "$out/board.json"
echo "$out/ds"
