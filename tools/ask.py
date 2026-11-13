"""Agent ask inbox in the vault: `ask.py list [--open|--answered] | answer <id> <text> | done <id>`."""

from __future__ import annotations

import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ASKS_ENV = "CLAUDE_ASKS_FILE"
DEFAULT_FILE = Path("/home/OMISTAJA/obsidian-vault/wiki/agent-asks.md")
HEAD = (
    "---\nsources: []\nsummary: 'Open questions agents filed for Dat; answer on the indented A: line'\n"
    "updated: {day}\n---\n\nAnswer on the indented `  - A:` line under an ask; the lead picks it up next prompt.\n\n"
)
ENTRY = re.compile(r"^- \[( |x)\] (\S+) · (.*?) · (.*?)(?: <!--(.*?)-->)?\s*$")
ANSWER = re.compile(r"^\s+- A:\s*(.*)$")


@dataclass
class Ask:
    id: str
    done: bool
    repo: str
    question: str
    meta: dict
    answer: str
    line: int


def path() -> Path:
    override = os.environ.get(ASKS_ENV)
    return Path(override) if override else DEFAULT_FILE


def _meta(raw: str | None) -> dict:
    return dict(p.split("=", 1) for p in (raw or "").split() if "=" in p)


def load() -> list[Ask]:
    try:
        lines = path().read_text("utf-8").splitlines()
    except OSError:
        return []
    asks: list[Ask] = []
    for i, ln in enumerate(lines):
        m = ENTRY.match(ln)
        if m:
            asks.append(Ask(m[2], m[1] == "x", m[3], m[4], _meta(m[5]), "", i))
            continue
        a = ANSWER.match(ln)
        if a and asks and not asks[-1].answer:
            asks[-1].answer = a[1].strip()
    return asks


def file_ask(question: str, cwd: str = "", session: str = "", agent: str = "", kind: str = "") -> str:
    ask_id = uuid.uuid4().hex[:4]
    repo = Path(cwd.replace("\\", "/")).name or "?"
    meta = f"sid={session} agent={agent} type={kind} cwd={cwd.replace(' ', '%20')} date={date.today()}"
    q = " ".join(question.split())
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        target.write_text(HEAD.format(day=date.today()), "utf-8")
    with target.open("a", encoding="utf-8") as fh:
        fh.write(f"- [ ] {ask_id} · {repo} · {q} <!-- {meta} -->\n")
    return ask_id


def answer(ask_id: str, text: str) -> bool:
    hit = next((a for a in load() if a.id == ask_id), None)
    if hit is None:
        return False
    lines = path().read_text("utf-8").splitlines()
    nxt = hit.line + 1
    reply = f"  - A: {text}"
    if nxt < len(lines) and ANSWER.match(lines[nxt]):
        lines[nxt] = reply
    else:
        lines.insert(nxt, reply)
    path().write_text("\n".join(lines) + "\n", "utf-8")
    return True


def done(ask_id: str) -> bool:
    hit = next((a for a in load() if a.id == ask_id), None)
    if hit is None:
        return False
    lines = path().read_text("utf-8").splitlines()
    lines[hit.line] = lines[hit.line].replace("- [ ]", "- [x]", 1)
    path().write_text("\n".join(lines) + "\n", "utf-8")
    return True


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        flag = argv[1] if len(argv) > 1 else ""
        for a in load():
            if a.done or (flag == "--open" and a.answer) or (flag == "--answered" and not a.answer):
                continue
            print(f"{a.id} · {a.repo} · {a.question}" + (f"\n  A: {a.answer}" if a.answer else ""))
        return 0
    if cmd == "answer" and len(argv) >= 3:
        ok = answer(argv[1], " ".join(argv[2:]))
    elif cmd == "done" and len(argv) == 2:
        ok = done(argv[1])
    else:
        print(__doc__)
        return 2
    print("ok" if ok else "no such ask")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
