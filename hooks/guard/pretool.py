"""PreToolUse guards. Run as `python -I pretool.py`: hook event JSON on stdin, hook output JSON on stdout."""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import repeats_hint
import session as work_dir

REPEAT_LIMIT = 3
READ_STREAK_LIMIT = 8
REPEAT_EDIT_FILES = 5
REPEAT_EDIT_MAX_CHARS = 300
EDIT_CHURN_LIMIT = 20
GREP_CAP = 30
BOUNDED_READ_MAX_LINES = 200
READ_MAX_BYTES = 24_000
READ_FILE_BUDGET = 72_000
IMAGE_MAX_BYTES = 200_000
AGENT_IMAGE_CAP = 20
CROP_CMD = "crop first: `node ~/.claude/tools/review.mjs <url> <out_dir> --sel <css>` (2x crop of one element)"
READ_MAX_LINES = 2000
CALL_HINT = 120
STREAK_EXEMPT = frozenset({"auditor", "board-auditor", "scout", "Explore", "Plan", "claude-code-guide"})
SCREENSHOT_SCALE = 0.5
STREAK_TOOLS = frozenset({"Read", "Grep", "Glob"})
CODE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".cs", ".go", ".rs", ".java", ".sql"})
LEAD_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
BARE_WILDCARD = re.compile(r"^(\*\*/)*\*+(\.\*)?$")
BROWSER_COMPUTER = re.compile(r"^mcp__.*__computer$")
BROWSER_BATCH = re.compile(r"^mcp__.*__browser_batch$")
SHELLS = ("Bash", "PowerShell")
SLEEP_MAX_S = 30
SLEEP = re.compile(r"(?:^|[;&|(\s])(?:sleep|Start-Sleep(?:\s+-Seconds|\s+-s)?)\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
SLEEP_ONLY_PARTS = re.compile(
    r"\bfor\s+\w+\s+in\s+[^;\n]*[;\n]|\bwhile\s+(?:true|:)\s*[;\n]|\b(?:do|done)\b"
    r"|\b(?:sleep|Start-Sleep(?:\s+-Seconds|\s+-s)?)\s+\d+(?:\.\d+)?|[;&\s]",
    re.IGNORECASE,
)
FIND_HUGE = re.compile(
    r"(?:^|[;&|(\n])\s*find\s+(?:-[HLP]\s+)?[\"']?(?:(?:/|~|\$HOME|\$\{HOME\}|/c/Users/OMISTAJA|/home/OMISTAJA|C:[/\\]Users[/\\]OMISTAJA)/?[\"']?(?=\s|$)|[^\s\"']*AppData[/\\]Local[/\\]Temp)",
    re.IGNORECASE,
)
CURL = re.compile(r"(?:^|[;&|(\n])\s*curl\s")
STDIN_CAT = re.compile(r"(?:^|[;&(\n])\s*cat(?:\s+-)?(?=\s*(?:$|[;&)>\n]|\|(?!\|)))(?![^;&|\n]*<)", re.MULTILINE)
CURL_TIMEOUT = re.compile(r"\s(?:--max-time|--connect-timeout|-[A-Za-z]*m)(?=[\s=\d]|$)")
POLL_LOOP = re.compile(r"^\s*(?:until|while|for)\b[^\n]*?\bdo\b.{0,200}?\b(?:sleep|Start-Sleep)\b", re.IGNORECASE | re.DOTALL | re.MULTILINE)
SCRATCH_TARGET = re.compile(r"<<[^\n]*>\s*[\"']?(?:/tmp/|[^\s\"']*(?:AppData[/\\]Local[/\\]Temp|scratchpad))", re.IGNORECASE)
HEREDOC_FILE = re.compile(r"^[^\n]*\b(?:cat|tee)\b[^\n]*<<-?\s*[\"']?\w|^[^\n]*<<-?\s*[\"']?\w[^\n]*>\s*[\w./~$\"']", re.MULTILINE)
HEREDOC_OK = re.compile(r"\b(?:python3?|node|git|psql|sqlite3|ssh)\b[^\n]*<<|<<[^\n]*\|\s*(?:python3?|node|bash|sh|psql|sqlite3)\b")
GIVE_LINE = re.compile(r"\b(?:give me the (?:line|command)|what(?:'s| is) the command)\b", re.IGNORECASE)
READ_ONLY_CMD = re.compile(r"^\s*(?:git\s+(?:status|diff|log|show)|ls|dir|cat|echo|pwd)\b")
LINE_ONLY = "Dat asked for the line, not a run: reply with the one command string, explanation after, and run nothing."
RULE_WORD = re.compile(r"[a-z]{5,}")
APPROVAL = re.compile(r"^\W*(?:yes|yep|ok(?:ay)?|sure|go ahead|do it|all|all plz|please do|approved)\b.{0,20}$", re.IGNORECASE)
VOLATILE_PARAMS = frozenset({"run_in_background", "timeout", "description"})
START_SESSION = re.compile(r"^mcp__.*__start_session$")
NO_COORDINATOR = "No `coordinator`: it is retired. Sizeable work runs the `ship-batch` workflow with a plan file; small work, brief a Sonnet `worker` directly."
BUILTIN_AGENTS = frozenset({"general-purpose", "Explore", "explore", "Plan", "claude"})
NO_BUILTIN = "No `{kind}` agent: it has no turn cap or brief. Edits or multi-step work → `worker` (Sonnet); find/read → `scout` (Haiku)."
SUB_NO_PING ="Sub-session: don't message other sessions. Your final reply at the end of the task is the only report."
SUB_FOREGROUND = "Sub-session: agents run in the foreground so the turn ends only when the task is done."
AGENT_FOREGROUND = (
    "Inside an agent, child agents run in the foreground: a background child makes you stop and re-wake, and every "
    "stop pings the lead. Launch parallel workers as several Agent calls in one message; you hand back once."
)
HEDGE = re.compile(
    r"\b(?:unverified|unchecked|unmeasured|left open|per the worker|partly|"
    r"not (?:yet )?(?:verified|checked|measured|viewed|seen|shot|re-?run|tested|fixed|done|confirmed)|"
    r"(?:did not|didn't|have not|haven't) (?:check|verify|measure|shoot|run|re-?run|test|fix|confirm|look))\b",
    re.IGNORECASE,
)
BLOCKED_LINE = re.compile(r"\bblocked\b", re.IGNORECASE)
SUITE = re.compile(
    r"^\s*(?:npm|pnpm|yarn)\s+(?:run\s+)?(?:test|build)\b|^\s*npx\s+vitest\b|^\s*vitest\b|^\s*(?:python\s+-m\s+)?pytest\b",
    re.IGNORECASE,
)
SUITE_TARGET = re.compile(r"\S+\.(?:test|spec)\.\w+|\S+/\S+\.(?:ts|tsx|js|mjs|py)\b|\S+::\S+|\s-k\s")
NO_MODEL = "Agent call without `model`: pass `model: \"sonnet\"` (or haiku). Opus agents are banned."
NO_OPUS = "Opus agents are banned: use `model: \"sonnet\"`."
WORKFLOW_OPUS = re.compile(r"\bmodel\s*:\s*[\"'`][^\"'`]*opus", re.IGNORECASE)
NO_WORKFLOW_OPUS = "Workflow script sets an Opus model on an agent(): Opus agents are banned, use `model: 'sonnet'` or omit it."
SHIPPERS = frozenset({"shipper"})
AGENTS_DIR = Path.home() / ".claude" / "agents"
BUILTIN_READERS = frozenset({"Explore", "claude-code-guide", "Plan"})
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


def read_only_agents(agents_dir: Path = AGENTS_DIR) -> frozenset[str]:
    """Built-in readers plus every agents/*.md whose frontmatter `tools:` lists no write tool."""
    names = set(BUILTIN_READERS)
    for f in agents_dir.glob("*.md"):
        head = f.read_text("utf-8", "replace").split("---")
        meta = head[1] if len(head) > 2 and not head[0].strip() else ""
        name = re.search(r"^name:\s*(\S+)", meta, re.MULTILINE)
        tools = re.search(r"^tools:\s*(.+)$", meta, re.MULTILINE)
        if name and tools and not WRITE_TOOLS & set(re.split(r"[\s,]+", tools.group(1))):
            names.add(name.group(1))
    return frozenset(names)


READ_ONLY_AGENTS = frozenset(n for a in read_only_agents() - SHIPPERS for n in (a, a.lower()))  # events send `explore`
LEAD_READERS = 2
LEAD_SOLOS = 3
LEAD_MESSAGES = 3
LEAD_CALL_CAP = 25
LEAD_WARN_AT = 22
LEAD_IMAGE_CAP = 60
TURN_FREE = re.compile(r"^(?:mcp__ccd_turn__\w+|Agent|ToolSearch)$")
UNCOUNTED = frozenset({"Agent", "SendMessage", "TaskStop"})
GATE_SEGMENT = re.compile(
    r"^\s*(?:cd\s+\S+|ruff\b[^>]*|mypy\b[^>]*|pytest\b[^>]*|python3?\s+(?:-I\s+)?-m\s+(?:ruff|pytest|mypy)\b[^>]*"
    r"|npx\s+(?:tsc|eslint)\b[^>]*|node\s+--test\b[^>]*|npm\s+(?:run\s+)?test\b[^>]*|(?:head|tail)(?:\s+-n?\s*\d+)?)\s*$"
)
PLAN_READ = re.compile(r"(?:plan[\w.-]*|status[\w.-]*)\.md$", re.IGNORECASE)
PLANS_PATH = re.compile(r"[/\\]\.claude[/\\]plans[/\\]", re.IGNORECASE)
LEAD_TOO_LONG = "Budget hit: write the plan to ~/.claude/plans/ and run the `ship-batch` workflow on it, or tell Dat what is left."
LEAD_NEAR_CAP = "3 calls left: write the plan and run the `ship-batch` workflow on it now"
LEAD_IMAGES_SPENT = f"Lead image budget ({LEAD_IMAGE_CAP}) spent: send crops review to a board-auditor or the ship-batch workflow."
RM_TEMP_ROOT = re.compile(
    r"(?:\brm\s+(?:-\w*[rR]\w*\s+)+|Remove-Item\b[^\n;|&]*-Recurse\b[^\n;|&]*?)"
    r"[\"']?(?:\S*[/\\])?(?:public[/\\]_tmp|\.tmp(?:[/\\][^/\\\s\"']+)?)[/\\]*[\"']?(?=\s|$|;|&|\|)"
)
RM_TEMP_MSG = "Delete only your own subfolder (public/_tmp/<job>/)."
LEAD_WORKER = (
    "The lead spawns at most 3 solo agents per request. More parallel work: write the plan and run the "
    "`ship-batch` workflow on it."
)
LEAD_FORK = "No `fork` agents: a fork re-reads the lead's whole context on Opus. Use a fresh Sonnet agent with a tight brief."
LEAD_MESSAGES_MAX = (
    f"{LEAD_MESSAGES} SendMessages already this request: end the turn and wait for the hand-back."
)
LEAD_READERS_MAX = f"{LEAD_READERS} read-only agents already this request: do the rest yourself or run the `ship-batch` workflow."
LEAD_MESSENGER = (
    "`{to}` is an agent's worker. Don't relay: the agent owns its "
    "workers. Message its parent or wait for its hand-back."
)
HEAVY = re.compile(r"\b(?:review\.mjs|shotpair\.sh|shot\.mjs|playwright|vite(?:\s|$)|npm\s+run\s+(?:dev|preview))\b")
SLOT = ("python" if os.name == "nt" else "python3") + " -I /home/OMISTAJA/.claude/tools/slot.py"
FULL_GATE = (
    "Full suite/build refused in a subagent: it is slow and floods your context. Allowed: one test file, "
    "e.g. `npx vitest run tests/x.test.ts` or `pytest tests/test_x.py -q`, plus `npm run typecheck` if types moved. "
    "The full gate runs once, at the end, in the shipper or the session."
)
HANDBACK_NO_SHIP = "Shipper hand-back must say `ship <sha>` or `not shipped: <why>`."
HANDBACK_WORKER_ASK = "Workers don't ask Dat: end with `blocked: <question>`; the lead answers."
HANDBACK_LEFT = "Hand-back says `left N` (N>0) with no `blocked: <reason>` or `needs Dat: <question>` line."
SHIP_LINE = re.compile(r"\bship(?:ped)? [0-9a-f]{7,40}\b|\bnot shipped:", re.IGNORECASE)
LEFT_OPEN = re.compile(r"\bleft ([1-9]\d*)\b", re.IGNORECASE)
LEFT_OK = re.compile(r"\bblocked:|\bneeds Dat:|\bneeds-owner:", re.IGNORECASE)
WORKER_OK_LINE = re.compile(r"(?:Caveats?:|needs-owner:)|.*\b(?:fully done|left 0)\b", re.IGNORECASE)
NEEDS_DAT = re.compile(r"\bneeds Dat:\s*(.+)", re.IGNORECASE)
HANDBACK_DIRTY = (
    "Hand-back refused: {lines}. Close each gap first: loop the owning worker back, or check it yourself. "
    "Only a real blocker on Dat (ship, deploy, creds, money, a decision) may stay, on a line starting `N: blocked —`."
)


SCRIPT_RUN = re.compile(r"(?:^|&&|;|\|\|)\s*(?:python3?|node)\s+(?:-[A-Za-z]+\s+)*([^\s;&|<>\"'$~*]+\.(?:py|js|mjs|cjs|ts))")
PATH_TOOLS = {"Read": "file_path", "Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}


def _suggest(path: Path) -> str:
    """Why `path` is missing: the nearest existing parent and its closest name."""
    parent = path.parent
    missing = [path.name]
    while not parent.exists() and parent != parent.parent:
        missing.append(parent.name)
        parent = parent.parent
    try:
        names = os.listdir(parent)
    except OSError:
        return f"{path} not found"
    close = difflib.get_close_matches(missing[-1], names, 1, 0.5)
    if close:
        return f"{path} not found; did you mean {(parent / close[0]).as_posix()}"
    return f"{path} not found (nearest existing dir: {parent.as_posix()})"


def _resolve(raw: str, cwd: str) -> Path | None:
    if not raw or any(c in raw for c in "$~*?"):
        return None
    if os.name == "nt" and raw.startswith("/"):
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return Path(cwd) / path if cwd else None


def path_refusal(event: dict, tool: str, params: dict) -> str | None:
    """Deny a Read/Edit/NotebookEdit/`python|node <file>` on a missing path, and a Write whose parent is missing."""
    cwd = str(event.get("cwd") or "")
    if tool in SHELLS:
        found = SCRIPT_RUN.search(str(params.get("command") or ""))
        if not found or (not Path(found.group(1)).is_absolute() and "cd " in str(params.get("command"))):
            return None
        path = _resolve(found.group(1), cwd)
        return _suggest(path) if path and not path.exists() else None
    key = PATH_TOOLS.get(tool)
    if not key:
        return None
    path = _resolve(str(params.get(key) or ""), cwd)
    if not path or path.exists():
        return None
    if tool == "Write":
        hint = "" if path.parent.exists() else _suggest(path.parent)
        return f"parent dir missing: {hint}" if "did you mean" in hint else None
    if tool == "Edit" and params.get("old_string") == "":
        return None
    return _suggest(path)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower().rstrip("/")


def wide_roots() -> set[str]:
    home = Path.home()
    return {_norm(str(home)), "c:", "c:/users", _norm(str(home.parent))}


def is_wide(path: str) -> bool:
    return bool(path) and _norm(path) in wide_roots()


def repeat_refusal(state: dict, tool: str, params: dict) -> str | None:
    stable = {k: v for k, v in params.items() if k not in VOLATILE_PARAMS}
    key = tool + json.dumps(stable, sort_keys=True, default=str)
    last, count = state.get("last_call", ["", 0])
    count = count + 1 if last == key else 1
    state["last_call"] = [key, count]
    if count < REPEAT_LIMIT:
        return None
    return f"replan: {tool} called {count} times in a row with identical input - change the input or the approach"


def read_streak_refusal(state: dict, tool: str, params: dict, prompts: int, agent_type: str = "") -> str | None:
    """Refuses the call that makes READ_STREAK_LIMIT + 1 reads in a row since the last prompt or edit."""
    if tool in common.EDIT_TOOLS:
        state.pop("streak", None)
        return None
    path = str(params.get("file_path") or params.get("path") or "")
    if tool not in STREAK_TOOLS or Path(path).suffix.lower() in IMAGE_SUFFIXES or agent_type in STREAK_EXEMPT:
        return None
    seen, count = state.get("streak", [prompts, 0])
    count = count + 1 if seen == prompts else 1
    state["streak"] = [prompts, count]
    if count != READ_STREAK_LIMIT + 1:
        return None
    return (
        f"{count} Read/Grep/Glob calls in a row with no edit: this is research, so offload it. Use "
        "codegraph_explore (one call returns the source, callers and blast radius) or hand the reading to an "
        "Agent (haiku scout) that returns only the answer, never the files. An Edit/Write resets the count."
    )


def _is_ranged(params: dict) -> bool:
    return bool(params.get("limit"))


def image_refusal(params: dict, state: dict, who: str) -> str | None:
    """Deny an image over IMAGE_MAX_BYTES, or a second Read of one unchanged since it was first viewed."""
    target = Path(str(params.get("file_path") or ""))
    if target.suffix.lower() not in IMAGE_SUFFIXES or not target.is_file():
        return None
    info = target.stat()
    if info.st_size > IMAGE_MAX_BYTES:
        return (
            f"Image is {info.st_size // 1000} KB (a big image costs ~100K tokens every later turn). Allowed: images up to "
            f"{IMAGE_MAX_BYTES // 1000} KB; make a smaller one: " + CROP_CMD + "."
        )
    seen = state.setdefault("images", {})
    key = f"{who}|{_norm(str(target))}"
    stamp = [info.st_mtime_ns, info.st_size]
    if seen.get(key) == stamp:
        return f"{target.name} is unchanged since you last viewed it: use what you saw. To see a part, " + CROP_CMD + "."
    if who.endswith("|"):
        seen[key] = stamp
        return None
    if state.setdefault("agent_images", {}).get(who, 0) >= AGENT_IMAGE_CAP:
        return f"Image cap ({AGENT_IMAGE_CAP} per agent) spent: hand back what you have and name what is unchecked."
    state["agent_images"][who] = state["agent_images"].get(who, 0) + 1
    seen[key] = stamp
    return None


def read_check(params: dict) -> tuple[str | None, dict | None, str]:
    """(deny reason, rewritten params, note) for a Read."""
    target = Path(str(params.get("file_path") or ""))
    if not target.is_file():
        return None, None, ""
    size = target.stat().st_size
    suffix = target.suffix.lower()
    if suffix in IMAGE_SUFFIXES or suffix == ".pdf":
        return None, None, ""
    if not params.get("offset") and not params.get("limit") and target.read_bytes().count(b"\n") + 1 > READ_MAX_LINES:
        return (
            f"{target.name} is over {READ_MAX_LINES} lines: a whole-file Read floods your context. Allowed: "
            "`Read offset=1 limit=200` (then page on), or Grep -n the block you need."
        ), None, ""
    limit = params.get("limit")
    too_wide = isinstance(limit, int) and limit > BOUNDED_READ_MAX_LINES
    if suffix not in CODE_SUFFIXES and size > READ_MAX_BYTES and too_wide:
        return None, {**params, "limit": BOUNDED_READ_MAX_LINES}, _cut_note(target, size, params)
    if _is_ranged(params):
        return None, None, ""
    unranged_big = size > READ_MAX_BYTES or (
        size > BOUNDED_READ_MAX_LINES and target.read_bytes().count(b"\n") + 1 > BOUNDED_READ_MAX_LINES
    )
    if not unranged_big:
        return None, None, ""
    return None, {**params, "limit": BOUNDED_READ_MAX_LINES}, _cut_note(target, size, params)


def read_budget(params: dict, state: dict, reader: str) -> tuple[str | None, dict | None, str]:
    """read_check, then a byte cap per Read and a byte budget per big file per transcript."""
    reason, updated, note = read_check(params)
    target = Path(str(params.get("file_path") or ""))
    if reason or not target.is_file() or target.suffix.lower() in IMAGE_SUFFIXES | {".pdf"}:
        return reason, updated, note
    size = target.stat().st_size
    if size <= READ_MAX_BYTES:
        return reason, updated, note
    p = updated or params
    lines = target.read_bytes().split(b"\n")
    start = max(int(p.get("offset") or 1), 1) - 1
    limit = int(p.get("limit") or len(lines))
    served, fit = 0, 0
    for line in lines[start:start + limit]:
        if fit and served + len(line) + 1 > READ_MAX_BYTES:
            break
        served += len(line) + 1
        fit += 1
    used = state.setdefault("read_bytes", {})
    key = f"{reader}|{_norm(str(target))}|{int(target.stat().st_mtime)}"
    if used.get(key, 0) + served > READ_FILE_BUDGET:
        return (
            f"{target.name}: {used.get(key, 0) // 1000} KB of it already read here. "
            "Grep -n the block you need and Read only that range, or hand it to an Agent that returns only the answer."
        ), None, ""
    used[key] = used.get(key, 0) + served
    if fit < limit:
        note = f"{target.name} has long lines: Read cut to {fit} lines ({served // 1000} KB) from line {start + 1} (why: one Read is capped at {READ_MAX_BYTES // 1000} KB to protect your context). Grep -n before paging."
        return None, {**p, "offset": start + 1, "limit": fit}, note
    return reason, updated, note


def _cut_note(target: Path, size: int, params: dict) -> str:
    more = (
        "codegraph_explore for the call chain, or Grep -n the symbol"
        if target.suffix.lower() in CODE_SUFFIXES
        else "Grep -n a known string, or hand the file to an Agent that returns only the answer"
    )
    start = params.get("offset") or 1
    return (
        f"{target.name} is {size // 1000} KB: Read cut to {BOUNDED_READ_MAX_LINES} lines from line {start} "
        "(why: a whole big file fills your context and every later turn re-reads it). "
        f"More: Read offset+limit, {more}."
    )


def search_refusal(tool: str, params: dict) -> str | None:
    path = str(params.get("path") or "")
    if is_wide(path) and not (tool == "Grep" and params.get("output_mode") == "count"):
        return "Glob/Grep from the home folder or a drive root times out. Allowed: pass the repo folder, e.g. path=\"/home/OMISTAJA/<repo>\" (Grep output_mode=count works anywhere)."
    pattern = str(params.get("pattern") or "")
    if tool == "Glob" and BARE_WILDCARD.match(pattern) and ("**" in pattern or not path):
        return (
            "Recursive or pathless bare wildcard Glob banned. Name an extension/stem (**/*.py), "
            'or list one named folder with pattern "*" and path; Grep output_mode=count for totals.'
        )
    return None


def shell_refusal(params: dict) -> str | None:
    cmd = str(params.get("command") or "")
    if HEREDOC_FILE.search(cmd) and not HEREDOC_OK.search(cmd) and not SCRATCH_TARGET.search(cmd):
        return (
            "Heredoc file write banned (breaks on quotes, Windows paths). Allowed: the Write tool, then run the file; "
            "no Write tool: pipe the heredoc straight to the interpreter, `python - <<'EOF'` or `cat <<'EOF' | node`."
        )
    if STDIN_CAT.search(cmd):
        return (
            "`cat` with no file and no pipe into it banned: it waits on stdin forever and hangs the shell. "
            "Allowed: `cat <file>`, `... | cat`, `cat <<'EOF'`, or drop it."
        )
    if params.get("run_in_background"):
        if SLEEP.search(cmd) and not SLEEP_ONLY_PARTS.sub("", cmd):
            return (
                "Background sleep-only command banned: a timer is not a wait. Allowed: wait for the notification "
                "of the real background command (gate, test, build), or one Monitor call on its DONE file."
            )
        return None
    if RM_TEMP_ROOT.search(cmd):
        return RM_TEMP_MSG
    if FIND_HUGE.search(cmd) and "-maxdepth" not in cmd:
        return (
            "find over /, ~, the user profile or AppData Temp without -maxdepth banned: it walks a huge tree and hangs. "
            "Allowed: add `-maxdepth N`, or use the Glob tool on a narrow path."
        )
    if CURL.search(cmd) and not CURL_TIMEOUT.search(cmd):
        return "curl without a timeout banned: a stalled host hangs the turn. Allowed: add `-m 5` (or --max-time / --connect-timeout)."
    if POLL_LOOP.search(cmd):
        return (
            "Foreground poll loop banned: it blocks the turn. Allowed: the same command with run_in_background: true "
            "(you are re-invoked on exit), or one Monitor call running `until [ -f DONE ]; do sleep 2; done`."
        )
    if any(float(s) > SLEEP_MAX_S for s in SLEEP.findall(cmd)):
        return f"sleep over {SLEEP_MAX_S}s banned. Allowed: `sleep {SLEEP_MAX_S}` or less, or the command with run_in_background: true."
    return None


def _big_scale(params: dict) -> bool:
    return params.get("action") == "screenshot" and isinstance(params.get("scale"), (int, float)) and params["scale"] > 1


SCALE_MSG = f"Screenshot scale above 1 banned (tokens). Allowed: scale {SCREENSHOT_SCALE} to 1, or a crop via the `region` arg."


def scale_refusal(tool: str, params: dict) -> str | None:
    if BROWSER_COMPUTER.match(tool):
        return SCALE_MSG if _big_scale(params) else None
    if BROWSER_BATCH.match(tool):
        acts = params.get("actions") if isinstance(params.get("actions"), list) else []
        bad = any(isinstance(a, dict) and isinstance(a.get("input"), dict) and _big_scale(a["input"]) for a in acts)
        return SCALE_MSG if bad else None
    return None


def _scaled_shot(params: dict) -> dict:
    if params.get("action") != "screenshot":
        return params
    scale = params.get("scale")
    if isinstance(scale, (int, float)) and scale <= SCREENSHOT_SCALE:
        return params
    return {**params, "scale": SCREENSHOT_SCALE}


def _scaled_batch(params: dict) -> dict:
    actions = params.get("actions")
    if not isinstance(actions, list):
        return params
    scaled = [
        {**item, "input": _scaled_shot(item["input"])}
        if isinstance(item, dict) and item.get("name") == "computer" and isinstance(item.get("input"), dict)
        else item
        for item in actions
    ]
    return {**params, "actions": scaled}


def capped(tool: str, params: dict) -> dict | None:
    """Params with bounds filled in (Grep head_limit, screenshot scale), or None when already bounded."""
    if tool == "Grep":
        return None if params.get("head_limit") is not None else {**params, "head_limit": GREP_CAP}
    if BROWSER_COMPUTER.match(tool):
        bounded = _scaled_shot(params)
    elif BROWSER_BATCH.match(tool):
        bounded = _scaled_batch(params)
    else:
        return None
    return None if bounded == params else bounded


def _removed_rules(params: dict) -> list[str]:
    edits = params.get("edits")
    if "old_string" in params:
        pairs = [(str(params.get("old_string") or ""), str(params.get("new_string") or ""))]
    elif isinstance(edits, list):
        pairs = [(str(e.get("old_string") or ""), str(e.get("new_string") or "")) for e in edits if isinstance(e, dict)]
    else:
        try:
            before = Path(str(params.get("file_path") or "")).read_text("utf-8", "replace")
        except OSError:
            before = ""
        pairs = [(before, str(params.get("content") or ""))]
    return [
        line.strip()
        for old, new in pairs
        for line in old.splitlines()
        if line.strip() and line.strip() not in {n.strip() for n in new.splitlines()}
    ]


def _named(line: str, prompt: str) -> bool:
    words = set(RULE_WORD.findall(line.lower()))
    return len(words & set(RULE_WORD.findall(prompt.lower()))) >= min(2, len(words))


def _reply_before_prompt(recs: list[dict]) -> str:
    shown = latest = ""
    for rec in recs:
        if common.is_prompt(rec):
            shown = latest
        elif rec.get("type") == "assistant":
            latest = common.last_assistant_text([rec]) or latest
    return shown


def rule_deletion(tool: str, params: dict, recs: list[dict]) -> str | None:
    if tool not in ("Edit", "MultiEdit", "Write") or not str(params.get("file_path") or "").endswith("CLAUDE.md"):
        return None
    prompt = common.last_prompt(recs)
    if APPROVAL.match(prompt.strip()):
        prompt = f"{prompt}\n{_reply_before_prompt(recs)}"
    gone = [line for line in _removed_rules(params) if not _named(line, prompt)]
    if not gone:
        return None
    shown = "; ".join(line[:100] for line in gone[:5])
    return f"CLAUDE.md edit removes rule line(s) the user's last prompt does not name: {shown}. Show the user this diff first."


BOARD_FILE = re.compile(r"[/\\]design[/\\].*\.dc\.html$", re.IGNORECASE)
BOARD_MAX_DELETED = 200


def _lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def board_deletion_refusal(tool: str, params: dict) -> str | None:
    """A board edit that drops more than BOARD_MAX_DELETED lines (an emptied board was restored twice)."""
    path = str(params.get("file_path") or "")
    if tool not in common.EDIT_TOOLS or not BOARD_FILE.search(path):
        return None
    if tool == "Write":
        try:
            old = _lines(Path(path).read_text("utf-8", "replace"))
        except OSError:
            return None
        dropped = old - _lines(str(params.get("content") or ""))
    else:
        edits = params.get("edits") if isinstance(params.get("edits"), list) else [params]
        dropped = sum(_lines(str(e.get("old_string") or "")) - _lines(str(e.get("new_string") or "")) for e in edits if isinstance(e, dict))
    if dropped <= BOARD_MAX_DELETED:
        return None
    return f"Edit drops {dropped} lines from a design board (limit {BOARD_MAX_DELETED}): boards were emptied before. Allowed: edits that remove up to {BOARD_MAX_DELETED} lines each; split a bigger removal into several."


def line_only(tool: str, params: dict, prompt: str) -> str | None:
    if not GIVE_LINE.search(prompt) or tool not in SHELLS:
        return None
    return None if READ_ONLY_CMD.match(str(params.get("command") or "")) else LINE_ONLY


def repeat_edit_warning(state: dict, params: dict) -> str | None:
    old, new = str(params.get("old_string") or ""), str(params.get("new_string") or "")
    if not old or len(old) > REPEAT_EDIT_MAX_CHARS:
        return None
    key = json.dumps([old, new])
    files = state.setdefault("edit_files", {}).setdefault(key, [])
    path = str(params.get("file_path") or "")
    if path not in files:
        files.append(path)
    if len(files) != REPEAT_EDIT_FILES:
        return None
    return (
        f"Same edit already in {len(files) - 1} files (why you see this: hand-editing the same change is slow and error-prone). One pass over every file: "
        "(codemod, ruff --fix, eslint --fix, sed)."
    )


def churn_warning(state: dict, tool: str, params: dict) -> str | None:
    path = str(params.get("file_path") or "")
    counts = state.setdefault("edit_counts", {})
    if tool == "Write":
        counts.pop(path, None)
        return None
    counts[path] = counts.get(path, 0) + 1
    if counts[path] != EDIT_CHURN_LIMIT + 1:
        return None
    return (
        f"{Path(path).name}: {counts[path] - 1} Edits this session (why you see this: many small patches usually mean the plan was unclear). Plan the rest of the change, "
        "then make it in few larger Edits."
    )


def handback_refusal(tool: str, params: dict, event: dict | None = None) -> str | None:
    """A hand-back must be clean: every hedge line is either fixed or an explicit blocker."""
    if tool != "SubagentHandback":
        return None
    kind = (event or {}).get("agent_type")
    if kind in READ_ONLY_AGENTS:
        return None
    text = "\n".join(str(v) for v in params.values() if isinstance(v, str))
    worker = bool(kind) and kind not in SHIPPERS
    dirty = [
        ln.strip()[:80]
        for ln in text.splitlines()
        if HEDGE.search(ln) and not BLOCKED_LINE.search(ln) and not (worker and WORKER_OK_LINE.match(ln.strip()))
    ]
    if dirty:
        return HANDBACK_DIRTY.format(lines="; ".join(f"`{d}`" for d in dirty[:5]))
    if worker and NEEDS_DAT.search(text):
        return HANDBACK_WORKER_ASK
    if kind in SHIPPERS and not SHIP_LINE.search(text):
        return HANDBACK_NO_SHIP
    if LEFT_OPEN.search(text) and not LEFT_OK.search(text):
        return HANDBACK_LEFT
    return None


def file_asks(event: dict, params: dict) -> None:
    """A hand-back's `needs Dat: <q>` lands in the vault inbox; the agent makes no extra call."""
    text = "\n".join(str(v) for v in params.values() if isinstance(v, str))
    found = NEEDS_DAT.search(text)
    if not found:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import ask

    ask.file_ask(
        found.group(1), str(event.get("cwd") or ""), str(event.get("session_id") or ""),
        str(event.get("agent_id") or ""), str(event.get("agent_type") or ""),
    )


def gate_refusal(event: dict, tool: str, params: dict) -> str | None:
    """Subagents other than a shipper never run a whole test suite or build."""
    if tool not in SHELLS or not event.get("agent_id") or event.get("agent_type") in SHIPPERS:
        return None
    parts = re.split(r"&&|\|\||;|\n", str(params.get("command") or ""))
    full = [p for p in parts if SUITE.search(p.split("|")[0]) and not SUITE_TARGET.search(p.split("|")[0])]
    return FULL_GATE if full else None


def call_hint(event: dict, state: dict) -> str:
    """A subagent's CALL_HINTth tool call gets a nudge to hand back."""
    agent = str(event.get("agent_id") or "")
    if not agent:
        return ""
    counts = state.setdefault("agent_calls", {})
    counts[agent] = counts.get(agent, 0) + 1
    if counts[agent] != CALL_HINT:
        return ""
    return (
        f"{CALL_HINT} tool calls so far in this agent (why you see this: long runs re-read a growing context and cost a lot). "
        "Hand back now with `done N, left M` so the caller can split what's left."
    )


def workflow_refusal(tool: str, params: dict) -> str | None:
    """A Workflow script (inline or by scriptPath) never puts an agent() on Opus."""
    if tool != "Workflow":
        return None
    script = str(params.get("script") or "")
    path = Path(str(params.get("scriptPath") or ""))
    if not script and path.is_file():
        script = path.read_text("utf-8", "replace")
    return NO_WORKFLOW_OPUS if WORKFLOW_OPUS.search(script) else None


def agent_defaults(tool: str, params: dict) -> dict | None:
    """Fill what the lead keeps forgetting instead of refusing: general-purpose → worker, no model → sonnet (scout: haiku)."""
    if tool != "Agent" or params.get("subagent_type") == "fork":
        return None
    fixed = dict(params)
    if str(params.get("subagent_type") or "general-purpose") == "general-purpose":
        fixed["subagent_type"] = "worker"
    if not params.get("model"):
        fixed["model"] = "haiku" if fixed.get("subagent_type") == "scout" else "sonnet"
    return fixed if fixed != params else None


def agent_refusal(event: dict, tool: str, params: dict, state: dict) -> str | None:
    """Every Agent names a non-Opus model."""
    if tool != "Agent" or params.get("subagent_type") == "fork":
        return None
    kind = str(params.get("subagent_type") or "general-purpose")
    if kind == "coordinator":
        return NO_COORDINATOR
    if kind in BUILTIN_AGENTS:
        return NO_BUILTIN.format(kind=kind)
    model = str(params.get("model") or "")
    if not model:
        return NO_MODEL
    if "opus" in model:
        return NO_OPUS
    return None


def nested_agent(transcript: str, agent_id: str) -> bool:
    """True when the agent's meta file says another agent spawned it (an agent's worker)."""
    path = Path(transcript)
    meta = path.parent / path.stem / "subagents" / f"agent-{agent_id}.meta.json"
    try:
        return bool(json.loads(meta.read_text("utf-8")).get("parentAgentId"))
    except (OSError, ValueError):
        return False


def is_gate(tool: str, params: dict) -> bool:
    """A Bash call made only of lint/test steps (plus cd, head/tail): the check the stop hook asks for."""
    if tool != "Bash":
        return False
    segments = re.split(r"&&|\|\||;|\|", str(params.get("command") or "").replace("2>&1", ""))
    return any(GATE_SEGMENT.match(seg) and not seg.strip().startswith(("cd", "head", "tail")) for seg in segments) and all(
        GATE_SEGMENT.match(seg) for seg in segments
    )


def _counted(use: dict) -> bool:
    if use.get("name") in UNCOUNTED or is_gate(str(use.get("name") or ""), use.get("input") or {}):
        return False
    params = use.get("input") or {}
    path = str(params.get("file_path") or "")
    if use.get("name") == "Read" and PLAN_READ.search(path.replace("\\", "/")):
        return False
    return not (use.get("name") in common.EDIT_TOOLS and PLANS_PATH.search(path))


def lead_calls(event: dict, recs: list[dict]) -> int:
    """Counted calls this turn; calls batched in one assistant message count once."""
    current = str(event.get("tool_use_id") or "")
    batches: set[str] = set()
    for rec in common.turn_records(recs):
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
        for use in common.tool_uses([rec]):
            uid = str(use.get("id") or "")
            if not (current and uid == current) and _counted(use):
                batches.add(str(msg.get("id") or uid or id(use)))
    return len(batches)


def is_lead(event: dict, state: dict) -> bool:
    return not (event.get("agent_id") or common.is_sub_session(str(event.get("transcript_path") or ""), state))


def lead_image_refusal(event: dict, tool: str, params: dict, state: dict) -> str | None:
    if tool != "Read" or not is_lead(event, state):
        return None
    if Path(str(params.get("file_path") or "")).suffix.lower() not in LEAD_IMAGE_SUFFIXES:
        return None
    state["lead_images"] = state.get("lead_images", 0) + 1
    return LEAD_IMAGES_SPENT if state["lead_images"] > LEAD_IMAGE_CAP else None


def lead_refusal(event: dict, tool: str, params: dict, recs: list[dict], state: dict) -> str | None:
    """Main-session lead: 3 solo agents + 2 readers per request, no forks, ballpark briefs,
    at most 3 messages, never to others' workers."""
    if event.get("agent_id") or common.is_sub_session(str(event.get("transcript_path") or ""), state):
        return None
    if not TURN_FREE.match(tool) and not is_gate(tool, params) and lead_calls(event, recs) >= LEAD_CALL_CAP:
        return LEAD_TOO_LONG
    if tool not in ("Agent", "SendMessage"):
        return None
    if tool == "SendMessage":
        to = str(params.get("to") or "")
        nested = nested_agent(str(event.get("transcript_path") or ""), to)
        if nested:
            return LEAD_MESSENGER.format(to=to[:40])
        sent = [u for u in common.calls_since_prompt(recs, str(event.get("tool_use_id") or "")) if u.get("name") == "SendMessage"]
        return LEAD_MESSAGES_MAX if len(sent) >= LEAD_MESSAGES else None
    kind = str(params.get("subagent_type") or "general-purpose")
    if kind == "fork":
        return LEAD_FORK
    denied = common.denied_ids(recs)
    earlier = [
        str((u.get("input") or {}).get("subagent_type") or "general-purpose")
        for u in common.calls_since_prompt(recs, str(event.get("tool_use_id") or ""))
        if u.get("name") == "Agent" and str(u.get("id")) not in denied
    ]
    if kind in READ_ONLY_AGENTS:
        return LEAD_READERS_MAX if sum(k in READ_ONLY_AGENTS for k in earlier) >= LEAD_READERS else None
    solos = sum(k not in READ_ONLY_AGENTS for k in earlier)
    return LEAD_WORKER if solos >= LEAD_SOLOS else None


def slotted(tool: str, params: dict) -> dict | None:
    """Screenshots, browsers and dev servers run through slot.py: at most 3 at once across all agents."""
    cmd = str(params.get("command") or "")
    if tool != "Bash" or params.get("run_in_background") or not HEAVY.search(cmd) or SLOT in cmd:
        return None
    wrapped = f"( S=$({SLOT} acquire) || exit 1; trap '{SLOT} release \"$S\"' EXIT\n{cmd}\n)"
    return {**params, "command": wrapped}


def sub_quiet(tool: str, params: dict, transcript: str, state: dict, agent_id: str = "") -> dict | None:
    """Sub-sessions and agents report once, at the end: child agents run in the foreground, no messages to other sessions."""
    if tool == "Agent" and agent_id and params.get("run_in_background") is not False:
        return common.allow_with({**params, "run_in_background": False}, AGENT_FOREGROUND)
    if tool not in ("Agent", "SendMessage") or not common.is_sub_session(transcript, state):
        return None
    if tool == "SendMessage" and str(params.get("to") or "").startswith("local_"):
        return common.deny(SUB_NO_PING)
    if tool == "Agent" and params.get("run_in_background") is not False:
        return common.allow_with({**params, "run_in_background": False}, SUB_FOREGROUND)
    return None


T_KEYS = {**PATH_TOOLS, "Glob": "path", "Grep": "path"}
T_PREFIX = re.compile(r"^\$T(?=$|[/\\])")


def expand_t(event: dict, tool: str, params: dict) -> dict | None:
    """`$T/x` in a file tool's path becomes the session work dir, as Bash already has it."""
    key = T_KEYS.get(tool)
    raw = str(params.get(key) or "") if key else ""
    if not T_PREFIX.match(raw):
        return None
    work = work_dir.work_path(str(event.get("cwd") or ""), str(event.get("session_id") or ""), Path.home())
    return {**params, key: T_PREFIX.sub(work.as_posix(), raw)} if work else None


GIT_PUSH = re.compile(r"\bgit(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+push\b")
WORKER_PUSH = "Workers never push (why: every push runs paid CI). Leave the change for the shipper."
SECOND_PUSH = "This shipper already pushed once (why: every push runs paid CI). Commit locally; push once, at hand-back."


def push_refusal(event: dict, tool: str, params: dict, state: dict) -> str | None:
    """Pushes start CI minutes: workers never push, a shipper pushes once."""
    agent = str(event.get("agent_id") or "")
    if tool not in SHELLS or not agent or not GIT_PUSH.search(str(params.get("command") or "")):
        return None
    if event.get("agent_type") not in SHIPPERS:
        return WORKER_PUSH
    pushed = state.setdefault("pushes", {})
    if pushed.get(agent):
        return SECOND_PUSH
    pushed[agent] = 1
    return None


def decide(event: dict, state: dict) -> dict | None:
    tool = str(event.get("tool_name") or "")
    params = event.get("tool_input") or {}
    if not isinstance(params, dict):
        return None
    expanded = expand_t(event, tool, params)
    if expanded:
        # The harness ignores updatedInput for file tools (Write made a literal `$T` dir), so refuse with the real path.
        return common.deny(f"$T is expanded only in Bash. Use the real path: {expanded[T_KEYS[tool]]}")
    if START_SESSION.match(tool) and isinstance(params.get("prompt"), str) and common.SUB_MARKER not in params["prompt"]:
        return common.allow_with({**params, "prompt": f"{common.SUB_RULES}\n\n{params['prompt']}"})
    defaulted = agent_defaults(tool, params)
    params = defaulted or params
    bad_agent = agent_refusal(event, tool, params, state) or workflow_refusal(tool, params)
    if bad_agent:
        return common.deny(bad_agent)
    quiet = sub_quiet(tool, params, str(event.get("transcript_path") or ""), state, str(event.get("agent_id") or ""))
    if quiet:
        return quiet
    recs = common.records(str(event.get("transcript_path") or ""))
    hint = call_hint(event, state)
    prompts = sum(1 for r in recs if common.is_prompt(r))
    reason = (
        handback_refusal(tool, params, event)
        or gate_refusal(event, tool, params)
        or push_refusal(event, tool, params, state)
        or lead_refusal(event, tool, params, recs, state)
        or path_refusal(event, tool, params)
        or repeat_refusal(state, tool, params)
        or read_streak_refusal(state, tool, params, prompts, str(event.get("agent_type") or ""))
        or scale_refusal(tool, params)
        or board_deletion_refusal(tool, params)
        or (search_refusal(tool, params) if tool in ("Glob", "Grep") else None)
        or (shell_refusal(params) if tool in SHELLS else None)
    )
    updated: dict | None = defaulted
    notes: list[str] = [hint]
    if is_lead(event, state) and not TURN_FREE.match(tool) and lead_calls(event, recs) == LEAD_WARN_AT - 1:
        notes.append(LEAD_NEAR_CAP)
    if not reason and tool == "Read":
        reason = lead_image_refusal(event, tool, params, state)
    if not reason and tool == "Read":
        reader = str(event.get("transcript_path") or "")
        note = ""
        reason = image_refusal(params, state, f"{reader}|{event.get('agent_id') or ''}")
        reason = reason or repeats_hint.read_repeat(state, params, str(event.get("agent_id") or "main"))
        if not reason:
            reason, budgeted, note = read_budget(params, state, reader)
            updated = budgeted or updated
        notes.append(note)
    if reason:
        return common.deny(reason)
    if tool == "SubagentHandback":
        file_asks(event, params)
    bounded = capped(tool, updated or params)
    updated = bounded or updated
    updated = slotted(tool, updated or params) or updated
    if tool in common.EDIT_TOOLS:
        notes += [rule_deletion(tool, params, recs), churn_warning(state, tool, params)]
        if tool == "Edit":
            notes.append(repeat_edit_warning(state, params))
    notes.append(line_only(tool, params, common.last_prompt(recs)))
    note = " ".join(n for n in notes if n)
    if updated:
        return common.allow_with(updated, note)
    return common.advise("PreToolUse", note) if note else None


def main() -> None:
    event = common.read_events()
    session = str(event.get("session_id") or "")
    state = common.load_state(session)
    output = decide(event, state)
    common.save_state(session, state)
    common.emit(output)


if __name__ == "__main__":
    main()
