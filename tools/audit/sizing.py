import json, glob, os, statistics as st, sys
root = os.path.expanduser('~/.claude/projects')
rows = []
for f in glob.glob(f'{root}/*Growth-Platform*/**/subagents/*.jsonl', recursive=True):
    meta = f[:-6] + '.meta.json'
    m = json.load(open(meta, encoding='utf8')) if os.path.exists(meta) else {}
    if m.get('agentType') in ('Explore', 'statusline-setup', 'claude-code-guide'): continue
    first = peak = turns = 0; tools = {}; res_chars = 0; brief = 0; compacts = 0; out = 0
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except: continue
        if j.get('type') == 'user':
            c = j.get('message', {}).get('content')
            if isinstance(c, str):
                if not brief: brief = len(c)
            elif isinstance(c, list):
                for p in c:
                    if p.get('type') == 'tool_result':
                        r = p.get('content'); res_chars += len(json.dumps(r)) if r else 0
                    elif p.get('type') == 'text' and not brief: brief = len(p.get('text', ''))
        if j.get('type') == 'system' and 'compact' in json.dumps(j).lower()[:400]: compacts += 1
        u = j.get('message', {}).get('usage') if j.get('type') == 'assistant' else None
        if u:
            ctx = u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
            if not first: first = ctx
            peak = max(peak, ctx); turns += 1; out += u.get('output_tokens', 0)
            for p in j['message'].get('content', []):
                if p.get('type') == 'tool_use': tools[p['name']] = tools.get(p['name'], 0) + 1
    if turns < 3: continue
    rows.append(dict(type=m.get('agentType', '?'), model=m.get('model', '?'), desc=m.get('description', '')[:40], first=first, peak=peak,
                     calls=sum(tools.values()), reads=tools.get('Read', 0), bash=tools.get('Bash', 0), edits=tools.get('Edit', 0) + tools.get('Write', 0),
                     res_k=res_chars // 4000, brief=brief, compacts=compacts, out=out))
print(len(rows), 'worker-ish subagents')
def q(xs, p): xs = sorted(xs); return xs[int(p * (len(xs) - 1))]
for t in sorted({r['type'] for r in rows}):
    rs = [r for r in rows if r['type'] == t]
    pk = [r['peak'] for r in rs]
    print(f"{t:18} n={len(rs):3} start med={q([r['first'] for r in rs],.5)//1000}k  peak med={q(pk,.5)//1000}k p75={q(pk,.75)//1000}k p90={q(pk,.9)//1000}k  >120k={sum(p>120000 for p in pk)}  compacted={sum(r['compacts']>0 for r in rs)}")
# what predicts peak? per-call cost
gr = [r for r in rows if r['calls'] >= 5]
per = [(r['peak'] - r['first']) / r['calls'] for r in gr]
print('growth per tool call: med', int(q(per, .5)), 'p75', int(q(per, .75)))
for k in ('calls', 'reads', 'bash', 'edits', 'res_k', 'brief'):
    xs = [r[k] for r in gr]; ys = [r['peak'] for r in gr]
    try: print(f'corr(peak,{k}) = {st.correlation(xs, ys):.2f}')
    except Exception as e: print(k, e)
print('\nbiggest:')
for r in sorted(rows, key=lambda r: -r['peak'])[:12]:
    print(f"{r['peak']//1000:4}k start {r['first']//1000}k calls={r['calls']:3} reads={r['reads']:3} bash={r['bash']:3} edits={r['edits']:3} resultsâ‰ˆ{r['res_k']}k  {r['type']}  {r['desc']}")
