"""What fills Growth Platform lead (main-session) context: chars/4 by source, last 7 days."""
import json, glob, os, time, collections as C
root = os.path.expanduser('~/.claude/projects'); since = time.time() - 7 * 86400
files = [f for f in glob.glob(f'{root}/*Growth-Platform*/*.jsonl') if os.path.getmtime(f) > since]
mix = C.Counter(); ntool = C.Counter(); first_ctx = []; agent_brief = []; reread = C.Counter(); att = C.Counter()
for f in files:
    names = {}; seen = C.Counter(); fc = None
    for line in open(f, encoding='utf8', errors='ignore'):
        try: j = json.loads(line)
        except ValueError: continue
        t = j.get('type'); m = j.get('message') or {}
        if t == 'attachment' or j.get('attachment'):
            a = j.get('attachment') or {}
            att[a.get('type', '?')] += len(json.dumps(a)) // 4; continue
        if t == 'summary' or j.get('isCompactSummary'):
            mix['compact summary'] += len(json.dumps(m)) // 4; continue
        c = m.get('content')
        if t == 'assistant':
            if fc is None and m.get('usage'):
                u = m['usage']; fc = u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
            for p in c or []:
                if p.get('type') == 'text': mix['assistant text'] += len(p['text']) // 4
                elif p.get('type') == 'thinking': mix['thinking'] += len(p.get('thinking', '')) // 4
                elif p.get('type') == 'tool_use':
                    names[p['id']] = p['name']; n = len(json.dumps(p.get('input', {}))) // 4
                    mix['tool input: ' + p['name']] += n; ntool[p['name']] += 1
                    if p['name'] == 'Agent': agent_brief.append(n)
                    if p['name'] == 'Read':
                        k = p['input'].get('file_path', ''); seen[k] += 1
                        if seen[k] > 1: reread['re-Read same file'] += 1
        elif t == 'user':
            if isinstance(c, str):
                key = 'user: task-notification' if '<task-notification' in c else 'user: system/hook text' if j.get('isMeta') or c.startswith('<') else 'user typed'
                mix[key] += len(c) // 4; continue
            for p in c or []:
                if p.get('type') == 'tool_result':
                    body = p.get('content'); n = len(body if isinstance(body, str) else json.dumps(body)) // 4
                    mix['tool result: ' + names.get(p.get('tool_use_id'), '?')] += n
                elif p.get('type') == 'text':
                    tx = p['text']; key = 'user: system-reminder' if '<system-reminder' in tx else 'user: task-notification' if '<task-notification' in tx else 'user typed'
                    mix[key] += len(tx) // 4
    if fc: first_ctx.append(fc)
tot = sum(mix.values()) + sum(att.values())
print(f'{len(files)} lead transcripts; content written into context ~{tot/1e6:.1f}M tokens (each one is then re-read every later call)')
for k, v in (mix + C.Counter({'attachment: ' + k: v for k, v in att.items()})).most_common(22):
    print(f'  {v/1e3:8.0f}k  {100*v/tot:4.1f}%  {k}')
first_ctx.sort(); agent_brief.sort()
print('first-call context (fixed overhead) median', first_ctx[len(first_ctx)//2] if first_ctx else '-', 'max', first_ctx[-1] if first_ctx else '-')
print('Agent briefs n', len(agent_brief), 'median', agent_brief[len(agent_brief)//2] if agent_brief else '-', 'p90', agent_brief[int(len(agent_brief)*.9)] if agent_brief else '-')
print('tool calls', ntool.most_common(12)); print(dict(reread))
