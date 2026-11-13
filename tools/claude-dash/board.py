#!/usr/bin/env python3
"""Emit one card per main session under ~/.claude/projects as JSON on stdout (run on the box)."""

import datetime as dt
import glob
import json
import os
import re

RUNNING_MINUTES = 10
NOISE = re.compile(r"<system-reminder>.*?</system-reminder>|<command-[a-z]+>.*?</command-[a-z]+>|<bash-[a-z]+>.*?</bash-[a-z]+>|<pasted_content[^>]*>", re.DOTALL)


def clean(text, limit):
    return re.sub(r"\s+", " ", NOISE.sub(" ", text)).strip()[:limit]


def read_session(path):
    card = {"id": os.path.basename(path)[:-6], "project": os.path.basename(os.path.dirname(path)).split("-work-")[-1], "branch": "", "goal": "", "last": "", "started": None, "active": None, "prompts": 0}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            ts = o.get("timestamp")
            if not ts:
                continue
            card["started"] = card["started"] or ts
            card["active"] = ts
            card["branch"] = o.get("gitBranch") or card["branch"]
            msg = o.get("message") or {}
            if o.get("type") == "user" and not o.get("isMeta") and isinstance(msg.get("content"), str):
                text = clean(msg["content"], 220)
                if text:
                    card["prompts"] += 1
                    card["goal"] = card["goal"] or text
            if o.get("type") == "assistant":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text" and block["text"].strip():
                        card["last"] = clean(block["text"], 260)
    return card


def main():
    now = dt.datetime.now(dt.UTC)
    cards = []
    for path in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        card = read_session(path)
        if not card["started"]:
            continue
        idle = (now - dt.datetime.fromisoformat(card["active"])).total_seconds() / 60
        card["state"] = "running" if idle < RUNNING_MINUTES else "idle"
        card["idle_minutes"] = round(idle)
        cards.append(card)
    cards.sort(key=lambda c: c["active"], reverse=True)
    print(json.dumps(cards))


main()
