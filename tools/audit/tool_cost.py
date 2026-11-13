"""Token cost per tool across transcripts: calls, input+result chars (~tokens = chars/4). argv[1] = days (7), argv[2] = project-dir substring (all)."""
import collections as C
import glob
import json
import os
import sys
import time

root = os.path.expanduser('~/.claude/projects')
since = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 7) * 86400
proj = sys.argv[2] if len(sys.argv) > 2 else ''
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_cost import size

calls, inp, out, biggest = C.Counter(), C.Counter(), C.Counter(), {}


def tool_key(name, args):
    if name in ('Bash', 'PowerShell'):
        first = (args.get('command') or '').split()
        return f"{name}:{first[0] if first else ''}"[:40]
    return name


for f in glob.glob(f'{root}/*/**/*.jsonl', recursive=True):
    if proj not in f or os.path.getmtime(f) < since:
        continue
    names = {}
    for line in open(f, encoding='utf8', errors='ignore'):
        try:
            content = (json.loads(line).get('message') or {}).get('content')
        except ValueError:
            continue
        for p in content if isinstance(content, list) else []:
            if not isinstance(p, dict):
                continue
            if p.get('type') == 'tool_use':
                k = tool_key(p.get('name', '?'), p.get('input') or {})
                names[p.get('id')] = k
                calls[k] += 1
                inp[k] += len(json.dumps(p.get('input')))
            elif p.get('type') == 'tool_result':
                k = names.get(p.get('tool_use_id'), '?')
                n = size(p.get('content')) * 4
                out[k] += n
                if n > biggest.get(k, (0,))[0]:
                    biggest[k] = (n, os.path.basename(f)[:8])

total = sum(inp.values()) + sum(out.values())
print(f"{'tool':40} {'calls':>6} {'in_tok':>8} {'out_tok':>9} {'share':>6} {'max_out':>8}")
for k in sorted(calls, key=lambda k: -(inp[k] + out[k]))[:30]:
    print(f"{k:40} {calls[k]:6} {inp[k]//4:8} {out[k]//4:9} {100*(inp[k]+out[k])/max(total,1):5.1f}% {biggest.get(k,(0,))[0]//4:8}")
print(f"total ~{total//4} tokens of tool I/O (each also re-sent every later turn)")
