"""Machine-wide cap on heavy commands (screenshots, browsers, dev servers) across all agents.

`slot.py acquire` waits for one of SLOTS lock files, prints its path. `slot.py release <path>` frees it.
The guard wraps heavy Bash commands as: ( S=$(slot.py acquire) || exit 1; trap 'slot.py release "$S"' EXIT; <cmd> )
A slot older than STALE_S is taken over (its holder crashed; Bash calls never run longer than 10 min).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

SLOTS = max(3, (os.cpu_count() or 4) - 2)
STALE_S = 15 * 60
WAIT_S = 9 * 60
# Sandboxed Bash can't write ~/.claude; /tmp/claude-<uid> is writable from every session of this user.
DIR = Path.home() / ".claude" / "hookstate" / "slots" if os.name == "nt" else Path(f"/tmp/claude-{os.getuid()}/slots")


def acquire() -> Path | None:
    try:
        DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path(os.devnull)  # no shared lock dir: run uncapped rather than fail the command
    deadline = time.time() + WAIT_S
    while time.time() < deadline:
        for i in range(SLOTS):
            path = DIR / f"slot{i}.lock"
            try:
                if time.time() - path.stat().st_mtime > STALE_S:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
            except OSError:
                return Path(os.devnull)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return path
        held = ", ".join(f"{p.name}=pid {p.read_text() or '?'}" for p in sorted(DIR.glob("slot*.lock")) if p.exists())
        print(f"slot.py: all {SLOTS} slots busy ({held}); waiting", file=sys.stderr)
        time.sleep(10)
    return None


def main() -> None:
    if sys.argv[1:2] == ["acquire"]:
        path = acquire()
        if path is None:
            sys.exit(f"slot.py: all {SLOTS} heavy-command slots busy for {WAIT_S // 60} min; retry later")
        print(path.as_posix())
    elif sys.argv[1:2] == ["release"] and len(sys.argv) > 2:
        lock = Path(sys.argv[2])
        if lock.parent == DIR and lock.name.startswith("slot") and lock.suffix == ".lock":
            lock.unlink(missing_ok=True)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
