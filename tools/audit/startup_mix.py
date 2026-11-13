import json, glob, os, sys, collections, statistics as S
root = os.path.expanduser('~/.claude/projects/C--Users-OMISTAJA-Growth-Platform')
files = sorted(glob.glob(f'{root}/*.jsonl'), key=os.path.getmtime)[-40:]
def tok(x): return len(json.dumps(x, ensure_ascii=False)) // 4
def label(j):
    t = j.get('type')
    if t == 'attachment':
        a = j.get('attachment') or {}
        return 'att:' + str(a.get('type'))
    if t == 'user':
        if j.get('isCompactSummary'): return 'compact_summary'
        if j.get('isMeta'): return 'user_meta'
        return 'user'
    return t
first = collections.defaultdict(list); post = collections.defaultdict(list); totals_f = []; totals_p = []
for f in files:
    lines = [json.loads(l) for l in open(f, encoding='utf8', errors='ignore') if l.strip().startswith('{')]
    seg = collections.Counter(); mode = 'first'; done_first = False
    for j in lines:
        if j.get('isSidechain'): continue
        if j.get('type') == 'system' and j.get('subtype') == 'compact_boundary':
            seg = collections.Counter(); mode = 'post'; continue
        u = (j.get('message') or {}).get('usage') if j.get('type') == 'assistant' else None
        if u:
            n = u.get('input_tokens',0)+u.get('cache_read_input_tokens',0)+u.get('cache_creation_input_tokens',0)
            if mode == 'first' and not done_first:
                totals_f.append((n, sum(seg.values()))); [first[k].append(v) for k,v in seg.items()]; done_first = True
            elif mode == 'post':
                totals_p.append((n, sum(seg.values()))); [post[k].append(v) for k,v in seg.items()]; mode = 'x'
            continue
        if mode in ('first','post') and not (mode=='first' and done_first):
            seg[label(j)] += tok(j.get('attachment') or j.get('message') or j)
def show(name, d, tot):
    print(f'== {name}: n={len(tot)} ctx median {int(S.median([a for a,b in tot]))}, transcript-visible median {int(S.median([b for a,b in tot]))} => hidden (system prompt+tools) ~{int(S.median([a-b for a,b in tot]))}')
    for k,v in sorted(d.items(), key=lambda kv: -S.median(kv[1])): print(f'  {k:40} median {int(S.median(v)):6}  in {len(v)}')
show('first call', first, totals_f); show('after compact', post, totals_p)
