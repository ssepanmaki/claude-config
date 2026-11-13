"""UserPromptSubmit + SessionStart: surface answered/open agent asks. `python -I asks_hook.py`."""

from __future__ import annotations

import contextlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import ask
import common

MAX_LINES = 15
TOOL = "python3 ~/.claude/tools/ask.py"


def _same(a: str, b: str) -> bool:
    return a.replace("%20", " ").replace("\\", "/").rstrip("/").lower() == b.replace("\\", "/").rstrip("/").lower()


def lines_for(session: str, cwd: str) -> list[str]:
    out: list[str] = []
    asks = [a for a in ask.load() if not a.done]
    for a in (x for x in asks if x.answer):
        agent = a.meta.get("agent", "")
        if a.meta.get("sid") == session and agent:
            out.append(f"Agent {agent} asked `{a.question}`, Dat answered `{a.answer}`: SendMessage it the answer, then `{TOOL} done {a.id}`.")
        elif cwd and _same(a.meta.get("cwd", ""), cwd):
            out.append(f"Earlier agent ask {a.id} `{a.question}`, Dat answered `{a.answer}`: use it as context, then `{TOOL} done {a.id}`.")
    out = out[: MAX_LINES - 1]
    waiting = sum(1 for a in asks if not a.answer)
    if waiting:
        out.append(f"{waiting} agent ask(s) still open for Dat (`{TOOL} list --open`).")
    return out


def main() -> None:
    event = common.read_events()
    lines = lines_for(str(event.get("session_id") or ""), str(event.get("cwd") or ""))
    if lines:
        common.emit(common.advise(str(event.get("hook_event_name") or "UserPromptSubmit"), "\n".join(lines)))


if __name__ == "__main__":
    with contextlib.suppress(Exception):
        main()
    sys.exit(0)
