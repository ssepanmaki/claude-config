"""Stop guards. Run as `python -I stop.py`: hook event JSON on stdin, hook output JSON on stdout."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import session

IDLE_BLOCKS = 3
SHOWN = 8
GIT_TIMEOUT_S = 15
ASK_BACK = re.compile(r"\b(?:want me to|should I|shall I|do you want|would you like)\b[^.?]*\?\s*$", re.IGNORECASE)
OPEN_ASK = re.compile(r"\b(?:something|anything|which|what)\b", re.IGNORECASE)
USER_ONLY = re.compile(r"\b(?:publish|push|deploy|merge|delete|creds?|credentials|sign(?:ed|ing)?[ -]?in|pay|purchase)\w*", re.IGNORECASE)
DOC_FILE = re.compile(r"\.(?:md|txt|tsv)$", re.IGNORECASE)
IMPERATIVE = re.compile(
    r"^\W*(?:please\s+)?(?:fix|do|run|implement|ship|add|make|build|update|change|write|create|deploy|merge|push|commit|continue|go)\b",
    re.IGNORECASE,
)
ASKED_INSTEAD = (
    "Turn ended on a question although the user's last prompt states the action. Do the step now; "
    "end on a question only for a real fork."
)
ASKED_PERMISSION = (
    "Turn ended asking permission for a next step. If the step is known, do it now. Only a real fork or a "
    "user-only step may end the turn - then end again."
)
PROOF_CLAIM = re.compile(
    r"\b(?:green|should (?:now )?(?:be fixed|work|pass)|done|fixed|passes|passing|works now|shipped)\b", re.IGNORECASE
)
TEST_CMD = re.compile(
    r"\b(?:pytest|ruff|tsc|vitest|jest)\b|\bnpm\s+(?:run\s+)?test\b|\bcargo\s+test\b|\bgo\s+test\b"
)
SHELLS = frozenset({"Bash", "PowerShell"})
BROWSER_TOOL = re.compile(r"^mcp__.*(?:browser|preview|playwright).*$", re.IGNORECASE)
UI_FILE = re.compile(r"\.(?:tsx|jsx|css|scss|html|vue|svelte)$")
SUPPRESSION = re.compile(
    r"#\s*type:\s*ignore|#\s*noqa|@pytest\.mark\.(?:skip|xfail)|pytest\.skip\(|"
    r"\b(?:it|test|describe)\.(?:skip|todo)\(|\bxit\(|@ts-(?:ignore|expect-error)|eslint-(?:disable)"
)
STRING_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
TEST_FILE = re.compile(r"(?:^|/)(?:tests?/|test_[^/]*\.py$|[^/]*_test\.py$|[^/]*\.(?:test|spec)\.[cm]?[jt]sx?$)")
GATE_CONFIG = re.compile(
    r"(?:^|/)(?:pyproject\.toml|setup\.cfg|ruff\.toml|mypy\.ini|pytest\.ini|conftest\.py|"
    r"tsconfig[^/]*\.json|eslint\.config\.[cm]?[jt]s|\.eslintrc[^/]*|biome\.jsonc?|\.github/workflows/[^/]+)$"
)
ASSERTION = re.compile(r"\bassert\b|\bassert\w*\(|\bexpect\(|\.to(?:Be|Equal|Throw|Match)\w*\(|pytest\.raises\(")
AGENT_STARTED = re.compile(r"async_launched\W+agentId\W+(\w+)")
AGENT_RESUMED = re.compile(r"resumedAgentId\W+(\w+)")
_ONE_NOTICE = r"(?:(?!</task-notification>).){0,400}?"
AGENT_ENDED = re.compile(rf"<task-id>(\w+)</task-id>{_ONE_NOTICE}<status>(?:completed|failed|killed)</status>", re.DOTALL)
AGENT_ENDED_STATUS_FIRST = re.compile(rf"<status>(?:completed|failed|killed)</status>{_ONE_NOTICE}<task-id>(\w+)</task-id>", re.DOTALL)
ASKS = re.compile(r'\\?"(?:ask|blocked)\\?"\s*:\s*(?:\\?"[^"\\]|true)')
SUB_MAX_LINES = 3
SUB_MAX_CHARS = 600
SUB_TALK = (
    "Sub-session: the reply is {lines} lines / {chars} chars. Rewrite it in {max_lines} lines and {max_chars} chars "
    "or fewer: commit, proof, what's left. No narration."
)
DIRTY_MAIN = (
    "Uncommitted changes on main in the main checkout ({files}). Commit them, or stash them with a note, "
    "then end the turn."
)


def running_agents(text: str) -> list[str]:
    """Async Agent ids whose latest launch or resume comes after their latest completed/failed/killed notice."""
    started = {m.group(1): m.start() for m in AGENT_STARTED.finditer(text)}
    for m in AGENT_RESUMED.finditer(text):
        started[m.group(1)] = m.start()
    ended = {m.group(1): m.start() for m in AGENT_ENDED.finditer(text)}
    for m in AGENT_ENDED_STATUS_FIRST.finditer(text):
        ended[m.group(1)] = max(ended.get(m.group(1), -1), m.start())
    return [a for a in started if started[a] > ended.get(a, -1)]


def waits_on_dat(tail: str) -> bool:
    """True when the last turn-closing call asks the user something."""
    closing = max(tail.rfind('"name":"mcp__ccd_turn__wrap_up"'), tail.rfind('"name": "mcp__ccd_turn__wrap_up"'), tail.rfind('"AskUserQuestion"'))
    if closing < 0:
        return False
    call = tail[closing : closing + 4000]
    return "AskUserQuestion" in call[:40] or bool(ASKS.search(call))


def _ends_on_question(text: str) -> bool:
    return (text.strip().splitlines() or [""])[-1].rstrip().endswith("?")


def ask_reason(text: str, prompt: str) -> str:
    tail = (text.strip().splitlines() or [""])[-1][-300:]
    user_only = USER_ONLY.search(text.strip()[-300:])
    asks = bool(ASK_BACK.search(tail)) and not OPEN_ASK.search(tail) and not user_only
    if asks:
        return ASKED_PERMISSION
    if _ends_on_question(text) and IMPERATIVE.match(prompt) and not OPEN_ASK.search(tail) and not user_only:
        return ASKED_INSTEAD
    return ""


def _is_evidence(use: dict) -> bool:
    name = str(use.get("name") or "")
    if name in SHELLS:
        return bool(TEST_CMD.search(str((use.get("input") or {}).get("command") or "")))
    return bool(BROWSER_TOOL.match(name))


def proof_reason(recs: list[dict], text: str) -> str:
    """Done wording with no test run after the last edit; a UI change also needs a browser call."""
    since = common.calls_since_prompt(recs)
    edits = [
        i for i, u in enumerate(since)
        if u.get("name") in common.EDIT_TOOLS and not DOC_FILE.search(str((u.get("input") or {}).get("file_path") or ""))
    ]
    if not edits or not PROOF_CLAIM.search(text):
        return ""
    after = since[edits[-1] + 1 :]
    if not any(_is_evidence(u) for u in after):
        return "Done wording with no test, lint or build run after your last edit. Run it and report the result, or say unverified."
    edited_ui = [p for p in common.edited_files(recs) if UI_FILE.search(p)]
    if edited_ui and not any(BROWSER_TOOL.match(str(u.get("name") or "")) for u in after):
        return "UI change called done with no browser evidence after the last edit. Load it, take a screenshot, give its path."
    return ""


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S, cwd=cwd, check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return done.returncode, done.stdout


def _repo_root(path: Path) -> Path | None:
    return next((p for p in (path, *path.parents) if (p / ".git").exists()), None)


def _session_repos(edited: list[str]) -> dict[Path, set[str]]:
    repos: dict[Path, set[str]] = {}
    for raw in edited:
        path = Path(raw)
        root = _repo_root(path.parent)
        if root:
            repos.setdefault(root, set()).add(Path(os.path.relpath(path, root)).as_posix().casefold())
    return repos


def _diff(base: Path, files: list[str]) -> str:
    code, out = _git(["diff", "-U0", "HEAD", "--", *files], base)
    return out if code == 0 else ""


def _added_lines(base: Path, files: list[str]) -> list[tuple[str, int, str]]:
    added: list[tuple[str, int, str]] = []
    name, line_no = "", 0
    for raw in _diff(base, files).splitlines():
        if raw.startswith("+++ "):
            name = raw[6:] if raw.startswith("+++ b/") else ""
        elif match := HUNK.match(raw):
            line_no = int(match.group(1))
        elif raw.startswith("+") and name:
            added.append((name, line_no, raw[1:]))
            line_no += 1
    _, untracked = _git(["ls-files", "--others", "--exclude-standard", "--", *files], base)
    for name in untracked.splitlines():
        text = (base / name).read_text("utf-8", errors="replace")
        added += [(name, n, line) for n, line in enumerate(text.splitlines(), 1)]
    return added


def _removed_lines(base: Path, files: list[str]) -> list[tuple[str, str]]:
    name, out = "", []
    for raw in _diff(base, files).splitlines():
        if raw.startswith("--- "):
            name = raw[6:] if raw.startswith("--- a/") else ""
        elif raw.startswith("-") and name:
            out.append((name, raw[1:]))
    return out


def _changed_mine(base: Path, mine: set[str]) -> list[str]:
    _, tracked = _git(["diff", "--name-only", "HEAD"], base)
    _, untracked = _git(["ls-files", "--others", "--exclude-standard"], base)
    return [n for n in [*tracked.splitlines(), *untracked.splitlines()] if n.casefold() in mine]


def _grader_edits(base: Path, files: list[str]) -> str:
    def is_grader(f: str) -> bool:
        return bool(GATE_CONFIG.search(f))
    code = [f for f in files if not TEST_FILE.search(f) and not is_grader(f)]
    if not code:
        return ""
    tests = [f for f in files if TEST_FILE.search(f)]
    loosened = sorted({n for n, line in _removed_lines(base, tests) if ASSERTION.search(line)}) if tests else []
    hits = [f for f in files if is_grader(f)] + [f"{n} (assertion removed or changed)" for n in loosened]
    if not hits:
        return ""
    return (
        f"{base.name}: edited what grades the code it also changed: {'; '.join(hits[:SHOWN])}. "
        "Revert unless the check itself was wrong; if it was, say why in the reply. Shown once."
    )


def _suppressions(base: Path, files: list[str]) -> str:
    kept = {(n, line.strip()) for n, line in _removed_lines(base, files)}
    hits = [
        f"{n}:{i}: {line.strip()[:120]}"
        for n, i, line in _added_lines(base, files)
        if SUPPRESSION.search(STRING_LITERAL.sub("\"\"", line)) and (n, line.strip()) not in kept
    ]
    if not hits:
        return ""
    more = f" (+{len(hits) - SHOWN} more)" if len(hits) > SHOWN else ""
    return (
        f"{base.name}: newly added suppression(s): {'; '.join(hits[:SHOWN])}{more}. "
        "Fix the cause instead of silencing the check."
    )


def diff_reason(state: dict, edited: list[str]) -> str:
    shown = state.setdefault("grader_shown", [])
    notes = []
    for base, mine in _session_repos(edited).items():
        files = _changed_mine(base, mine)
        if not files:
            continue
        grader = _grader_edits(base, files)
        if grader and grader not in shown:
            shown.append(grader)
            notes.append(grader)
        notes.append(_suppressions(base, files))
    return " ".join(n for n in notes if n)


def dirty_main_reason(cwd: str, edited: list[str]) -> str:
    if not cwd or not Path(cwd).is_dir():
        return ""
    base = Path(cwd)
    code, top = _git(["rev-parse", "--show-toplevel"], base)
    status_code, status = _git(["status", "--porcelain=v1", "-b", "--untracked-files=all"], base)
    lines = status.splitlines()
    if code or status_code or not lines or not re.match(r"## main(?:\.\.\.|$)", lines[0]):
        return ""
    root = Path(top.strip())
    if not (root / ".git").is_dir():
        return ""
    def norm(p: str) -> str:
        return os.path.normcase(os.path.normpath(p))
    dirty = {norm(str(root / ln[3:].split(" -> ")[-1].strip('"'))) for ln in lines[1:] if len(ln) > 3}
    mine = {norm(p) for p in edited}
    stranded = sorted(p for p in dirty if p in mine and Path(p).exists())
    if not stranded:
        return ""
    names = ", ".join(Path(p).name for p in stranded[:5]) + (", ..." if len(stranded) > 5 else "")
    return DIRTY_MAIN.format(files=names)


def sub_talk_reason(transcript: str, state: dict, text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if (len(lines) <= SUB_MAX_LINES and len(text) <= SUB_MAX_CHARS) or not common.is_sub_session(transcript, state):
        return ""
    return SUB_TALK.format(lines=len(lines), chars=len(text), max_lines=SUB_MAX_LINES, max_chars=SUB_MAX_CHARS)


def _idle_block(state: dict, calls: int) -> bool:
    """Counts a block; resets when the session made a tool call since the last one."""
    blocks, seen = state.get("idle", [0, -1])
    blocks = 0 if calls != seen else blocks
    if blocks >= IDLE_BLOCKS:
        return False
    state["idle"] = [blocks + 1, calls]
    return True


def decide(event: dict, state: dict) -> dict | None:
    if event.get("stop_hook_active"):
        return None
    transcript = str(event.get("transcript_path") or "")
    recs = common.records(transcript)
    if not recs:
        return None
    raw_tail = _raw_tail(transcript)
    if waits_on_dat(raw_tail) or running_agents(raw_tail):
        return None
    text = str(event.get("last_assistant_message") or common.last_assistant_text(recs))
    edited = common.edited_files(recs)
    reason = (
        sub_talk_reason(transcript, state, text)
        or ask_reason(text, common.last_prompt(recs))
        or proof_reason(recs, text)
        or (diff_reason(state, edited) if edited else "")
        or dirty_main_reason(str(event.get("cwd") or ""), edited)
    )
    if not reason or not _idle_block(state, len(common.tool_uses(recs))):
        return None
    return {"decision": "block", "reason": reason}


def _raw_tail(transcript: str) -> str:
    path = Path(transcript)
    if not path.is_file():
        return ""
    with path.open("rb") as fh:
        fh.seek(max(0, path.stat().st_size - common.TAIL_BYTES))
        return fh.read().decode("utf-8", "replace")


def prune_work(event: dict) -> None:
    """Prune stale sibling work dirs (<repo>/.tmp/*) of this session's repo."""
    work = session.work_path(str(event.get("cwd") or ""), str(event.get("session_id") or ""), Path.home())
    if work and work.parent.is_dir():
        session.prune(work.parent, work, time.time())


def main() -> None:
    event = common.read_events()
    try:
        prune_work(event)
    except OSError:
        pass
    session = str(event.get("session_id") or "")
    state = common.load_state(session)
    output = decide(event, state)
    common.save_state(session, state)
    common.emit(output)


if __name__ == "__main__":
    main()
