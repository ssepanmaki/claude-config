#!/usr/bin/env bash
# Measures every frame of a board. Usage: probe.sh <out_dir> <Board.dc.html:WxH> ... -> <out>/<Board>.probe.json + .md (md printed)
# Wrapper over shoot.mjs; env BOARD_PUBLIC, BOARD_ORIGIN, BOARD_PALETTE as before. Batch many shots in one call: shoot.mjs <job.json>.
exec node "$(dirname "$0")/shoot.mjs" probe "$@"
