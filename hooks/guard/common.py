"""Shared helpers for the guard hooks: transcript scan, per-session JSON state, debounce, hook output."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
TAIL_BYTES = 400_000
STATE_ROOT_ENV = "CLAUDE_GUARD_STATE_DIR"


def state_dir() -> Path:
    override = os.environ.get(STATE_ROOT_ENV)
    return Path(override) if override else Path.home() / ".claude" / "hookstate"


def _state_path(session: str) -> Path:
    safe = "".join(c for c in session if c.isalnum() or c in "-_") or "anon"
    return state_dir() / f"{safe}.json"


def load_state(session: str) -> dict:
    try:
        data = json.loads(_state_path(session).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(session: str, state: dict) -> None:
    path = _state_path(session)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), "utf-8")
    except OSError:
        pass


def debounced(state: dict, key: str, seconds: float) -> bool:
    """True when `key` already fired within `seconds`; otherwise records now and returns False."""
    fired = state.setdefault("debounce", {})
    now = time.time()
    if now - fired.get(key, 0) < seconds:
        return True
    fired[key] = now
    return False


def read_events() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def records(transcript: str, tail_bytes: int = TAIL_BYTES) -> list[dict]:
    path = Path(transcript) if transcript else None
    if path is None or not path.is_file():
        return []
    with path.open("rb") as fh:
        fh.seek(max(0, path.stat().st_size - tail_bytes))
        lines = fh.read().decode("utf-8", "replace").splitlines()
    out = []
    for raw in lines:
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _blocks(rec: dict) -> list[dict]:
    message = rec.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def is_prompt(rec: dict) -> bool:
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return False
    origin = rec.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    blocks = _blocks(rec)
    return bool(blocks) and all(b.get("type") in ("text", "image", "document") for b in blocks) and bool(prompt_text(rec).strip())


def is_handback(rec: dict) -> bool:
    """A subagent hand-back or task-notification delivered as a user-side record."""
    origin = rec.get("origin")
    return rec.get("type") == "user" and not rec.get("isSidechain") and isinstance(origin, dict) and origin.get("kind") in ("peer", "task-notification")


def prompt_text(rec: dict) -> str:
    return "\n".join(str(b.get("text", "")) for b in _blocks(rec) if b.get("type") == "text")


def tool_uses(recs: list[dict]) -> list[dict]:
    """Every tool_use block, in order."""
    return [
        b
        for r in recs
        if r.get("type") == "assistant"
        for b in _blocks(r)
        if b.get("type") == "tool_use"
    ]


def denied_ids(recs: list[dict]) -> set[str]:
    """tool_use ids whose result is an error (hook refusal, failed spawn): those calls never ran."""
    ids = set()
    for r in recs:
        for b in _blocks(r):
            if b.get("type") != "tool_result" or not b.get("is_error"):
                continue
            ids.add(str(b.get("tool_use_id")))
    return ids


TRIVIAL_CMD = frozenset({"git", "ls", "cat", "cd", "echo", "pwd", "head", "tail", "wc", "true", "mkdir", "dir", "sleep"})
_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")
_PATHY = re.compile(r"\S*[/\\]\S*|~\S*")
_ID = re.compile(r"\b[0-9a-f]{7,}(?:-[0-9a-f]+)*\b", re.IGNORECASE)
_NUM = re.compile(r"\b\d+\b")


def bash_shape(cmd: str) -> str:
    """Command with quoted strings, paths, ids and numbers replaced by placeholders; "" for trivial or scripted ones."""
    words = cmd.split()
    if not words or words[0] in TRIVIAL_CMD or "/.claude/tools/" in cmd.replace("\\", "/") or "~/.claude/tools" in cmd:
        return ""
    shape = _QUOTED.sub("S", cmd)
    shape = _PATHY.sub("P", shape)
    shape = _NUM.sub("N", _ID.sub("ID", shape))
    return " ".join(shape.split())[:200]


def last_prompt(recs: list[dict]) -> str:
    for rec in reversed(recs):
        if is_prompt(rec):
            return prompt_text(rec)
    return ""


SUB_MARKER = "[sub-session]"
SUB_RULES = (
    f"{SUB_MARKER} Rules enforced by hooks: do the work yourself (Sonnet workers "
    "at most, run in the foreground); don't message other sessions; end your turn only when the task is done or "
    "blocked; every reply is 3 lines or fewer (commit, proof, what's left)."
)
SUB_HEAD_BYTES = 200_000


def is_sub_session(transcript: str, state: dict) -> bool:
    """A session started by another via start_session: its first prompt carries SUB_MARKER. Cached in state."""
    if "sub" not in state:
        path = Path(transcript) if transcript else None
        if path is None or not path.is_file():
            return False
        with path.open("rb") as fh:
            head = fh.read(SUB_HEAD_BYTES).decode("utf-8", "replace").splitlines()
        first = ""
        for raw in head:
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict) and is_prompt(rec):
                first = prompt_text(rec)
                break
        if not first:
            return False
        state["sub"] = SUB_MARKER in first
    return bool(state["sub"])


def _calls_after(recs: list[dict], at: int, current_id: str) -> list[dict]:
    """Tool calls after index `at`, deduped by id; the running call (already in the transcript) is excluded."""
    seen: set[str] = set()
    out = []
    for use in tool_uses(recs[at + 1 :]):
        uid = str(use.get("id") or "")
        if uid and (uid == current_id or uid in seen):
            continue
        seen.add(uid)
        out.append(use)
    return out


def calls_since_prompt(recs: list[dict], current_id: str = "") -> list[dict]:
    at = max((i for i, r in enumerate(recs) if is_prompt(r)), default=-1)
    return _calls_after(recs, at, current_id)


def turn_records(recs: list[dict]) -> list[dict]:
    at = max((i for i, r in enumerate(recs) if is_prompt(r) or is_handback(r)), default=-1)
    return recs[at + 1 :]


def calls_since_turn(recs: list[dict], current_id: str = "") -> list[dict]:
    """Like calls_since_prompt, but a subagent hand-back or task-notification also restarts the count."""
    at = max((i for i, r in enumerate(recs) if is_prompt(r) or is_handback(r)), default=-1)
    return _calls_after(recs, at, current_id)


def last_assistant_text(recs: list[dict]) -> str:
    for rec in reversed(recs):
        if rec.get("type") != "assistant":
            continue
        texts = [str(b.get("text", "")) for b in _blocks(rec) if b.get("type") == "text"]
        if texts:
            return texts[-1]
    return ""


def edited_files(recs: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for use in tool_uses(recs):
        if use.get("name") in EDIT_TOOLS:
            params = use.get("input") or {}
            path = params.get("file_path") or params.get("notebook_path")
            if path:
                seen[str(path)] = None
    return list(seen)


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def allow_with(updated: dict, note: str = "") -> dict:
    out = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": updated,
    }
    if note:
        out["additionalContext"] = note
    return {"hookSpecificOutput": out}


def advise(event_name: str, note: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": note}}


def emit(output: dict | None) -> None:
    if output:
        sys.stdout.write(json.dumps(output))
