"""Rank Read tool output by file kind and by repeat reads.

Usage: python -I read_cost.py <days> [project_dir_name]
"""

from __future__ import annotations

import base64
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"


def image_tok(data: str) -> int:
    """Billed image tokens = w*h/750, capped at ~1600 (API downscales to ~1.15MP)."""
    try:
        head = base64.b64decode(data[:64])
    except ValueError:
        return 1600
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        return min(1600, w * h // 750)
    return 1600


def size(content) -> int:
    if isinstance(content, str):
        return len(content) // 4
    total = 0
    for c in content or []:
        if isinstance(c, dict) and c.get("type") == "image":
            total += image_tok(c.get("source", {}).get("data", ""))
        elif isinstance(c, dict):
            total += len(c.get("text", "")) // 4
    return total


def main() -> None:
    days = float(sys.argv[1]) if len(sys.argv) > 1 else 7
    base = ROOT / sys.argv[2] if len(sys.argv) > 2 else ROOT
    cutoff = time.time() - days * 86400
    by_ext: Counter[str] = Counter()
    n_ext: Counter[str] = Counter()
    repeats = repeat_tok = 0
    for f in base.rglob("*.jsonl"):
        if f.stat().st_mtime < cutoff:
            continue
        pending: dict[str, str] = {}
        seen: set[str] = set()
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                content = (json.loads(line).get("message") or {}).get("content")
            except ValueError:
                continue
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use" and c.get("name") == "Read":
                    pending[c.get("id", "")] = json.dumps(c.get("input", {}), sort_keys=True)
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                    key = pending.pop(c["tool_use_id"])
                    path = json.loads(key).get("file_path", "")
                    ext = Path(path).suffix.lower() or "(none)"
                    tok = size(c.get("content"))
                    by_ext[ext] += tok
                    n_ext[ext] += 1
                    if key in seen:
                        repeats += 1
                        repeat_tok += tok
                    seen.add(key)
    total = sum(by_ext.values())
    print(f"read_tok~{total} repeat_reads={repeats} repeat_tok~{repeat_tok}")
    for ext, tok in by_ext.most_common(10):
        print(f"{ext:8} n={n_ext[ext]:5} tok~{tok:9} {tok * 100 // max(total, 1)}%")


if __name__ == "__main__":
    main()
