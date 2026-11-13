"""Bash shapes ranked by count x output chars, plus calls >5 min: `python -I bash_shapes.py [days=3] [top=25]`."""
import collections as C
import glob
import json
import os
import re
import sys
import time
from datetime import datetime

days = float(sys.argv[1]) if len(sys.argv) > 1 else 3
top = int(sys.argv[2]) if len(sys.argv) > 2 else 25
since = time.time() - days * 86400
root = os.path.expanduser('~/.claude/projects')


def norm(c):
    c = re.sub(r'"[^"]*"|\'[^\']*\'', 'S', c)
    c = re.sub(r'(?:[A-Za-z]:)?[/\\~][^\s|;&]*', 'P', c)
    c = re.sub(r'\d+', 'N', c)
    return re.sub(r'\s+', ' ', c).strip()[:140]


def ts(r):
    try:
        return datetime.fromisoformat(r['timestamp']).timestamp()
    except (KeyError, ValueError, TypeError):
        return 0


n, out, dur, ex, sess = C.Counter(), C.Counter(), C.Counter(), {}, C.defaultdict(set)
slow = []
for f in glob.glob(f'{root}/*/**/*.jsonl', recursive=True):
    if os.path.getmtime(f) < since:
        continue
    pend = {}
    for line in open(f, encoding='utf8', errors='ignore').read().splitlines():  # noqa: SIM115
        if 'tool_' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        c = (r.get('message') or {}).get('content')
        for p in c if isinstance(c, list) else []:
            if not isinstance(p, dict):
                continue
            if p.get('type') == 'tool_use' and p.get('name') == 'Bash':
                cmd = (p.get('input') or {}).get('command') or ''
                pend[p['id']] = (norm(cmd), ts(r), cmd)
                k = norm(cmd)
                n[k] += 1
                ex.setdefault(k, cmd[:200])
                sess[k].add(os.path.basename(f)[:8])
            elif p.get('type') == 'tool_result' and p.get('tool_use_id') in pend:
                k, t0, cmd = pend.pop(p['tool_use_id'])
                out[k] += len(json.dumps(p.get('content')))
                d = ts(r) - t0 if t0 else 0
                dur[k] += d
                if d > 300:
                    slow.append((d, os.path.basename(f)[:8], cmd[:160].replace('\n', ' ')))

print(f"{'n':>4} {'sess':>4} {'outK':>6} {'durS':>6}  shape")
for k in sorted(n, key=lambda k: -(n[k] * (1 + out[k] / 4000 + dur[k] / 60)))[:top]:
    print(f"{n[k]:4} {len(sess[k]):4} {out[k]//1000:6} {int(dur[k]):6}  {k}\n{'':24}e.g. {ex[k][:150]!r}")
print(f"\n>5min calls: {len(slow)}")
for d, s, c in sorted(slow, reverse=True)[:15]:
    print(f"{int(d)}s {s} {c}")
