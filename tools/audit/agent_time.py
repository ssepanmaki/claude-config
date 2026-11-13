"""Where a session tree's wall time goes: model time vs tool time, by tool and by command head.

Usage: python -I agent_time.py <transcript_id or prefix> [...]   (searched across ~/.claude/projects/*)

Tool time = tool_use record -> its tool_result. Model time = previous record -> assistant record.
Gaps over IDLE_S are counted as idle (waiting on the user, a background agent, or a stalled box).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IDLE_S = 900
HEAD = re.compile(r"(?:cd \S+ (?:&&|;) )?\s*((?:npx |npm run |python -I |python |node )?\S+(?: \S+)?)")


def ts(rec: dict) -> float | None:
    raw = rec.get("timestamp")
    try:
        return datetime.fromisoformat(str(raw)).timestamp() if raw else None
    except ValueError:
        return None


def label(use: dict) -> str:
    name = str(use.get("name") or "")
    params = use.get("input") or {}
    if name in ("Bash", "PowerShell"):
        m = HEAD.match(str(params.get("command") or ""))
        return f"Bash: {m.group(1)[:40] if m else '?'}"
    if name == "Agent":
        return f"Agent({params.get('subagent_type') or 'general'})"
    return name


def scan(path: Path, tools: dict, totals: dict) -> None:
    pending: dict[str, tuple[float, str]] = {}
    prev: float | None = None
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = ts(rec)
        if t is None:
            continue
        content = (rec.get("message") or {}).get("content") if isinstance(rec.get("message"), dict) else None
        blocks = [b for b in content or [] if isinstance(b, dict)] if isinstance(content, list) else []
        if rec.get("type") == "assistant" and prev is not None:
            gap = t - prev
            totals["idle" if gap > IDLE_S else "model"] += max(gap, 0)
        for b in blocks:
            if b.get("type") == "tool_use":
                pending[str(b.get("id"))] = (t, label(b))
            elif b.get("type") == "tool_result" and str(b.get("tool_use_id")) in pending:
                start, name = pending.pop(str(b.get("tool_use_id")))
                dur = max(t - start, 0)
                if name.startswith("Agent"):
                    totals["waiting on agents"] += dur
                else:
                    totals["tools"] += dur
                tools[name][0] += 1
                tools[name].append(dur)
                tools[name][1] += dur
        prev = t


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    projects = Path.home() / ".claude" / "projects"
    for scope in ("lead", "agents"):
        tools: dict[str, list] = defaultdict(lambda: [0, 0.0])
        totals: dict[str, float] = defaultdict(float)
        for sid in sys.argv[1:]:
            for main_file in sorted(projects.glob(f"*/{sid}*.jsonl")):
                files = [main_file] if scope == "lead" else sorted((main_file.parent / main_file.stem / "subagents").glob("*.jsonl"))
                for f in files:
                    scan(f, tools, totals)
        print(f"== {scope}: " + ", ".join(f"{k} {v / 60:.0f} min" for k, v in sorted(totals.items(), key=lambda kv: -kv[1])))
        for name, (n, dur, *ds) in sorted(tools.items(), key=lambda kv: -kv[1][1])[:15]:
            print(f"  {name:48} {n:>5} calls {dur / 60:>7.1f} min  avg {dur / max(n, 1):>6.1f} s  median {sorted(ds)[len(ds) // 2]:>5.1f} s")


if __name__ == "__main__":
    main()
