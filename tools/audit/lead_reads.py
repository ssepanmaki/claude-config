import json, glob, os, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
files = [f for f in glob.glob(f'{root}/*Growth-Platform*/*.jsonl') if os.path.getmtime(f) > since]
rows = []; byfile = C.Counter(); kinds = C.Counter()
for f in files:
    ids = {}
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except ValueError: continue
        m = j.get('message') or {}
        for p in (m.get('content') if isinstance(m.get('content'), list) else []):
            if p.get('type') == 'tool_use' and p['name'] == 'Read': ids[p['id']] = p['input']
            if p.get('type') == 'tool_result' and p.get('tool_use_id') in ids:
                b = p.get('content'); inp = ids[p['tool_use_id']]
                img = isinstance(b, list) and any(x.get('type') == 'image' for x in b)
                n = len(b if isinstance(b, str) else json.dumps(b)) // 4
                fp = inp.get('file_path', ''); ext = os.path.splitext(fp)[1].lower()
                rows.append((n, fp, 'limit' in inp or 'offset' in inp, img)); byfile[fp] += n; kinds[(ext, img, 'ranged' if ('limit' in inp or 'offset' in inp) else 'whole')] += n
rows.sort(reverse=True)
print('reads', len(rows), 'total', sum(r[0] for r in rows) // 1000, 'k')
for k, v in kinds.most_common(10): print(f'  {v//1000:6}k', k)
for n, fp, ranged, img in rows[:15]: print(f'  {n//1000:4}k ranged={ranged} img={img} {fp[-80:]}')
