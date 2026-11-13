import json, glob, os, re, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
files = [f for f in glob.glob(f'{root}/*Growth-Platform*/*.jsonl') if os.path.getmtime(f) > since]
rows = []; trig_all = C.Counter(); tools_all = C.Counter()
for f in files:
    turns = toks = peak = calls = compacts = 0; ctxs = []; trig = C.Counter(); tools = C.Counter(); title = ''
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except: continue
        m = j.get('message') or {}
        if j.get('type') == 'summary': title = j.get('summary', '')[:40]
        if j.get('type') == 'system' and j.get('subtype') == 'compact_boundary': compacts += 1
        if j.get('type') == 'user' and not j.get('isMeta'):
            c = m.get('content'); txt = c if isinstance(c, str) else ''.join(p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text') if isinstance(c, list) else ''
            if txt.strip():
                t = ('task-notification' if '<task-notification' in txt else 'agent-message' if '<agent-message' in txt or 'Subagent hand-back' in txt
                     else 'side-session' if 'side-sessions-event' in txt else 'ci-monitor' if 'ci-monitor-event' in txt
                     else 'codebus/relay' if re.search(r'codebus|relay|frame', txt[:300], re.I) else 'cross-session' if 'From ' in txt[:80] or '<cross-session' in txt
                     else 'slash-cmd' if txt.lstrip().startswith('<command-') else 'user')
                trig[t] += 1
        if j.get('type') == 'assistant' and m.get('usage'):
            u = m['usage']; n = u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('input_tokens', 0)
            turns += 1; toks += n + u.get('output_tokens', 0); peak = max(peak, n); ctxs.append(n)
            for p in m.get('content', []):
                if p.get('type') == 'tool_use':
                    calls += 1; nm = p['name']
                    if nm.startswith('mcp__'): nm = 'mcp:' + nm.split('__')[1]
                    tools[nm] += 1
    if not turns: continue
    trig_all.update(trig); tools_all.update(tools)
    rows.append(dict(f=os.path.basename(f)[:8], proj=os.path.basename(os.path.dirname(f))[-22:], toks=toks, turns=turns, avg=sum(ctxs) // len(ctxs), peak=peak, calls=calls, compacts=compacts, trig=trig, tools=tools))
rows.sort(key=lambda r: -r['toks']); T = sum(r['toks'] for r in rows)
print(f'{len(rows)} main sessions, {T/1e6:.0f}M')
print('top sessions:')
for r in rows[:10]:
    print(f"  {r['toks']/1e6:5.0f}M {r['f']} {r['proj']:22} turns {r['turns']:5} avg ctx {r['avg']//1000:3}k peak {r['peak']//1000}k compacts {r['compacts']} | " + ', '.join(f'{k} {v}' for k, v in r['trig'].most_common(4)))
print('turn triggers (all main):', ', '.join(f'{k} {v}' for k, v in trig_all.most_common()))
print('main-session tool calls:', ', '.join(f'{k} {v}' for k, v in tools_all.most_common(14)))
# cost per triggering event type ~ avg ctx; tokens in turns of the turn chain each trigger
avgctx = sum(r['avg'] * r['turns'] for r in rows) / sum(r['turns'] for r in rows)
print(f'avg main ctx {avgctx/1000:.0f}k; turns/trigger {sum(r["turns"] for r in rows)/max(sum(trig_all.values()),1):.1f}')
