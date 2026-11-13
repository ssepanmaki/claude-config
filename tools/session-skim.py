#!/usr/bin/env python3
"""session-skim: skim Claude Code session transcripts into to-dos, progress and recaps.

Usage:
  session-skim.py [TARGET ...] [--recent N] [--project TEXT] [--since HOURS]
                  [--board] [--json] [--full] [--no-redact]

TARGET is a .jsonl path, a session-id prefix, or omitted (= most recent session).
  --recent N    skim the N most recently active sessions
  --project T   only sessions whose project dir or cwd contains T
  --since H     only sessions active in the last H hours
  --board       one line per session (status board) instead of a full skim
  --json        machine-readable output
  --full        no truncation of lists
  --hosts A,B   merge sessions from these ssh hosts (default: $SKIM_HOSTS or tools/skim-hosts.txt)
  --local-only  skip remote hosts
  --out FILE    also write the result to FILE (shared board.md)
Reads ~/.claude/projects/*/*.jsonl (or $CLAUDE_CONFIG_DIR/projects). Stdlib only.
"""
import argparse
import contextlib
import glob
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

with contextlib.suppress(AttributeError, ValueError):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects")

SECRET_RES = [
    re.compile(r"\b(ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
]
NOISE_RES = [
    re.compile(r"<system-reminder[^>]*>.*?</system-reminder>", re.DOTALL),
    re.compile(r"<(command-message|command-name|command-args|local-command-stdout|local-command-caveat)>.*?</\1>", re.DOTALL),
]
NOISE_ASK_RE = re.compile(
    r"^(<(system-reminder|task-notification|relay|wake|fork-source|command-)|Tool loaded\.?$|This session is being continued|\[Request interrupted|Caveat:)")
PR_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(?:pull|issues)/\d+")
DONE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

REDACT = True
HOSTNAME = (os.environ.get("SKIM_NAME") or platform.node().split(".")[0] or "local").lower()
HOSTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skim-hosts.txt")
# Brief boilerplate that hides the real task in titles.
TITLE_PREFIX_RE = re.compile(
    r"^(?:\s*(?:Background \(from the session that started this one\):?|Repo \S+(?: \([^)]*\))?[.:]?|Branch \S+[.:]?|Other[^.]*\.|Read CLAUDE\.md first\.?)\s*)+",
)


def clean(s, n=None):
    if not isinstance(s, str):
        return ""
    for r in NOISE_RES:
        s = r.sub("", s)
    if REDACT:
        for r in SECRET_RES:
            s = r.sub("[redacted]", s)
    s = re.sub(r"\s+", " ", s).strip()
    if n and len(s) > n:
        s = s[: n - 1].rstrip() + "…"
    return s


def parse_ts(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def load_line(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def ago(dt):
    if not dt:
        return "?"
    d = (datetime.now(UTC) - dt).total_seconds()
    for unit, sec in (("d", 86400), ("h", 3600), ("m", 60)):
        if d >= sec:
            return f"{int(d // sec)}{unit} ago"
    return "just now"


class Plan:
    def __init__(self):
        self.items = []

    def set(self, items):
        self.items = [{"content": i.get("content", ""), "status": i.get("status", "pending")} for i in items if isinstance(i, dict)]

    def update_plan(self, inp):
        if isinstance(inp.get("items"), list):
            self.set(inp["items"])
        if inp.get("advance"):
            self._advance()
        for n in inp.get("done") or []:
            self._mark(n, "completed")
        if inp.get("start"):
            for i in self.items:
                if i["status"] == "in_progress":
                    i["status"] = "pending"
            self._mark(inp["start"], "in_progress")

    def _mark(self, n, st):
        if isinstance(n, int) and 1 <= n <= len(self.items):
            self.items[n - 1]["status"] = st

    def _advance(self):
        for i in self.items:
            if i["status"] == "in_progress":
                i["status"] = "completed"
                break
        for i in self.items:
            if i["status"] == "pending":
                i["status"] = "in_progress"
                break

    def close(self):
        for i in self.items:
            if i["status"] == "in_progress":
                i["status"] = "completed"

    def progress(self):
        done = sum(1 for i in self.items if i["status"] == "completed")
        return done, len(self.items)


def skim(path):
    s = {
        "path": path, "session": os.path.splitext(os.path.basename(path))[0],
        "project": os.path.basename(os.path.dirname(path)), "cwd": None, "branch": None,
        "start": None, "end": None, "title": None, "asks": [], "recaps": [], "open_question": None,
        "files": Counter(), "commands": [], "errors": [], "links": OrderedDict(),
        "agents": [], "sessions_started": [], "compactions": 0, "last_text": None,
        "tool_count": 0, "turns": 0,
    }
    plan = Plan()
    pending_ids = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        s["errors"].append(f"cannot open: {e}")
        return s, plan
    for line in lines:
            ev = load_line(line)
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "summary" and ev.get("summary") and not s["title"]:
                s["title"] = clean(ev["summary"], 100)
            if ev.get("isSidechain"):
                continue
            ts = parse_ts(ev.get("timestamp") or "")
            if ts:
                s["start"] = s["start"] or ts
                s["end"] = ts
            s["cwd"] = ev.get("cwd") or s["cwd"]
            s["branch"] = ev.get("gitBranch") or s["branch"]
            msg = ev.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            role = msg.get("role")
            if role == "user":
                if ev.get("isCompactSummary"):
                    s["compactions"] += 1
                    continue
                if ev.get("isMeta"):
                    continue
                texts = []
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text":
                            texts.append(b.get("text", ""))
                        elif b.get("type") == "tool_result" and b.get("is_error"):
                            c = b.get("content")
                            if isinstance(c, list):
                                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                            tool = pending_ids.get(b.get("tool_use_id"), "?")
                            s["errors"].append(f"{tool}: {clean(c, 160)}")
                full = " ".join(texts)
                t = clean(full, 200)
                if t and not NOISE_ASK_RE.match(t):
                    s["asks"].append(((ts.isoformat() if ts else None), t))
                    s["turns"] += 1
                    if not s["title"]:
                        s["title"] = clean(TITLE_PREFIX_RE.sub("", clean(full, 800)), 100) or clean(t, 100)
                for m in PR_RE.findall(" ".join(texts)):
                    s["links"][m] = 1
            elif role == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        s["last_text"] = b["text"]
                        for m in PR_RE.findall(b["text"]):
                            s["links"][m] = 1
                    elif b.get("type") == "tool_use":
                        s["tool_count"] += 1
                        name, inp = b.get("name", ""), b.get("input") or {}
                        pending_ids[b.get("id")] = name.split("__")[-1]
                        short = name.split("__")[-1]
                        if short == "update_plan":
                            plan.update_plan(inp)
                        elif name == "TodoWrite" and isinstance(inp.get("todos"), list):
                            plan.set(inp["todos"])
                        elif short == "wrap_up":
                            plan.close()
                            if inp.get("recap"):
                                s["recaps"].append(((ts.isoformat() if ts else None), clean(inp["recap"], 400)))
                            s["open_question"] = clean(inp.get("ask"), 160) or None
                        elif name in DONE_TOOLS:
                            p = inp.get("file_path") or inp.get("notebook_path")
                            if p:
                                s["files"][p.replace("\\", "/")] += 1
                        elif name == "Bash" and inp.get("command"):
                            s["commands"].append(clean(inp["command"].splitlines()[0], 140))
                        elif name in ("Agent", "Task"):
                            s["agents"].append(clean(inp.get("description") or inp.get("prompt"), 80))
                        elif short in ("start_session", "hand_off_to_session"):
                            s["sessions_started"].append(clean(inp.get("title") or inp.get("prompt"), 80))
                        blob = json.dumps(inp)[:4000]
                        for m in PR_RE.findall(blob):
                            s["links"][m] = 1
    if s["recaps"] and s["open_question"] is None:
        pass
    return s, plan


def status_of(s, plan):
    done, total = plan.progress()
    if s["open_question"]:
        return "waiting on user"
    if total and done < total:
        return "in progress"
    if s["end"] and (datetime.now(UTC) - s["end"]).total_seconds() < 600:
        return "active"
    return "idle"


def to_json(s, plan):
    d = dict(s)
    d["files"] = dict(s["files"])
    d["links"] = list(s["links"])
    d["start"] = s["start"].isoformat() if s["start"] else None
    d["end"] = s["end"].isoformat() if s["end"] else None
    d["plan"] = plan.items
    d["progress"] = plan.progress()
    d["status"] = status_of(s, plan)
    d["last_text"] = clean(s["last_text"], 600)
    return d


def cap(lst, n, full):
    return lst if full else lst[-n:]


def render(s, plan, full=False):
    mark = {"completed": "[x]", "in_progress": "[>]", "pending": "[ ]"}
    done, total = plan.progress()
    out = [f"## {s['title'] or s['session']}"]
    out.append(f"- session `{s['session'][:8]}` · {s['project']} · branch `{s['branch'] or '-'}`")
    out.append(f"- active {ago(s['end'])} · {s['turns']} user turns · {s['tool_count']} tool calls"
               + (f" · {s['compactions']} compactions" if s["compactions"] else ""))
    out.append(f"- status: **{status_of(s, plan)}**" + (f" · plan {done}/{total}" if total else ""))
    if s["open_question"]:
        out.append(f"- open question: {s['open_question']}")
    if plan.items:
        out.append("\n### To-do / progress")
        out += [f"- {mark.get(i['status'], '[ ]')} {clean(i['content'], 120)}" for i in plan.items]
    if s["recaps"]:
        out.append("\n### Recaps (latest last)")
        out += [f"- {r}" for _, r in cap(s["recaps"], 4, full)]
    if s["asks"]:
        out.append("\n### User asks")
        out += [f"- {a}" for _, a in cap(s["asks"], 8, full)]
    if s["files"]:
        out.append("\n### Files changed")
        items = s["files"].most_common(None if full else 15)
        out += [f"- {p} ({n}x)" for p, n in items]
    if s["links"]:
        out.append("\n### PRs / issues")
        out += [f"- {u}" for u in s["links"]]
    if s["agents"] or s["sessions_started"]:
        out.append("\n### Delegated")
        out += [f"- agent: {a}" for a in cap(s["agents"], 8, full)]
        out += [f"- session: {a}" for a in cap(s["sessions_started"], 8, full)]
    if s["commands"]:
        out.append("\n### Recent commands")
        out += [f"- `{c}`" for c in cap(s["commands"], 8, full)]
    if s["errors"]:
        out.append(f"\n### Errors ({len(s['errors'])})")
        out += [f"- {e}" for e in cap(s["errors"], 5, full)]
    if s["last_text"]:
        out.append("\n### Last reply")
        out.append(clean(s["last_text"], None if full else 500))
    return "\n".join(out) + "\n"


def board_line(s, plan):
    done, total = plan.progress()
    cur = next((i["content"] for i in plan.items if i["status"] == "in_progress"), "")
    last = s["recaps"][-1][1] if s["recaps"] else (s["asks"][-1][1] if s["asks"] else clean(s["last_text"], 90))
    title = s["title"] or clean(s["last_text"], 50) or "(untitled)"
    prog = f"{done}/{total}" if total else "-"
    return (f"| {s.get('host', HOSTNAME)} | {s['session'][:8]} | {clean(title, 50)} | {s['branch'] or '-'} | {status_of(s, plan)} "
            f"| {prog} | {clean(cur, 40)} | {ago(s['end'])} | {clean(last, 90)} |")


def from_json(d, host):
    """Rebuild (s, plan) from another host's --json output."""
    s = dict(d)
    s["host"] = host
    s["files"] = Counter(d.get("files") or {})
    s["links"] = OrderedDict((u, 1) for u in d.get("links") or [])
    s["start"] = parse_ts(d.get("start"))
    s["end"] = parse_ts(d.get("end"))
    for k in ("asks", "recaps", "commands", "errors", "agents", "sessions_started"):
        s[k] = d.get(k) or []
    for k in ("turns", "tool_count", "compactions"):
        s[k] = d.get(k) or 0
    plan = Plan()
    plan.set(d.get("plan") or [])
    return s, plan


def dedupe(results):
    """The desktop app mirrors SSH-session transcripts locally, so one session can
    appear on two hosts. Keep one row per session id: the copy with the latest
    activity, credited to the host whose path style matches the session's cwd."""
    best = {}
    for s, pl in results:
        sid = s["session"]
        cur = best.get(sid)
        if cur is None or (s["end"] or datetime.min.replace(tzinfo=UTC)) > (cur[0]["end"] or datetime.min.replace(tzinfo=UTC)):
            best[sid] = (s, pl)
    hosts_by_sid = {}
    for s, _ in results:
        hosts_by_sid.setdefault(s["session"], set()).add(s.get("host"))
    for sid, (s, _) in best.items():
        hs = hosts_by_sid[sid]
        if len(hs) > 1:
            cwd = s.get("cwd") or ""
            linux = cwd.startswith("/")
            remote = sorted(h for h in hs if h != HOSTNAME)
            s["host"] = (remote[0] if remote else s["host"]) if linux else HOSTNAME
    out = list(best.values())
    out.sort(key=lambda r: r[0]["end"] or datetime.min.replace(tzinfo=UTC), reverse=True)
    return out


def load_hosts(arg):
    if arg is not None:
        return [h for h in arg.split(",") if h.strip()]
    if os.environ.get("SKIM_HOSTS"):
        return [h for h in os.environ["SKIM_HOSTS"].split(",") if h.strip()]
    if os.path.isfile(HOSTS_FILE):
        with open(HOSTS_FILE, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return []


def fetch_remote(host, passthrough):
    """Run session-skim --json on HOST over ssh. Returns (results, error)."""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host,
           "python3 ~/.claude/tools/session-skim.py --json " + " ".join(shlex.quote(x) for x in passthrough)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"{host}: {e}"
    if r.returncode != 0:
        return [], f"{host}: exit {r.returncode} {clean(r.stderr, 160)}"
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return [], f"{host}: bad JSON"
    return [from_json(d, host) for d in data], None


def find_sessions(targets, recent, project, since):
    allf = [p for p in glob.glob(os.path.join(ROOT, "*", "*.jsonl")) if not os.path.basename(p).startswith("agent-")]
    if project:
        allf = [p for p in allf if project.lower() in p.lower()]
    allf.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    if since:
        cut = time.time() - since * 3600
        allf = [p for p in allf if os.path.getmtime(p) >= cut]
    if targets:
        out = []
        for t in targets:
            if os.path.isfile(t):
                out.append(t)
                continue
            m = [p for p in allf if os.path.basename(p).startswith(t)]
            if not m:
                print(f"no session matches {t!r}", file=sys.stderr)
            out += m[:1]
        return out
    return allf[: recent or 1] if not since or recent else allf


def main():
    global REDACT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--recent", type=int)
    ap.add_argument("--project")
    ap.add_argument("--since", type=float)
    ap.add_argument("--board", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--no-redact", action="store_true")
    ap.add_argument("--hosts", help="comma list of ssh hosts to merge in (default: $SKIM_HOSTS or tools/skim-hosts.txt)")
    ap.add_argument("--local-only", action="store_true", help="ignore --hosts / skim-hosts.txt")
    ap.add_argument("--out", help="also write the output to this file (e.g. a shared board.md)")
    a = ap.parse_args()
    REDACT = not a.no_redact
    paths = find_sessions(a.targets, a.recent, a.project, a.since)
    results = [skim(p) for p in paths]
    for s, _ in results:
        s["host"] = HOSTNAME
    warnings = []
    hosts = [] if (a.local_only or a.json) else load_hosts(a.hosts)
    if hosts:
        passthrough = list(a.targets)
        for flag, val in (("--recent", a.recent), ("--project", a.project), ("--since", a.since)):
            if val is not None:
                passthrough += [flag, str(val)]
        if a.no_redact:
            passthrough.append("--no-redact")
        with ThreadPoolExecutor(max_workers=8) as ex:
            for got, err in ex.map(lambda h: fetch_remote(h, passthrough), hosts):
                results += got
                if err:
                    warnings.append(err)
        results = dedupe(results)
        if a.recent and not a.targets:
            results = results[: a.recent]
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    if not results:
        print("no sessions found under " + ROOT, file=sys.stderr)
        return 1
    if a.json:
        text = json.dumps([to_json(s, pl) for s, pl in results], indent=2, ensure_ascii=False, default=str)
    elif a.board:
        rows = ["| host | id | title | branch | status | plan | current step | active | last recap / ask |",
                "|---|---|---|---|---|---|---|---|---|"]
        rows += [board_line(s, pl) for s, pl in results]
        text = "\n".join(rows)
    else:
        text = "\n---\n".join(f"<!-- host: {s.get('host')} -->\n" + render(s, pl, a.full) for s, pl in results)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(f"<!-- session-skim {datetime.now(UTC).isoformat(timespec='seconds')} -->\n{text}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
