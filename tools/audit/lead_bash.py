import json, glob, os, re, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
cnt = C.Counter(); ctx_sum = C.Counter(); ex = {}
for f in glob.glob(f'{root}/*Growth-Platform*/*.jsonl'):
    if os.path.getmtime(f) < since: continue
    for line in open(f, encoding='utf8', errors='ignore'):
        if '"tool_use"' not in line: continue
        try: j = json.loads(line)
        except: continue
        m = j.get('message') or {}; u = m.get('usage') or {}
        ctx = u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
        for p in m.get('content', []):
            if p.get('type') != 'tool_use' or p['name'] not in ('Bash', 'PowerShell'): continue
            c = p['input'].get('command', '')
            k = next((n for pat, n in [(r'attc-(codebus|relay)', 'attc codebus/relay'), (r'git (worktree|branch -[dD]|push|merge|rebase|cherry-pick|commit|checkout|switch|reset)', 'git landing/branching'),
                (r'git (diff|show|log)', 'git diff/show/log (reviewing)'), (r'git status|git rev-parse|git fetch', 'git status/fetch'),
                (r'pytest|vitest|dotnet test|npm (run )?test|playwright|e2e', 'running tests'), (r'build|tsc|lint|typecheck', 'build/lint'),
                (r'gh (pr|run|api|issue)', 'gh'), (r'(grep|rg|findstr|Select-String)\b', 'grep'), (r'^\s*(cat|head|tail|sed -n|Get-Content|type)\b', 'reading files'),
                (r'\b(ls|find|Get-ChildItem|dir)\b', 'ls/find'), (r'gp-worktree-setup|\.ps1', 'ps1 scripts'), (r'python|node', 'python/node'),
                (r'curl|Invoke-WebRequest', 'curl'), (r'sleep|Start-Sleep|timeout ', 'waiting')] if re.search(pat, c)), 'other')
            cnt[k] += 1; ctx_sum[k] += ctx; ex.setdefault(k, c[:70].replace('\n', ' '))
T = sum(ctx_sum.values())
for k, n in cnt.most_common():
    print(f'{n:5} calls  {ctx_sum[k]/1e6:5.0f}M ctx-tokens ({100*ctx_sum[k]//T:2}%)  {k:30} e.g. {ex[k]}')
