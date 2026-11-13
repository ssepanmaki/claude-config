"""Cost of one session tree: the main transcript plus its subagents, for each session id given.

Usage: python -I session_cost.py <transcript_id or prefix> [...]   (searched across ~/.claude/projects/*)

One API message is logged as several JSONL records (one per content block) sharing message.id;
usage is counted once per id (last record wins). Cache writes are priced by TTL: 5m = 1.25x input, 1h = 2x.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# USD per MTok: input, output, cache read. Writes derive from input.
PRICES = {
    "fable-5-1": (10.0, 50.0, 0.25),
    "opus-5-5": (4.0, 20.0, 0.20),
    "opus": (5.0, 25.0, 0.50),
    "sonnet-5-5": (2.0, 10.0, 0.10),
    "sonnet": (3.0, 15.0, 0.30),
    "haiku-5-5": (0.10, 0.50, 0.01),
    "haiku": (1.0, 5.0, 0.10),
}
FIELDS = ("input", "read", "write5m", "write1h", "output")


def tier(model: str) -> str:
    return next((t for t in PRICES if t in model), "opus")


def usage_by_message(path: Path) -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        msg = rec.get("message")
        if rec.get("type") != "assistant" or not isinstance(msg, dict) or not msg.get("usage"):
            continue
        out[str(msg.get("id") or rec.get("uuid"))] = (str(msg.get("model") or ""), msg["usage"])
    return out


def tokens(u: dict) -> dict[str, int]:
    split = u.get("cache_creation") or {}
    w1h = split.get("ephemeral_1h_input_tokens", 0) or 0
    w5m = split.get("ephemeral_5m_input_tokens", (u.get("cache_creation_input_tokens") or 0) - w1h) or 0
    return {
        "input": u.get("input_tokens") or 0,
        "read": u.get("cache_read_input_tokens") or 0,
        "write5m": w5m,
        "write1h": w1h,
        "output": u.get("output_tokens") or 0,
    }


def usd(model: str, t: dict[str, int]) -> float:
    inp, out, read = PRICES[tier(model)]
    return (t["input"] * inp + t["read"] * read + t["write5m"] * inp * 1.25 + t["write1h"] * inp * 2 + t["output"] * out) / 1e6


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    projects = Path.home() / ".claude" / "projects"
    rows: dict[str, dict] = defaultdict(lambda: {**dict.fromkeys(FIELDS, 0), "usd": 0.0, "msgs": 0})
    for sid in sys.argv[1:]:
        mains = sorted(projects.glob(f"*/{sid}*.jsonl"))
        files = [f for m in mains for f in (m, *sorted((m.parent / m.stem / "subagents").glob("*.jsonl")))]
        for f in files:
            label = f"{sid[:8]} {'lead' if f in mains else 'agents'}"
            for model, u in usage_by_message(f).values():
                t = tokens(u)
                for key in (label, f"{label} {tier(model)}", "TOTAL"):
                    row = rows[key]
                    for k in FIELDS:
                        row[k] += t[k]
                    row["usd"] += usd(model, t)
                    row["msgs"] += 1
    print(f"{'group':28} {'msgs':>6} {'input':>9} {'read':>12} {'write5m':>11} {'write1h':>11} {'output':>10} {'usd':>9}")
    for key in sorted(rows, key=lambda k: (k == "TOTAL", k)):
        r = rows[key]
        print(f"{key:28} {r['msgs']:>6} {r['input']:>9} {r['read']:>12} {r['write5m']:>11} {r['write1h']:>11} {r['output']:>10} {r['usd']:>9.2f}")


if __name__ == "__main__":
    main()
