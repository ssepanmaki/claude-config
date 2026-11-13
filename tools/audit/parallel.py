"""Lead wake-up cost vs worker cost, concurrency and file overlap of workers, last N days (argv[1], default 7)."""
import json, glob, os, sys, time, statistics as S, collections as C
from datetime import datetime
root = os.path.expanduser('~/.claude/projects'); since = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 7) * 86400
ts = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
ctx = lambda u: u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
wake_tok = []; wake_calls = []; user_tok = []; work_tok = []; conc = []; overlap = 0; pairs = 0; walls = []
for f in glob.glob(f'{root}/*/*.jsonl'):
    if os.path.getmtime(f) < since: continue
    kind = None; tok = 0; calls = 0; seen = set()
    def close():
        if kind == 'wake': wake_tok.append(tok); wake_calls.append(calls)
        elif kind == 'user': user_tok.append(tok)
    for l in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(l)
        except ValueError: continue
        if j.get('isSidechain'): continue
        m = j.get('message') or {}; c = m.get('content')
        if j.get('type') == 'user' and not j.get('isMeta'):
            text = c if isinstance(c, str) else ''.join(p.get('text', '') for p in c or [] if p.get('type') == 'text')
            if text:
                close(); kind = 'wake' if '<task-notification' in text else 'user'; tok = calls = 0
        if m.get('usage') and m.get('id') not in seen: seen.add(m.get('id')); tok += ctx(m['usage'])
        if m.get('usage'): calls += sum(p.get('type') == 'tool_use' for p in c or [] if isinstance(p, dict))
    close()
    sub = glob.glob(os.path.join(f[:-6], 'subagents', 'agent-*.jsonl'))
    spans = []
    for s in sub:
        meta = s[:-6] + '.meta.json'
        mt = json.load(open(meta, encoding='utf8')) if os.path.exists(meta) else {}
        if mt.get('agentType') not in ('worker', 'gp-worker'): continue
        t0 = t1 = None; tok = 0; files = set(); seen = set()
        for l in open(s, encoding='utf8', errors='ignore'):
            try: j = json.loads(l)
            except ValueError: continue
            if j.get('timestamp'): t = ts(j['timestamp']); t0 = t0 or t; t1 = t
            m = j.get('message') or {}
            if m.get('usage') and m.get('id') not in seen: seen.add(m.get('id')); tok += ctx(m['usage'])
            for p in m.get('content') or [] if isinstance(m.get('content'), list) else []:
                if p.get('type') == 'tool_use' and p.get('name') in ('Edit', 'Write'): files.add(os.path.basename(p['input'].get('file_path', '')))
        if t0: work_tok.append(tok); spans.append((t0, t1, files)); walls.append((t1 - t0) / 60)
    for i, a in enumerate(spans):
        conc.append(sum(1 for b in spans if b[0] < a[1] and a[0] < b[1]))
        for b in spans[i + 1:]:
            if b[0] < a[1] and a[0] < b[1]: pairs += 1; overlap += bool(a[2] & b[2])
q = lambda xs: f'median {S.median(xs)/1000:.0f}k, total {sum(xs)/1e6:.1f}M (n={len(xs)})' if xs else 'n=0'
print('lead wake-up turn tokens:', q(wake_tok), '| calls median', S.median(wake_calls) if wake_calls else '-')
print('lead user turn tokens:   ', q(user_tok))
print('worker job tokens:       ', q(work_tok))
print('worker wall minutes median', round(S.median(walls), 1) if walls else '-', '| concurrency per worker:', dict(sorted(C.Counter(conc).items())))
print(f'concurrent worker pairs {pairs}, editing a same-named file {overlap}')
