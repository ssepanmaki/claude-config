"""Pre-aggregated usage cube. Parses each transcript once into usage.db (re-parses only changed files), then queries by dimension.

usage: python -I rollup.py [days=30] [by=project[,day,model,role,session]] [project-substring]
dims: day, project, model, role (lead/sub), session. Cost is computed at query time from stored tokens (PRICES below).
"""

import glob
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.expanduser("~/.claude/projects")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.db")
PRICES = {"opus": (4.0, 0.20, 20.0), "sonnet": (2.0, 0.10, 10.0), "haiku": (0.10, 0.01, 0.50)}  # $/M: in, cache read, out


def fam(m):
    return next((k for k in PRICES if k in (m or "")), "other")


def parse(f):
    side = os.sep + "subagents" + os.sep in f
    parts = f.split(os.sep)
    pj = re.sub(r"^C--Users-OMISTAJA-?", "", parts[-4] if side else parts[-2]) or "home"
    sid = parts[-3] if side else os.path.basename(f)[:8]
    agg, seen = {}, set()
    with open(f, encoding="utf8", errors="ignore") as fh:
        for line in fh:
            if '"type":"assistant"' not in line:
                continue
            try:
                j = json.loads(line)
            except ValueError:
                continue
            m = j.get("message") or {}
            u = m.get("usage")
            if not u:
                continue
            mid = (m.get("id") or "") + (j.get("requestId") or "")
            if mid in seen:
                continue
            seen.add(mid)
            k = ((j.get("timestamp") or "")[:10], fam(m.get("model")))
            a = agg.setdefault(k, [0, 0, 0, 0, 0])
            a[0] += 1
            a[1] += u.get("input_tokens", 0)
            a[2] += u.get("cache_creation_input_tokens", 0)
            a[3] += u.get("cache_read_input_tokens", 0)
            a[4] += u.get("output_tokens", 0)
    role = "sub" if side else "lead"
    return [(f, d, pj, sid, role, mo, *v) for (d, mo), v in agg.items()]


def refresh(db):
    db.execute("create table if not exists files(path primary key, mtime, size)")
    db.execute(
        "create table if not exists fact(path, day, project, session, role, model, calls, inp, cw, cr, out)"
    )
    db.execute("create index if not exists fx on fact(path)")
    known = {p: (m, s) for p, m, s in db.execute("select path, mtime, size from files")}
    n = 0
    for f in glob.glob(f"{ROOT}/*/**/*.jsonl", recursive=True):
        st = os.stat(f)
        if known.get(f) == (st.st_mtime, st.st_size):
            continue
        db.execute("delete from fact where path=?", (f,))
        db.executemany("insert into fact values(?,?,?,?,?,?,?,?,?,?,?)", parse(f))
        db.execute("insert or replace into files values(?,?,?)", (f, st.st_mtime, st.st_size))
        n += 1
    db.commit()
    return n


def main():
    days = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    dims = (sys.argv[2] if len(sys.argv) > 2 else "project").split(",")
    sub = sys.argv[3] if len(sys.argv) > 3 else ""
    db = sqlite3.connect(DB)
    t = time.time()
    n = refresh(db)
    print(f"# refreshed {n} files in {time.time() - t:.0f}s")
    cut = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
    rows = db.execute(
        f"select {','.join(dims)}, model, sum(calls), sum(inp), sum(cw), sum(cr), sum(out) "
        f"from fact where day>=? and project like ? group by {','.join(dims)}, model",
        (cut, f"%{sub}%"),
    ).fetchall()
    tot, cost = {}, 0.0
    nd = len(dims)
    for r in rows:
        key, mo, c, i, cw, cr, o = r[:nd], r[nd], *r[nd + 1 :]
        pi, pc, po = PRICES.get(mo, PRICES["sonnet"])
        usd = (i * pi + cw * pi * 1.25 + cr * pc + o * po) / 1e6
        e = tot.setdefault(key, [0, 0.0])
        e[0] += c
        e[1] += usd
        cost += usd
    print(f"== {days:g}d by {','.join(dims)}  total ${cost:,.0f}")
    for key, (c, usd) in sorted(tot.items(), key=lambda x: -x[1][1]):
        if usd >= 0.5:
            print(f"  ${usd:7.0f} {c:7} calls  {' | '.join(map(str, key))}")


main()
