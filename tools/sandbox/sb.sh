#!/usr/bin/env bash
set -e
dir="$(cd "$(dirname "$0")" && pwd)"
docker image inspect claude-sb >/dev/null 2>&1 || docker build -t claude-sb "$dir"
MSYS_NO_PATHCONV=1 exec docker run --rm -it \
  --cap-drop ALL --security-opt no-new-privileges --memory 4g --pids-limit 512 \
  -v claude-sb:/home/dev/.claude -v "$(pwd -W 2>/dev/null || pwd)":/work \
  claude-sb "$@"
