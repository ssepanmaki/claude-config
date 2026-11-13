"""What is inside the 7-day cost: waste patterns per lead session + cross-session Bash/read/retry/Opus-lead breakdown.
usage: python -I week_inside.py [days=7] [top=8]"""
import json, glob, os, sys, time, re, collections as C
root = os.path.expanduser('~/.claude/projects'); days = float(sys.argv[1]) if len(sys.argv) > 1 else 7
top = int(sys.argv[2]) if len(sys.argv) > 2 else 8
since = time.time() - days * 86400; cut = time.strftime('%Y-%m-%d', time.gmtime(since))
P = {'opus': (4.0, 0.20, 20.0), 'sonnet': (2.0, 0.10, 10.0), 'haiku': (0.10, 0.01, 0.50)}
def fam(m): return next((k for k in P if k in (m or '')), 'other')
def cost(u, f):
    pi, pc, po = P.get(f, P['sonnet'])
    return (u.get('input_tokens', 0) * pi + u.get('cache_creation_input_tokens', 0) * pi * 1.25 + u.get('cache_read_input_tokens', 0) * pc + u.get('output_tokens', 0) * po) / 1e6
def size(x): return len(x) if isinstance(x, str) else sum(len(q.get('text', '')) for q in x if isinstance(q, dict)) if isinstance(x, list) else 0
def txt(c): return c if isinstance(c, str) else ''.join(p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text') if isinstance(c, list) else ''
def bashkey(cmd):
    cmd = cmd.strip(); w = re.split(r'\s+', cmd)
    if w[0] in ('cd', 'export') and '&&' in cmd: w = re.split(r'\s+', cmd.split('&&', 1)[1].strip())
    k = w[0]
    return (k + ' ' + w[1]) if k in ('git', 'npm', 'gh', 'python', 'py', 'node', 'npx', 'attc-codebus') and len(w) > 1 else k
BK = C.defaultdict(lambda: [0, 0.0]); S = []; bash =C.defaultdict(lambda: [0, 0]); opus_lead = C.defaultdict(lambda: [0, 0.0]); all_ret = C.Counter()
for f in glob.glob(f'{root}/*/**/*.jsonl', recursive=True):
    if os.path.getmtime(f) < since or os.sep + 'subagents' + os.sep in f: continue
    pj = re.sub(r'^C--Users-OMISTAJA-?', '', f.split(os.sep)[-2])[:22] or 'home'
    names = {}; seen = set(); st = dict(f=os.path.basename(f)[:8], pj=pj, calls=0, cost=0.0, peak=0, first='', model=C.Counter(), comp=0,
         typed=0, wake=0, hookerr=0, nudge=0, stopblk=0, errs=0, ret=0, big=[], reads=C.Counter(), calls_by=C.Counter(), edits=0, agents=0, cost_by_tool=C.Counter(), prev=None)
    last_call = None; prev_err = False; prev_sig = None
    for line in open(f, encoding='utf8', errors='ignore'):
        if 'compact_boundary' in line: st['comp'] += 1
        if 'hook error' in line: st['hookerr'] += 1
        if 'recon calls' in line or "hasn't heard from you" in line: st['nudge'] += 1
        if 'Stop hook' in line: st['stopblk'] += 1
        if '"type":"assistant"' not in line and '"type":"user"' not in line: continue
        try: j = json.loads(line)
        except Exception: continue
        m = j.get('message') or {}; c = m.get('content'); ts = (j.get('timestamp') or '')[:10]
        if j.get('type') == 'user':
            if isinstance(c, list):
                for p in c:
                    if isinstance(p, dict) and p.get('type') == 'tool_result':
                        n = names.get(p.get('tool_use_id'), ('?', ''))
                        L = size(p.get('content')) // 4
                        if ts >= cut:
                            if n[0] == 'Bash': bash[bashkey(n[1])][0] += 1; bash[bashkey(n[1])][1] += L
                            st['big'].append((L, n[0], n[1][:90]))
                        if p.get('is_error'): st['errs'] += 1; prev_err = True
            t = txt(c).strip()
            if t and not j.get('isMeta') and ts >= cut:
                if not st['first'] and not t.startswith('<'): st['first'] = t[:110].replace('\n', ' ')
                if '<task-notification' in t or 'side-sessions-event' in t or '<agent-message' in t or 'Subagent hand-back' in t: st['wake'] += 1
                elif not t.startswith('<'): st['typed'] += 1
            continue
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get('type') == 'tool_use':
                    i = p.get('input') or {}; nm = p.get('name')
                    arg = i.get('command') or i.get('file_path') or i.get('pattern') or i.get('prompt') or i.get('description') or ''
                    names[p.get('id')] = (nm, str(arg))
                    if ts < cut: continue
                    st['calls_by'][nm] += 1
                    if nm == 'Read': st['reads'][i.get('file_path')] += 1
                    if nm in ('Edit', 'Write'): st['edits'] += 1
                    if nm == 'Agent': st['agents'] += 1
                    sig = (nm, str(arg)[:200])
                    if prev_err and sig == prev_sig: st['ret'] += 1
                    prev_sig = sig; prev_err = False
        if ts < cut or not m.get('usage'): continue
        mid = (m.get('id') or '') + (j.get('requestId') or '')
        if mid in seen: continue
        seen.add(mid); u = m['usage']; fm = fam(m.get('model')); n = u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('input_tokens', 0)
        cc = cost(u, fm); b = '<50k' if n < 50e3 else '50-100k' if n < 100e3 else '100-150k' if n < 150e3 else '150k+'; BK[b][0] += 1; BK[b][1] += cc; st['calls'] += 1; st['cost'] += cc; st['peak'] = max(st['peak'], n); st['model'][fm] += 1
        if fm == 'opus': opus_lead[pj][0] += 1; opus_lead[pj][1] += cc
    if st['calls']: S.append(st)
S.sort(key=lambda s: -s['cost'])
tot = sum(s['cost'] for s in S)
print(f'lead sessions {len(S)}, lead cost ${tot:,.0f}; top {top} = ${sum(s["cost"] for s in S[:top]):,.0f}')
for s in S[:top]:
    rd = [(k, v) for k, v in s['reads'].most_common(3) if v > 2]
    print(f"\n## {s['pj']} {s['f']} ${s['cost']:.0f} calls {s['calls']} peak {s['peak'] // 1000}k models {dict(s['model'])}")
    print(f"   task: {s['first']}")
    print(f"   typed {s['typed']} wakeups {s['wake']} compactions {s['comp']} | errs {s['errs']} same-call retries {s['ret']} | hook errs {s['hookerr']} nudges {s['nudge']} stop blocks {s['stopblk']}")
    print(f"   calls: {dict(s['calls_by'].most_common(6))} edits {s['edits']} agents {s['agents']}")
    if rd: print('   re-read x3+:', [(os.path.basename(str(k)), v) for k, v in rd])
    for L, n, a in sorted(s['big'], reverse=True)[:3]: print(f'   big result {L // 1000}k {n}: {a}')
print('\n== Bash by command (lead, ~tokens returned, n):')
for k, v in sorted(bash.items(), key=lambda x: -x[1][1])[:14]: print(f'  {k:26} {v[1] // 1000:6}k n={v[0]:5} avg {v[1] // max(v[0], 1)}')
print('\n== Opus lead $ by project:')
for k, v in sorted(opus_lead.items(), key=lambda x: -x[1][1])[:6]: print(f'  {k:22} calls {v[0]:5} ${v[1]:.0f}')
print('\n== lead cost by context size:', {k: (v[0], round(v[1])) for k, v in BK.items()})
T = C.Counter()
for s_ in S: T.update(s_['calls_by'])
print('== lead calls by tool:', dict(T.most_common(12)))
print('\n== totals: errs', sum(s['errs'] for s in S), 'same-call retries', sum(s['ret'] for s in S), 'compactions', sum(s['comp'] for s in S),
      'wakeups', sum(s['wake'] for s in S), 'typed', sum(s['typed'] for s in S), 'edits', sum(s['edits'] for s in S), 'calls', sum(s['calls'] for s in S))
