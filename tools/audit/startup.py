"""First-turn context, Bash ToolSearch loads, tool-use counts, costliest transcripts (7 days, main sessions only)."""

import json
import re
import statistics
import time
from collections import Counter
from pathlib import Path

ROOT = Path.home() / ".claude/projects"
cutoff = time.time() - 7 * 86400
WATCH = re.compile(
    r"SendToProject|FetchInboxMessage|DesignSync|ArtifactData|ReportFindings|mcp__visualize__|"
    r"mcp__mcp-registry__|mcp__ccd_sidebar__|mcp__ccd_window__|mcp__1a59c906"
)
first, cost = [], []
bash_load = sessions = 0
uses: Counter[str] = Counter()
doc_sessions = 0
for f in ROOT.glob("*/*.jsonl"):
    if f.stat().st_mtime < cutoff:
        continue
    ft = None
    total = 0
    loaded = docs = False
    with f.open(encoding="utf8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line).get("message") or {}
            except ValueError:
                continue
            u = m.get("usage")
            if u:
                ctx = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                total += ctx
                if ft is None:
                    ft = ctx
            c = m.get("content")
            for p in c if isinstance(c, list) else []:
                if isinstance(p, dict) and p.get("type") == "tool_use":
                    n = p.get("name", "")
                    if n == "ToolSearch" and "Bash" in json.dumps(p.get("input")):
                        loaded = True
                    w = WATCH.search(n)
                    if w:
                        uses[n] += 1
                        docs |= n.startswith("mcp__1a59c906")
    if ft:
        sessions += 1
        first.append(ft)
        bash_load += loaded
        doc_sessions += docs
        cost.append((total, f.parent.name[-30:], f.stem))
print(f"sessions={sessions} first_turn median={statistics.median(first):.0f} p90={sorted(first)[int(len(first) * .9)]}")
print(f"sessions loading Bash via ToolSearch={bash_load} ({100 * bash_load // max(sessions, 1)}%)")
print(f"sessions using docs MCP={doc_sessions}")
print("watched tool uses:", dict(uses.most_common()))
for t, p, s in sorted(cost, reverse=True)[:3]:
    print(f"costly {t} {p} {s}")
