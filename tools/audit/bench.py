"""Bench Claude Code settings: runs `claude -p` per variant N times, prints a cost table.
argv[1] = runs per variant (2), argv[2] = variant-name substring filter (all). Writes bench.jsonl next to cwd."""
import concurrent.futures as F
import json
import os
import pathlib
import subprocess
import sys
import tempfile

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
PICK = sys.argv[2] if len(sys.argv) > 2 else ''
SAY = 'Reply with exactly: ok'
TASK = 'Read n.txt, multiply the number by 2, reply with only the result.'
BIG = 'Run `seq 1 40000` with Bash and reply with only the last line it printed.'
SUB = 'Use the Agent tool (subagent_type={a}) to read n.txt; reply with only the number.'

# name, prompt, extra flags, extra env, expected substring
V = [
    ('base:say', SAY, [], {}, 'ok'),
    ('base:task', TASK, [], {}, '84'),
    ('deny-more', TASK, ['--disallowedTools', 'ShowOnboardingRolePicker,SearchMcpRegistry,SuggestConnectors,ListConnectors,ListPlugins,ListSkills,SearchSkills'], {}, '84'),
    ('hooks-off', TASK, ['--settings', '{"disableAllHooks":true}'], {}, '84'),
    ('toolsearch-off', TASK, [], {'ENABLE_TOOL_SEARCH': 'false'}, '84'),
    ('tools-min', TASK, ['--tools', 'Read'], {}, '84'),
    ('no-skills', TASK, ['--disable-slash-commands'], {}, '84'),
    ('no-user-settings', TASK, ['--setting-sources', 'project,local'], {}, '84'),
    ('bare', TASK, ['--bare'], {}, '84'),
    ('no-dynamic-sys', TASK, ['--exclude-dynamic-system-prompt-sections'], {}, '84'),
    ('style-default', TASK, ['--settings', '{"outputStyle":"default"}'], {}, '84'),
    ('model-haiku', TASK, ['--model', 'haiku'], {}, '84'),
    ('model-opus', TASK, ['--model', 'opus'], {}, '84'),
    ('effort-low', TASK, ['--effort', 'low'], {}, '84'),
    ('effort-high', TASK, ['--effort', 'high'], {}, '84'),
    ('perm-bypass', TASK, ['--permission-mode', 'bypassPermissions'], {}, '84'),
    ('bash-big', BIG, [], {}, '40000'),
    ('bash-big-cap4k', BIG, [], {'BASH_MAX_OUTPUT_LENGTH': '4000'}, '40000'),
    ('sub-general', SUB.format(a='general-purpose'), [], {}, '42'),
    ('sub-scout', SUB.format(a='scout'), [], {}, '42'),
]


def run(v, i):
    name, prompt, flags, env, want = v
    d = tempfile.mkdtemp()
    pathlib.Path(f'{d}/n.txt').write_text('42\n')
    cmd = ['claude', '-p', prompt, '--output-format', 'json', '--max-budget-usd', '0.5',
           '--no-session-persistence', '--permission-mode', 'acceptEdits', *flags]
    try:
        p = subprocess.run(cmd, cwd=d, env={**os.environ, **env}, capture_output=True, text=True, timeout=300, check=False)
        j = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {'v': name, 'i': i, 'err': str(e)[:80]}
    mu = j.get('modelUsage') or {}
    return {'v': name, 'i': i, 'ok': want in str(j.get('result', '')), 'usd': j.get('total_cost_usd', 0),
            'in': sum(m.get('inputTokens', 0) + m.get('cacheReadInputTokens', 0) + m.get('cacheCreationInputTokens', 0) for m in mu.values()),
            'write': sum(m.get('cacheCreationInputTokens', 0) for m in mu.values()),
            'out': sum(m.get('outputTokens', 0) for m in mu.values()), 'turns': j.get('num_turns'),
            'models': ','.join(k.split('-')[1] for k in mu)}


def avg(rs, k):
    return sum(r[k] or 0 for r in rs) / len(rs)


jobs = [(v, i) for v in V if PICK in v[0] for i in range(N)]
with F.ThreadPoolExecutor(4) as ex, open('bench.jsonl', 'a') as log:
    rows = list(ex.map(lambda a: run(*a), jobs))
    log.writelines(json.dumps(r) + '\n' for r in rows)
agg = {}
for r in rows:
    agg.setdefault(r['v'], []).append(r)
print(f"{'variant':18} {'ok':>4} {'usd':>7} {'in_tok':>7} {'write':>6} {'out':>5} {'turns':>5} models")
for name, rs in agg.items():
    good = [r for r in rs if 'err' not in r]
    if not good:
        print(f'{name:18} ERR {rs[0]["err"]}')
        continue
    print(f"{name:18} {sum(r['ok'] for r in good)}/{len(rs)} {avg(good, 'usd'):7.4f} {avg(good, 'in'):7.0f} {avg(good, 'write'):6.0f} {avg(good, 'out'):5.0f} {avg(good, 'turns'):5.1f} {good[0]['models']}")
