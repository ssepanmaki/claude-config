"""Lead wake-ups from background Bash: which commands, by day, and when the bg-policy block first fired. argv[1] = days (7)."""
import json, glob, os, re, sys, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 7) * 86400
first_block = None; by_day = C.Counter(); by_cmd = C.Counter(); by_proj = C.Counter(); status = C.Counter(); fg = C.Counter(); ex = {}
def kind(cmd):
    c = re.sub(r'^(cd \S+\s*(&&|;)\s*)+', '', cmd.strip()).replace('FULL_GATE=1 ', 'FULL_GATE ')
    return ' '.join(c.split()[:3])[:50]
for f in glob.glob(f'{root}/*/*.jsonl'):
    if os.path.getmtime(f) < since: continue
    cmds = {}
    for l in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(l)
        except ValueError: continue
        if j.get('isSidechain'): continue
        m = j.get('message') or {}; c = m.get('content'); day = (j.get('timestamp') or '')[:10]
        for p in c if isinstance(c, list) else []:
            if p.get('type') == 'tool_use' and p.get('name') == 'Bash' and p['input'].get('run_in_background'):
                cmds[p['id']] = p['input'].get('command', '')
            if p.get('type') == 'tool_result' and 'Only FULL_GATE=1 runs may go' in json.dumps(p.get('content')):
                first_block = min(x for x in (first_block, j.get('timestamp')) if x) if (first_block or j.get('timestamp')) else None
        t = c if isinstance(c, str) else ''.join(p.get('text', '') for p in c or [] if isinstance(p, dict) and p.get('type') == 'text')
        if j.get('type') != 'user' or '<task-notification' not in t: continue
        tid = re.search(r'<tool-use-id>(\S+?)</tool-use-id>', t)
        if not tid or tid.group(1) not in cmds: continue
        cmd = cmds[tid.group(1)]; k = kind(cmd)
        if os.environ.get('AFTER') and (j.get('timestamp') or '') < os.environ['AFTER']: continue
        by_day[day] += 1; by_cmd[k] += 1; by_proj[os.path.basename(os.path.dirname(f))[-24:]] += 1
        status[(re.search(r'<status>(\w+)', t) or [None, '?'])[1]] += 1; ex.setdefault(k, cmd[:140])
print('first bg-policy block:', first_block)
print('by day:', dict(sorted(by_day.items())))
print('status:', dict(status)); print('by project:', dict(by_proj.most_common(5)))
for k, n in by_cmd.most_common(int(os.environ.get("TOP", 15))): print(f'{n:4} {k!r:55} e.g. {ex[k]!r}')
