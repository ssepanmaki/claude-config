"""Bash command shapes repeated >=5x across >=2 sessions: `python -I repeats.py <days>`."""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "guard"))
import common

MIN_COUNT, MIN_SESSIONS, TOP = 5, 2, 40


def scan(root: Path, days: float) -> dict[str, dict]:
    cutoff = time.time() - days * 86400
    shapes: dict[str, dict] = defaultdict(lambda: {"n": 0, "sessions": set(), "example": ""})
    for f in [*root.glob("*/*.jsonl"), *root.glob("*/*/subagents/*.jsonl")]:
        if f.stat().st_mtime < cutoff:
            continue
        session = f.parent.parent.name if f.parent.name == "subagents" else f.stem
        for raw in f.read_text("utf-8", "replace").splitlines():
            if '"Bash"' not in raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            for use in common.tool_uses([rec]):
                cmd = str((use.get("input") or {}).get("command") or "")
                shape = common.bash_shape(cmd) if use.get("name") == "Bash" else ""
                if shape:
                    s = shapes[shape]
                    s["n"] += 1
                    s["sessions"].add(session)
                    s["example"] = s["example"] or " ".join(cmd.split())[:90]
    return shapes


def suggest(shape: str) -> str:
    words = [w for w in re.findall(r"[a-z][a-z0-9.]*", shape.lower()) if w not in ("p", "s", "n", "id")][:2]
    return "-".join(words) + ".sh" if words else "repeat.sh"


def report(shapes: dict[str, dict]) -> list[str]:
    rows = sorted(
        ((v["n"], len(v["sessions"]), v["example"], k) for k, v in shapes.items() if v["n"] >= MIN_COUNT and len(v["sessions"]) >= MIN_SESSIONS),
        reverse=True,
    )
    return [f"{n}x {sess} sessions  {ex}  -> {suggest(k)}" for n, sess, ex, k in rows[:TOP]]


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    days = float(argv[0]) if argv else 7
    for line in report(scan(Path.home() / ".claude" / "projects", days)):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
