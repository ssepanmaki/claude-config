import json, glob, os, re, collections
root = os.path.expanduser('~/.claude/projects/C--Users-OMISTAJA-Growth-Platform')
FIX = re.compile(r"\b(no+|wrong|not what|why (?:did|is|are)|still (?:broken|not|fail)|again|revert|you (?:forgot|missed|broke)|didn'?t|doesn'?t work|that'?s not)\b", re.I)
by = collections.defaultdict(lambda: [0, 0]); per = []
for f in glob.glob(f'{root}/*.jsonl'):
    k = 0; n = 0
    for l in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(l)
        except ValueError: continue
        if j.get('isSidechain'): continue
        if j.get('type') == 'system' and j.get('subtype') == 'compact_boundary': k += 1; continue
        c = (j.get('message') or {}).get('content')
        if j.get('type') != 'user' or j.get('isMeta') or j.get('isCompactSummary'): continue
        t = c if isinstance(c, str) else ''.join(p.get('text', '') for p in (c or []) if p.get('type') == 'text')
        if not t.strip() or t.lstrip().startswith('<'): continue
        b = min(k, 3); by[b][0] += 1; by[b][1] += bool(FIX.search(t[:400]))
    if k or n: per.append(k)
per.sort(); print('sessions', len(per), 'compacts per session: 0:', per.count(0), '1-2:', sum(1 for x in per if 1 <= x <= 2), '3+:', sum(1 for x in per if x >= 3), 'max', per[-1])
for b in sorted(by): print(f'after {b}{"+" if b == 3 else ""} compacts: {by[b][0]} user msgs, {by[b][1] / max(1, by[b][0]):.0%} look like corrections')
