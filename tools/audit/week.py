"""7-day token audit across all projects: cost by day/model/role, lead context per call, spawns, signals, fillers.
usage: python -I week.py [days=7]"""
import collections as C
import glob
import json
import os
import re
import sys
import time

root = os.path.expanduser('~/.claude/projects'); days = float(sys.argv[1]) if len(sys.argv) > 1 else 7
since = time.time() - days * 86400; cut = time.strftime('%Y-%m-%d', time.gmtime(since))
P = {'opus': (4.0, 0.20, 20.0), 'sonnet': (2.0, 0.10, 10.0), 'haiku': (0.10, 0.01, 0.50)}  # $/M: in, cache read, out
def fam(m): return next((k for k in P if k in (m or '')), 'other')
def cost(u, f):
    pi, pc, po = P.get(f, P['sonnet'])
    return (u.get('input_tokens', 0) * pi + u.get('cache_creation_input_tokens', 0) * pi * 1.25
            + u.get('cache_read_input_tokens', 0) * pc + u.get('output_tokens', 0) * po) / 1e6
day = C.defaultdict(lambda: C.defaultdict(lambda: [0, 0, 0.0]))  # day -> role/fam -> calls, ctx tokens, $
proj = C.defaultdict(lambda: [0, 0, 0.0]); sess = []; spawn = C.Counter(); sig = C.Counter()
fill = C.defaultdict(lambda: [0, 0]); ctxbuck = C.Counter(); skipped = []
SIG = {'hook error': 'hook error', 'recon calls': 'recon nudge', 'Hard stop': 'hard stop', "hasn't heard from you": 'app nudge',
       'Stop hook': 'stop-hook block', 'narrowed to': 'narrowed', 'is_error": true': 'tool error'}
for f in glob.glob(f'{root}/*/**/*.jsonl', recursive=True):
    if os.path.getmtime(f) < since: continue
    side = os.sep + 'subagents' + os.sep in f
    parts = f.split(os.sep); pj = parts[-4] if side else parts[-2]
    pj = re.sub(r'^C--Users-OMISTAJA-?', '', pj)[:26] or 'home'
    role = 'sub' if side else 'lead'; seen = set(); s = [0, 0.0, 0, 0]; names = {}
    for line in open(f, encoding='utf8', errors='ignore'):
        for k, v in SIG.items():
            if k in line: sig[v] += 1
        if '"type":"assistant"' not in line and '"type":"user"' not in line: continue
        try: j = json.loads(line)
        except Exception: continue
        m = j.get('message') or {}; c = m.get('content')
        if j.get('type') == 'user' and isinstance(c, list) and not side:
            for p in c:
                if isinstance(p, dict) and p.get('type') == 'tool_result':
                    n = names.get(p.get('tool_use_id'), '?'); x = p.get('content')
                    L = len(x) if isinstance(x, str) else sum(len(q.get('text', '')) for q in x if isinstance(q, dict)) if isinstance(x, list) else 0
                    fill[n][0] += 1; fill[n][1] += L // 4
        if j.get('type') != 'assistant' or not m.get('usage'): continue
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get('type') == 'tool_use':
                    names[p.get('id')] = p.get('name')
                    if p.get('name') == 'Agent' and (j.get('timestamp') or '')[:10] >= cut:
                        i = p.get('input') or {}; spawn[(role, i.get('subagent_type') or 'default', (i.get('model') or 'inherit')[:12])] += 1
        ts = (j.get('timestamp') or '')[:10]
        if ts < cut: continue
        mid = (m.get('id') or '') + (j.get('requestId') or '')
        if mid in seen: continue
        seen.add(mid); u = m['usage']; fm = fam(m.get('model'))
        n = u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('input_tokens', 0)
        cc = cost(u, fm); r = day[ts][f'{role}/{fm}']; r[0] += 1; r[1] += n; r[2] += cc
        q = proj[pj]; q[0] += 1; q[1] += n; q[2] += cc; s[0] += 1; s[1] += cc; s[2] = max(s[2], n); s[3] += n
        if role == 'lead': ctxbuck['<50k' if n < 50e3 else '50-100k' if n < 100e3 else '100-150k' if n < 150e3 else '150k+'] += 1
    if s[0]: sess.append((s[1], s[0], s[2], pj, os.path.basename(f)[:8], role))
tot = sum(v[2] for d in day.values() for v in d.values())
print(f'== {days:g} days, est cost ${tot:,.0f} (list-price units)')
print('day        role/model       calls   avgctx      $')
for d in sorted(day):
    for k, v in sorted(day[d].items(), key=lambda x: -x[1][2]):
        print(f'{d} {k:16} {v[0]:6} {v[1] // max(v[0], 1) // 1000:6}k {v[2]:8.0f}')
by = C.defaultdict(float)
for d in day.values():
    for k, v in d.items(): by[k] += v[2]
print('\nby role/model $:', {k: round(v) for k, v in sorted(by.items(), key=lambda x: -x[1])})
print('lead calls by context size:', dict(ctxbuck))
print('\nprojects:'); [print(f'  {p:26} calls {v[0]:6} $ {v[2]:7.0f}') for p, v in sorted(proj.items(), key=lambda x: -x[1][2]) if v[2] >= 0.5]
print('\ntop sessions ($, calls, peak ctx):')
for b in sorted(sess, reverse=True)[:10]: print(f'  ${b[0]:6.0f} {b[1]:5} peak {b[2] // 1000}k {b[3]} {b[4]} {b[5]}')
print('\nAgent spawns (role, type, model):'); [print(f'  {k} {v}') for k, v in spawn.most_common(12)]
print('\nsignals:', dict(sig))
print('\nlead context fillers (tool results, ~tokens, count):')
for k, v in sorted(fill.items(), key=lambda x: -x[1][1])[:10]: print(f'  {k:28} {v[1] // 1000:7}k  n={v[0]}  avg {v[1] // max(v[0], 1)}')
