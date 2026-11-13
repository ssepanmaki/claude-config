import json, glob, os, re, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
files = [f for f in glob.glob(f'{root}/*Growth-Platform*/**/*.jsonl', recursive=True) if os.path.getmtime(f) > since]
tot = C.Counter(); by_kind = C.Counter(); res_tool = C.Counter(); res_cmd = C.Counter(); reads = C.Counter()
starts = []; cw_events = 0; big_cw = C.Counter(); turns_small = 0; turns = 0; out_tok = 0
def key_cmd(cmd):
    c = cmd.strip()
    for pat, name in [(r'\bgit (diff|show|log)', 'git diff/show/log'), (r'\bgit status', 'git status'), (r'pytest', 'pytest'),
                      (r'playwright|e2e', 'playwright/e2e'), (r'\b(npm|pnpm|npx) (run )?(test|vitest)', 'js tests'),
                      (r'dotnet (test|build)', 'dotnet test/build'), (r'\b(npm|pnpm|npx) (run )?(build|lint|tsc|typecheck)|\btsc\b', 'js build/lint/tsc'),
                      (r'^(cat|head|tail|sed -n|type|Get-Content)\b', 'file read via shell'), (r'\b(grep|rg|findstr|Select-String)\b', 'grep'),
                      (r'\b(ls|find|dir|Get-ChildItem|tree)\b', 'ls/find'), (r'curl|Invoke-WebRequest', 'curl'), (r'sqlcmd|psql|sqlite', 'db cli'),
                      (r'\bgh\b', 'gh'), (r'python|node ', 'python/node script')]:
        if re.search(pat, c): return name
    return 'other: ' + c.split()[0][:20] if c else 'other'
for f in files:
    sub = '/subagents/' in f.replace(chr(92), '/')
    meta = {}
    if sub and os.path.exists(f[:-6] + '.meta.json'): meta = json.load(open(f[:-6] + '.meta.json', encoding='utf8'))
    model_meta = meta.get('model', '')
    kind = meta.get('agentType', 'subagent?') if sub else 'main session'
    pending = {}; first = True; prev_ts = None
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except: continue
        m = j.get('message') or {}
        if j.get('type') == 'assistant' and m.get('usage'):
            model = m.get('model', '')
            if 'opus' in model and kind == 'general-purpose': break  # skip Opus review agents
            u = m['usage']; cr = u.get('cache_read_input_tokens', 0); cc = u.get('cache_creation_input_tokens', 0); it = u.get('input_tokens', 0); ot = u.get('output_tokens', 0)
            tot['cache_read'] += cr; tot['cache_write'] += cc; tot['input'] += it; tot['output'] += ot
            by_kind[kind] += cr + cc + it + ot
            if first and sub: starts.append((cr + cc + it, kind)); first = False
            elif cc > 20000: big_cw[kind] += cc; cw_events += 1
            turns += 1; turns_small += ot < 150
            for p in m.get('content', []):
                if p.get('type') == 'tool_use':
                    name = p['name']; inp = p.get('input', {})
                    label = key_cmd(inp.get('command', '')) if name in ('Bash', 'PowerShell') else name
                    if name == 'Read': reads[(f, inp.get('file_path', ''))] += 1
                    pending[p['id']] = (name, label)
        elif j.get('type') == 'user' and isinstance(m.get('content'), list):
            for p in m['content']:
                if p.get('type') == 'tool_result' and p.get('tool_use_id') in pending:
                    name, label = pending.pop(p['tool_use_id'])
                    n = len(json.dumps(p.get('content', ''))) // 4
                    res_tool[name] += n
                    if name in ('Bash', 'PowerShell'): res_cmd[label] += n
print(f'{len(files)} transcripts, 7 days, Opus general-purpose excluded')
T = sum(tot.values()); print(f'total {T/1e6:.0f}M: ' + ', '.join(f'{k} {v/1e6:.0f}M' for k, v in tot.items()))
print(f'cost-weighted (read .1, write 1.25, in 1, out 5): ' + ', '.join(f'{k} {v*w/1e6:.0f}M' for (k, v), w in zip(tot.items(), (0.1, 1.25, 1, 5))))
print('by kind:', ', '.join(f'{k} {v/1e6:.0f}M' for k, v in by_kind.most_common(6)))
print(f'mid-run cache rewrites >20k: {cw_events} events, ' + ', '.join(f'{k} {v/1e6:.1f}M' for k, v in big_cw.most_common(4)))
s = sorted(x for x, _ in starts); print(f'subagent start context: n={len(s)} median {s[len(s)//2]//1000}k p90 {s[int(len(s)*.9)]//1000}k')
print(f'turns {turns}, with <150 output tokens: {turns_small} ({100*turns_small//max(turns,1)}%)')
print('tool result tokens by tool:', ', '.join(f'{k} {v/1e6:.1f}M' for k, v in res_tool.most_common(8)))
print('shell output by command kind:'); [print(f'  {v/1e6:5.2f}M  {k}') for k, v in res_cmd.most_common(14)]
rr = sum(c - 1 for c in reads.values() if c > 1); print(f'repeat Reads of same file in same transcript: {rr} (of {sum(reads.values())})')
