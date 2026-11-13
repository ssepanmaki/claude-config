#!/usr/bin/env bash
# Shoots one region of a board, magnified. Usage: zoom.sh <path/Board.dc.html>:<W>x<H> <x> <y> <w> <h> <out.png> [zoom=2]
# Wrapper over shoot.mjs; env BOARD_PUBLIC, BOARD_ORIGIN, BOARD_PALETTE as before. Batch many shots in one call: shoot.mjs <job.json>.
exec node "$(dirname "$0")/shoot.mjs" zoom "$@"
