#!/usr/bin/env python3
"""Fold local.json and vm.json (collect.py output) into small dataset files. Usage: build_data.py <in_dir> <out_dir>"""

import json
import os
import sys
from collections import Counter, defaultdict

PRICE = {"opus": (15, 75, 1.5, 18.75), "sonnet": (3, 15, 0.3, 3.75), "haiku": (1, 5, 0.1, 1.25)}


def family(model):
    return next((k for k in PRICE if k in model), "sonnet")


def cost(r):
    pi, po, pr, pc = PRICE[family(r["model"])]
    return (r["inp"] * pi + r["out"] * po + r["cr"] * pr + r["cc"] * pc) / 1e6


def load(in_dir):
    out = {}
    for src, name in (("claude-box", "vm.json"),):
        with open(os.path.join(in_dir, name), encoding="utf-8") as fh:
            out[src] = json.load(fh)
    return out


def main(in_dir, out_dir):
    data = load(in_dir)
    daily = defaultdict(lambda: {"msgs": 0, "out_tokens": 0, "cost": 0.0})
    proj = defaultdict(lambda: {"msgs": 0, "out_tokens": 0, "cost": 0.0, "sessions": 0, "prompts": 0})
    models, tools = defaultdict(lambda: {"msgs": 0, "cost": 0.0}), Counter()
    sess_day = defaultdict(set)
    for src, d in data.items():
        for r in d["rows"]:
            c = cost(r)
            for tgt in (daily[(r["date"], src)], proj[(r["project"], src)]):
                tgt["msgs"] += r["msgs"]
                tgt["out_tokens"] += r["out"]
                tgt["cost"] += c
            m = models[r["model"]]
            m["msgs"] += r["msgs"]
            m["cost"] += c
            tools.update(r["tools"])
        for s in d["sessions"]:
            if s["msgs"] and not s["agent"]:
                sess_day[(s["first"][:10], src)].add(s["id"])
                p = proj[(s["project"] or "?", src)]
                p["sessions"] += 1
                p["prompts"] += s["prompts"]
    commits = Counter((c["date"], c["repo"]) for d in data.values() for c in d["commits"])
    daily_rows = [
        {"date": k[0], "source": k[1], "sessions": len(sess_day.get(k, ())), **{a: round(b, 2) for a, b in v.items()}}
        for k, v in sorted(daily.items())
    ]
    tot = lambda key: round(sum(r[key] for r in daily_rows), 2)
    summary = [{
        "sessions": tot("sessions"), "msgs": tot("msgs"), "out_tokens": tot("out_tokens"), "cost": tot("cost"),
        "commits": sum(commits.values()), "days_active": len({r["date"] for r in daily_rows}),
        "from": daily_rows[0]["date"], "to": daily_rows[-1]["date"],
        "box_cost": round(sum(r["cost"] for r in daily_rows if r["source"] == "claude-box"), 2),
    }]
    files = {
        "daily": daily_rows,
        "projects": [{"project": k[0], "source": k[1], **{a: round(b, 2) for a, b in v.items()}} for k, v in proj.items() if v["msgs"]],
        "models": [{"model": k, "msgs": v["msgs"], "cost": round(v["cost"], 2)} for k, v in models.items()],
        "tools": [{"tool": k, "uses": v} for k, v in tools.most_common(15)],
        "commits": [{"date": k[0], "repo": k[1], "commits": v} for k, v in sorted(commits.items())],
        "summary": summary,
    }
    os.makedirs(out_dir, exist_ok=True)
    for name, rows in files.items():
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh)
        print(name, len(rows), os.path.getsize(os.path.join(out_dir, name + ".json")))


main(sys.argv[1], sys.argv[2])
