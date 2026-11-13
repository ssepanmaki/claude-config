#!/usr/bin/env python3
"""Aggregate Claude Code transcripts under ~/.claude/projects into JSON on stdout. Usage: collect.py [days]"""

import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 90
NOW = dt.datetime.now(dt.UTC)
CUT = (NOW - dt.timedelta(days=DAYS)).strftime("%Y-%m-%d")
ROOT = os.path.expanduser("~/.claude/projects")


def proj(cwd):
    p = (cwd or "").replace("\\", "/").rstrip("/")
    m = re.match(r"(?i)^[a-z]:/Users/[^/]+/?(.*)$", p) or re.match(r"^/home/[^/]+/?(.*)$", p)
    if not m:
        return "other"
    parts = m.group(1).split("/")
    if not parts[0]:
        return "~ (home)"
    if parts[0] in ("AppData", ".claude"):
        return "scratch/tmp"
    if parts[0] == "work":
        parts = parts[1:] or ["work"]
    return parts[0]


def new_row():
    return {"msgs": 0, "inp": 0, "out": 0, "cr": 0, "cc": 0, "tools": {}}


def scan_file(f, sessions, rows, seen):
    sid = os.path.basename(f)[:-6]
    s = sessions.setdefault(sid, {"id": sid, "project": None, "first": None, "last": None, "prompts": 0, "msgs": 0, "agent": False})
    if "/subagents/" in f.replace("\\", "/"):
        s["agent"] = True
    with open(f, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            scan_line(o, s, rows, seen)


def scan_line(o, s, rows, seen):
    ts = o.get("timestamp")
    if not ts:
        return
    if not s["project"] and o.get("cwd"):
        s["project"] = proj(o["cwd"])
    s["first"] = min(s["first"] or ts, ts)
    s["last"] = max(s["last"] or ts, ts)
    t = o.get("type")
    if t == "user" and not o.get("isSidechain") and not o.get("isMeta") and isinstance((o.get("message") or {}).get("content"), str):
        s["prompts"] += 1
    if t != "assistant":
        return
    msg = o.get("message") or {}
    u = msg.get("usage")
    key = (msg.get("id"), o.get("requestId"))
    mdl = msg.get("model") or "?"
    if not u or key in seen or ts[:10] < CUT or mdl.startswith("<"):
        return
    seen.add(key)
    r = rows.setdefault((ts[:10], s["project"] or "?", mdl), new_row())
    r["msgs"] += 1
    s["msgs"] += 1
    r["inp"] += u.get("input_tokens", 0)
    r["out"] += u.get("output_tokens", 0)
    r["cr"] += u.get("cache_read_input_tokens", 0)
    r["cc"] += u.get("cache_creation_input_tokens", 0)
    for c in msg.get("content") or []:
        if isinstance(c, dict) and c.get("type") == "tool_use":
            n = c.get("name", "?")
            n = "mcp" if n.startswith("mcp__") else n
            r["tools"][n] = r["tools"].get(n, 0) + 1


def git_commits():
    home = os.path.expanduser("~")
    commits = []
    for g in glob.glob(home + "/*/.git") + glob.glob(home + "/work/*/.git"):
        repo = os.path.dirname(g)
        cmd = ["git", "-C", repo, "log", "--all", f"--since={DAYS} days ago", "--date=short", "--pretty=%ad|%an|%s"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False).stdout or ""
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"git failed in {repo}: {exc}", file=sys.stderr)
            continue
        for ln in out.splitlines():
            a = ln.split("|", 2)
            if len(a) == 3:
                commits.append({"repo": os.path.basename(repo), "date": a[0], "author": a[1], "subject": a[2][:80]})
    return commits


def main():
    rows, sessions, seen = {}, {}, set()
    horizon = NOW.timestamp() - DAYS * 86400
    for f in glob.glob(ROOT + "/**/*.jsonl", recursive=True):
        try:
            if os.path.getmtime(f) >= horizon:
                scan_file(f, sessions, rows, seen)
        except OSError as exc:
            print(f"skip {f}: {exc}", file=sys.stderr)
    out = {
        "rows": [{"date": k[0], "project": k[1], "model": k[2], **v} for k, v in rows.items()],
        "sessions": [s for s in sessions.values() if s["first"] and s["last"][:10] >= CUT],
        "commits": git_commits(),
    }
    print(json.dumps(out))


main()
