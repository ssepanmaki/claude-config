"""Size path overhead in Claude Code transcripts: long-path chars in tool inputs and path-not-found failures.

Usage: python -I path_cost.py <days> [project_dir_name]
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
LONG = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+OMISTAJA[\\/]+AppData[\\/]+Local[\\/]+Temp[\\/]+claude[\\/]+[^\s\"'`]+", re.IGNORECASE)
ABS = re.compile(r"(?:[A-Za-z]:[\\/]|~/|/c/)[^\s\"'`<>|]{20,}")
MISS = re.compile(r"does not exist|no such file|cannot find the path|not found|ENOENT|FileNotFoundError|can't open file", re.IGNORECASE)


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return ""


def main() -> None:
    days = float(sys.argv[1]) if len(sys.argv) > 1 else 7
    base = ROOT / sys.argv[2] if len(sys.argv) > 2 else ROOT
    cutoff = time.time() - days * 86400
    calls = long_calls = long_chars = abs_chars = 0
    fails = long_fails = 0
    fail_tools: Counter[str] = Counter()
    files = [p for p in base.rglob("*.jsonl") if p.stat().st_mtime >= cutoff]
    for f in files:
        pending: dict[str, tuple[str, str]] = {}
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    s = json.dumps(c.get("input", {}), ensure_ascii=False).replace("\\\\", "\\")
                    calls += 1
                    hits = LONG.findall(s)
                    if hits:
                        long_calls += 1
                        long_chars += sum(map(len, hits))
                    abs_chars += sum(map(len, ABS.findall(s)))
                    pending[c.get("id", "")] = (c.get("name", ""), s)
                elif c.get("type") == "tool_result":
                    name, s = pending.pop(c.get("tool_use_id", ""), ("", ""))
                    if c.get("is_error") and MISS.search(text_of(c.get("content"))[:600]):
                        fails += 1
                        fail_tools[name] += 1
                        if LONG.search(s):
                            long_fails += 1
    print(f"transcripts={len(files)} days={days}")
    print(f"tool_calls={calls} with_temp_path={long_calls} temp_path_chars={long_chars} (~{long_chars // 3} tok)")
    print(f"all_abs_path_chars={abs_chars} (~{abs_chars // 3} tok)")
    print(f"path_not_found_fails={fails} on_temp_path={long_fails} by_tool={dict(fail_tools.most_common(6))}")


if __name__ == "__main__":
    main()
