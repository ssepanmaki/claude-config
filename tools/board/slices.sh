#!/usr/bin/env bash
# Shoots a board at 1:1 in 1340x1052 slices. Usage: slices.sh <outdir> <Board.dc.html>:<W>x<H> ... -> <outdir>/<Board>-r<row>-c<col>.png
# Wrapper over shoot.mjs; env BOARD_PUBLIC, BOARD_ORIGIN, BOARD_PALETTE as before. Batch many shots in one call: shoot.mjs <job.json>.
exec node "$(dirname "$0")/shoot.mjs" slices "$@"
