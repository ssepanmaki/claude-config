"""PostToolUse(Bash): the 3rd run of the same command shape in one session/agent hints at a script."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common

HINT = "Repeated 3x: make it a script in ~/.claude/tools/ (Write, then run)"


SEEN = "already read (unchanged since); use what you have"


def read_repeat(state: dict, params: dict, who: str) -> str | None:
    """Deny the same Read (file_path+offset+limit) while the file is unchanged and the session has not compacted."""
    target = Path(str(params.get("file_path") or ""))
    if not target.is_file():
        return None
    info = target.stat()
    key = f"{who}|{target.as_posix().lower()}|{params.get('offset')}|{params.get('limit')}"
    stamp = [info.st_mtime_ns, info.st_size]
    reads = state.setdefault("reads", {})
    if reads.get(key) == stamp:
        return SEEN
    reads[key] = stamp
    return None


def main() -> None:
    event = common.read_events()
    shape = common.bash_shape(str((event.get("tool_input") or {}).get("command") or ""))
    if event.get("tool_name") != "Bash" or not shape:
        return
    session = str(event.get("session_id") or "")
    state = common.load_state(session)
    counts = state.setdefault("shapes", {}).setdefault(str(event.get("agent_id") or "main"), {})
    counts[shape] = counts.get(shape, 0) + 1
    common.save_state(session, state)
    if counts[shape] == 3:
        common.emit(common.advise("PostToolUse", HINT))


if __name__ == "__main__":
    with contextlib.suppress(Exception):
        main()
    sys.exit(0)
