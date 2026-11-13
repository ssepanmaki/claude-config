"""PreCompact / SessionStart(compact): save a short resume note before compaction, replay it after."""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

MAX_LINES = 60
BIG_TAIL = 2_000_000
AGENT_ID = re.compile(r"agentId[\"']?:\s*[\"']?([A-Za-z0-9]+)")
MSG_FROM = re.compile(r"<agent-message from=\\?[\"']([A-Za-z0-9]+)")
TASK_ID = re.compile(r"<task-id>\s*([A-Za-z0-9]+)\s*</task-id>")
NOT_TYPED = ("<agent-message", "<artifact-content-authored-by-others", "<command-", "<local-command-", "<task-notification", "This session is being continued")


def typed_prompt(rec: dict) -> bool:
    if rec.get("isCompactSummary") or not common.is_prompt(rec):
        return False
    text = common.prompt_text(rec).strip()
    if text.startswith(NOT_TYPED):
        return False
    return bool(re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL).strip())


def finished_ids(recs: list[dict]) -> set[str]:
    done = set()
    for r in recs:
        if r.get("type") != "user":
            continue
        text = json.dumps(r.get("message"))
        done.update(MSG_FROM.findall(text))
        if "<task-notification" in text and re.search(r"status>\s*completed", text):
            done.update(TASK_ID.findall(text))
    return done


def note_path(session: str) -> Path:
    safe = "".join(c for c in session if c.isalnum() or c in "-_") or "anon"
    return Path.home() / ".claude" / "state" / "compact" / f"{safe}.md"


def git(cwd: str, *args: str) -> list[str]:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=8, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return out.splitlines()[:15]


def build(event: dict) -> str:
    recs = common.records(str(event.get("transcript_path") or ""), BIG_TAIL)
    uses = common.tool_uses(recs)
    lines = ["## Resume note (written before compaction)", "### Last user prompts"]
    prompts = [common.prompt_text(r).strip() for r in recs if typed_prompt(r)]
    lines += [f"- {' '.join(p.split())[:300]}" for p in prompts[-3:]]
    plans = [u for u in uses if str(u.get("name", "")).endswith("update_plan")]
    if plans:
        lines.append("### Plan")
        for item in (plans[-1].get("input") or {}).get("items") or []:
            if isinstance(item, dict):
                lines.append(f"- [{item.get('status', '?')}] {str(item.get('content', ''))[:120]}")
    results = {str(b.get("tool_use_id")): str(b.get("content")) for r in recs for b in common._blocks(r) if b.get("type") == "tool_result"}
    handed = {str((r.get("origin") or {}).get("senderTaskId")) for r in recs if common.is_handback(r)} | finished_ids(recs)
    open_agents = []
    for u in uses:
        if u.get("name") != "Agent":
            continue
        uid = str(u.get("id"))
        found = AGENT_ID.search(results.get(uid, ""))
        if uid not in results or (found and found.group(1) not in handed):
            open_agents.append((u, found.group(1) if found else uid))
    if open_agents:
        lines.append("### Agents without hand-back")
        for u, aid in open_agents:
            p = u.get("input") or {}
            lines.append(f"- {str(p.get('description', ''))[:80]} ({p.get('subagent_type', 'general-purpose')}, id {aid})")
    files = common.edited_files(recs)
    if files:
        lines.append("### Edited files")
        lines += [f"- {f}" for f in files[-15:]]
    cwd = str(event.get("cwd") or "") or "."
    status, log = git(cwd, "status", "--short"), git(cwd, "log", "--oneline", "-5")
    if status or log:
        lines.append("### Git")
        lines += [f"  {x}" for x in [*status, *log]]
    return "\n".join(lines[:MAX_LINES]) + "\n"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    event = common.read_events()
    session = str(event.get("session_id") or "")
    path = note_path(session)
    if mode in ("precompact", "sessionstart"):
        state = common.load_state(session)
        state.pop("reads", None)
        common.save_state(session, state)
    if mode == "precompact":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build(event), "utf-8")
    elif mode == "sessionstart" and path.is_file():
        common.emit(common.advise("SessionStart", path.read_text("utf-8")))


if __name__ == "__main__":
    with contextlib.suppress(Exception):
        main()
    sys.exit(0)
