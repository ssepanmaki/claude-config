import json, glob, os, statistics as S, collections
root = os.path.expanduser('~/.claude/projects/C--Users-OMISTAJA-Growth-Platform')
big = collections.Counter(); nb = collections.Counter(); calls_per_turn = []; kinds = collections.Counter(); cost = collections.Counter()
for f in sorted(glob.glob(f'{root}/*.jsonl'), key=os.path.getmtime)[-45:]:
    kind = None; n = 0; tok = 0
    def close():
        if kind: calls_per_turn.append(n); kinds[kind] += 1; cost[kind] += tok; big[min(n//10,5)] += tok; nb[min(n//10,5)] += 1
    for l in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(l)
        except ValueError: continue
        if j.get('isSidechain'): continue
        c = (j.get('message') or {}).get('content')
        if j.get('type') == 'user' and not j.get('isMeta') and (isinstance(c, str) or any(p.get('type') == 'text' for p in c or [])):
            close(); text = c if isinstance(c, str) else ''.join(p.get('text', '') for p in c if p.get('type') == 'text')
            kind = 'notification' if '<task-notification' in text or 'side-sessions-event' in text or 'ci-monitor' in text else 'user'
            n = 0; tok = 0; continue
        u = (j.get('message') or {}).get('usage') if j.get('type') == 'assistant' else None
        if u: n += 1; tok += u.get('input_tokens',0)+u.get('cache_read_input_tokens',0)+u.get('cache_creation_input_tokens',0)
    close()
q = sorted(calls_per_turn)
print('turns', len(q), 'calls/turn median', S.median(q), 'p90', q[int(.9*len(q))], 'max', q[-1])
for k in kinds: print(k, 'turns', kinds[k], 'context-tokens sent', f'{cost[k]/1e6:.1f}M')
tot=sum(big.values())
for b in sorted(big): print(f"calls {b*10}-{b*10+9 if b<5 else 999}: {nb[b]} turns, {big[b]/tot:.0%} of tokens")
