"""Fit the per-call cost model to transcripts: where $ goes, cache TTL misses, context growth per step.

Usage: python -I cost_model.py [days=14]
Per call cost (input-price units): new + 1.25*write + 0.1*read + 5*out.
Job cost ~= sum over steps of ctx_i, ctx_i ~= c0 + g*i  ->  n*c0 + g*n^2/2 (quadratic in steps).
"""

import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / ".claude/projects"
PRICE = {
    "opus-5-5": (4, 5, 8, 0.20, 20),
    "sonnet-5-5": (2, 2.5, 4, 0.10, 10),
    "haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    "opus-4": (5, 6.25, 10, 0.50, 25),
    "fable-5-1": (10, 12.5, 20, 0.25, 50),
}
TTL = 300


def fam(model: str) -> str:
    """Price key from a model id ($/MTok: input, 5m write, 1h write, read, output)."""
    return next((k for k in PRICE if k in model.lower()), "")


def calls(f: Path) -> list[dict]:
    """Assistant calls of one transcript, deduped by message id."""
    seen, out = set(), []
    for line in f.open(encoding="utf8", errors="ignore"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        m = rec.get("message") or {}
        u = m.get("usage")
        if (
            m.get("role") != "assistant"
            or not u
            or m.get("id") in seen
            or not fam(m.get("model", ""))
        ):
            continue
        seen.add(m.get("id"))
        ts = rec.get("timestamp")
        out.append(
            {
                "fam": fam(m["model"]),
                "t": datetime.fromisoformat(ts).timestamp() if ts else 0,
                "new": u.get("input_tokens", 0),
                "w": u.get("cache_creation_input_tokens", 0),
                "w1h": (u.get("cache_creation") or {}).get(
                    "ephemeral_1h_input_tokens", 0
                ),
                "r": u.get("cache_read_input_tokens", 0),
                "o": u.get("output_tokens", 0),
            }
        )
    return out


def cost_parts(c: dict) -> dict[str, float]:
    """Dollar cost of one call split by token kind."""
    i, w5, w1, r, o = PRICE[c["fam"]]
    return {
        "read": c["r"] * r / 1e6,
        "write": ((c["w"] - c["w1h"]) * w5 + c["w1h"] * w1) / 1e6,
        "new": c["new"] * i / 1e6,
        "out": c["o"] * o / 1e6,
    }


def main() -> None:
    """Print cost split, TTL-miss waste and fitted growth per model and session kind."""
    cutoff = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 14) * 86400
    split: dict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    miss_usd = miss_n = gaps = 0.0
    s1h = [0, 0]
    fits: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    for f in ROOT.glob("*/**/*.jsonl"):
        if f.stat().st_mtime < cutoff:
            continue
        cs = calls(f)
        if not cs:
            continue
        kind = "sub" if "subagents" in f.parts else "main"
        for i, c in enumerate(cs):
            s = split[f"{kind}:{c['fam']}"]
            for k, v in cost_parts(c).items():
                s[k] += v
            s["calls"] += 1
            if i and c["t"] - cs[i - 1]["t"] > TTL:
                gaps += 1
                if c["w"] > 0.5 * (c["w"] + c["r"]):
                    miss_n += 1
                    _, w5, w1, r, _ = PRICE[c["fam"]]
                    miss_usd += c["w"] * ((w1 if c["w1h"] else w5) - r) / 1e6
                    s1h[c["w1h"] > 0] += 1
        ctx = [c["new"] + c["w"] + c["r"] for c in cs]
        if len(ctx) >= 5:
            g = (ctx[-1] - ctx[0]) / (len(ctx) - 1)
            fits[f"{kind}:{cs[0]['fam']}"].append((ctx[0], g, len(ctx)))
    print("cost split ($, share of that bucket)")
    grand = sum(v for s in split.values() for k, v in s.items() if k != "calls")
    for k, s in sorted(
        split.items(), key=lambda kv: -sum(v for x, v in kv[1].items() if x != "calls")
    ):
        tot = sum(v for x, v in s.items() if x != "calls")
        parts = "  ".join(
            f"{x}={100 * s[x] / tot:3.0f}%" for x in ("read", "write", "new", "out")
        )
        print(
            f"{k:12} ${tot:8.0f} ({100 * tot / grand:3.0f}% of all)  calls={int(s['calls']):6}  {parts}"
        )
    print(f"total ${grand:.0f}")
    print(
        f"\nidle gaps >{TTL}s: {int(gaps)}; followed by cache rebuild: {int(miss_n)}; extra $ vs cached read: ${miss_usd:.0f} (5m={s1h[0]} 1h={s1h[1]})"
    )
    print(
        "\nfitted ctx_i = c0 + g*i  (medians)  -> n* = steps where growth cost equals start cost (2*c0/g)"
    )
    for k, rows in sorted(fits.items()):
        c0 = statistics.median(r[0] for r in rows)
        g = statistics.median(r[1] for r in rows)
        n = statistics.median(r[2] for r in rows)
        star = 2 * c0 / g if g > 0 else float("inf")
        print(
            f"{k:12} n={len(rows):5} c0={c0:7.0f} g={g:6.0f} tok/step  median calls={n:5.0f}  n*={star:6.0f}"
        )


if __name__ == "__main__":
    main()
