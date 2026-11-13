"""Real context growth in GP lead sessions: usage delta between API calls, charged to what came in between."""
import json, glob, os, re, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
files = [f for f in glob.glob(f'{root}/*Growth-Platform*/*.jsonl') if os.path.getmtime(f) > since]
grow = C.Counter(); cnt = C.Counter(); big = []
def ctx(u): return u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
def label(name, inp):
    if name in ('Bash', 'PowerShell'):
        c = inp.get('command', '')
        for pat, k in [(r'git (diff|show|log)', 'git diff/show/log'), (r'git (merge|rebase|commit|push|worktree|branch|checkout)', 'git landing'),
                       (r'pytest|vitest|npm (run )?test|playwright|e2e', 'tests'), (r'build|tsc|lint|typecheck|npm ci|docker', 'build/install'),
                       (r'\b(grep|rg|Select-String)\b', 'grep'), (r'^\s*(cat|head|tail|sed -n|type|Get-Content)\b', 'file read via shell'),
                       (r'attc-codebus|attc-relay', 'codebus/relay'), (r'python|node ', 'script')]:
            if re.search(pat, c): return 'Bash: ' + k
        return 'Bash: other'
    return name
for f in files:
    prev = None; pending = []; ids = {}
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except ValueError: continue
        m = j.get('message') or {}; t = j.get('type'); c = m.get('content')
        if t == 'assistant' and m.get('usage') and not j.get('isSidechain'):
            n = ctx(m['usage'])
            if prev is not None and 0 < n - prev < 60000 and pending:
                share = (n - prev) / len(pending)
                for k in pending: grow[k] += share; cnt[k] += 1
                if n - prev > 15000: big.append((n - prev, pending[:3], os.path.basename(f)[:8]))
            prev = n; pending = []
            for p in c or []:
                if p.get('type') == 'tool_use': ids[p['id']] = label(p['name'], p.get('input', {}))
        elif t == 'user':
            if isinstance(c, str):
                pending.append('notification' if '<task-notification' in c else 'user/hook text')
            else:
                for p in c or []:
                    if p.get('type') == 'tool_result': pending.append(ids.get(p.get('tool_use_id'), '?'))
                    elif p.get('type') == 'text': pending.append('notification' if '<task-notification' in p['text'] else 'user/hook text')
tot = sum(grow.values())
print(f'{len(files)} leads, real context added ~{tot/1e6:.2f}M tokens')
for k, v in grow.most_common(16): print(f'  {v/1e3:7.0f}k {100*v/tot:4.1f}%  n={cnt[k]:5}  avg {v/cnt[k]:6.0f}  {k}')
big.sort(reverse=True); print('biggest single jumps:'); [print('  ', b) for b in big[:10]]
