"""Last message of recent subagents: did they stop before finishing, and why."""
import json, glob, os, re, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 5 * 86400
pat = {'waiting on background': r'(background|running in bg|wait(ing)? for (the )?(completion|notification|it to)|will (report|check) (back|when))',
       'blocked/permission': r'(permission|denied|blocked|not allowed|cannot (run|access))',
       'budget checkpoint': r'(budget|what is left|remaining work|left for (a )?(fresh|next|the lead))',
       'gave up / partial': r"(couldn't|could not|unable to|didn't (finish|complete)|not (yet )?(done|complete|implemented)|stopp(ed|ing) here|TODO)"}
tally = C.Counter(); ex = C.defaultdict(list); n = 0
for f in glob.glob(f'{root}/*/*/subagents/agent-*.jsonl'):
    if os.path.getmtime(f) < since: continue
    meta = json.load(open(f[:-6] + '.meta.json', encoding='utf8')) if os.path.exists(f[:-6] + '.meta.json') else {}
    if meta.get('agentType') in ('Explore', 'claude-code-guide', 'statusline-setup'): continue
    last = ''; calls = 0; bg = 0
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except ValueError: continue
        if j.get('type') != 'assistant': continue
        for p in j['message'].get('content', []):
            if p.get('type') == 'text': last = p['text']
            if p.get('type') == 'tool_use':
                calls += 1; bg += bool(p.get('input', {}).get('run_in_background'))
    n += 1; hit = [k for k, r in pat.items() if re.search(r, last, re.I)]
    for k in hit or ['looks finished']: tally[k] += 1
    if hit and len(ex[hit[0]]) < 4: ex[hit[0]].append(f"{meta.get('agentType')} calls={calls} bg={bg}: {last[:260].replace(chr(10), ' ')}")
print(n, 'subagents (last 5 days)'); print(tally.most_common())
for k, v in ex.items():
    print('==', k); [print('  -', e) for e in v]
