"""Queue-flow metrics since a date (argv[1], default 5 days ago): worker jobs, calls/job, commits/job,
hand-back length, lead wake-ups per worker job. Run before/after the queue change to compare."""
import json, glob, os, re, sys, time, statistics as S
root = os.path.expanduser('~/.claude/projects')
since = time.mktime(time.strptime(sys.argv[1], '%Y-%m-%d')) if len(sys.argv) > 1 else time.time() - 5 * 86400
jobs = []; wake = 0; leads = 0
for f in glob.glob(f'{root}/*/*.jsonl'):
    if os.path.getmtime(f) < since: continue
    w = 0
    for l in open(f, encoding='utf8', errors='ignore'):
        if '<task-notification' in l and '"type":"user"' in l: w += 1
    if w: wake += w; leads += 1
for f in glob.glob(f'{root}/*/*/subagents/agent-*.jsonl'):
    if os.path.getmtime(f) < since: continue
    meta = f[:-6] + '.meta.json'
    m = json.load(open(meta, encoding='utf8')) if os.path.exists(meta) else {}
    if m.get('agentType') not in ('worker', 'gp-worker'): continue
    calls = commits = 0; hb = ''
    for l in open(f, encoding='utf8', errors='ignore'):
        try: c = (json.loads(l).get('message') or {}).get('content')
        except ValueError: continue
        for p in c if isinstance(c, list) else []:
            if p.get('type') != 'tool_use': continue
            calls += 1
            if re.search(r'git commit', json.dumps(p.get('input'))): commits += 1
            if p.get('name') == 'SubagentHandback': hb = p['input'].get('message', '')
    jobs.append((calls, commits, len(hb)))
if not jobs: sys.exit('no worker jobs')
med = lambda i: S.median(j[i] for j in jobs)
print(f'worker jobs {len(jobs)} | calls/job median {med(0)} | commits/job median {med(1)} (total {sum(j[1] for j in jobs)})')
print(f'hand-back chars median {med(2)}, max {max(j[2] for j in jobs)}')
print(f'lead wake-ups (task notifications) {wake} over {leads} lead sessions; per worker job {wake / len(jobs):.2f}')
