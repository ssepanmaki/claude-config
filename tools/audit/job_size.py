"""Subagent job size by model: steps, tokens, peak context, and failure rate per size bucket.

Usage: python -I job_size.py [days=14]
Failure = handback says done:false / not done / blocked, or the agent ended on a tool error.
"""

import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / ".claude/projects"
FAIL = re.compile(r'"done"\s*:\s*false|^\W*(?:blocked|not done|could not|couldn.t|stopped)\b', re.IGNORECASE)
PRICE = {"haiku": 1, "sonnet": 3, "opus": 5, "fable": 5}
BUCKETS = (5, 10, 15, 20, 30, 50, 10**9)


def scan(f: Path) -> dict | None:
    """One subagent transcript -> size and outcome."""
    meta = f.with_suffix(".meta.json")
    try:
        info = json.loads(meta.read_text(encoding="utf8"))
    except (OSError, ValueError):
        info = {}
    steps = turns = out = cost = peak = brief = errs = 0
    eff = 0.0
    model, last, last_err = "", "", False
    for line in f.open(encoding="utf8", errors="ignore"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        m = rec.get("message") or {}
        c = m.get("content")
        if rec.get("type") == "user" and not brief:
            brief = len(c) if isinstance(c, str) else len(json.dumps(c))
        if m.get("role") == "assistant":
            model = model or m.get("model", "")
            u = m.get("usage") or {}
            ctx = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            turns += 1
            cost += ctx
            out += u.get("output_tokens", 0)
            eff += u.get("input_tokens", 0) + 1.25 * u.get("cache_creation_input_tokens", 0) + 0.1 * u.get("cache_read_input_tokens", 0) + 5 * u.get("output_tokens", 0)
            peak = max(peak, ctx)
        for p in c if isinstance(c, list) else []:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "tool_use":
                steps += 1
                if p.get("name") == "StructuredOutput" or p.get("name") == "SubagentHandback":
                    last = json.dumps(p.get("input"))
            elif p.get("type") == "tool_result":
                last_err = bool(p.get("is_error"))
                errs += last_err
            elif p.get("type") == "text" and m.get("role") == "assistant":
                last = p.get("text", "") or last
    if not turns:
        return None
    fam = next((k for k in ("haiku", "sonnet", "opus", "fable") if k in (model + info.get("model", "")).lower()), "other")
    return {
        "model": fam, "type": info.get("agentType", "?"), "steps": steps, "turns": turns, "out": out,
        "cost": cost, "usd": eff * PRICE.get(fam, 3) / 1e6, "peak": peak, "brief": brief, "errs": errs, "fail": bool(FAIL.search(last)) or last_err,
    }


def pct(xs: list[int], q: float) -> int:
    """Quantile of a non-empty list."""
    return sorted(xs)[min(len(xs) - 1, int(len(xs) * q))]


def main() -> None:
    """Print per-model size distribution and failure rate by step bucket."""
    cutoff = time.time() - float(sys.argv[1] if len(sys.argv) > 1 else 14) * 86400
    rows = [r for f in ROOT.glob("*/*/subagents/**/agent-*.jsonl") if f.stat().st_mtime >= cutoff and (r := scan(f))]
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["model"]].append(r)
    print(f"agents={len(rows)}")
    print("model   n    steps p50/p90  peakctx p50/p90   tok/job p50/p90      fail%")
    for k, rs in sorted(by.items()):
        s, pk, c = [r["steps"] for r in rs], [r["peak"] for r in rs], [r["cost"] for r in rs]
        fr = 100 * sum(r["fail"] for r in rs) / len(rs)
        print(f"{k:7} {len(rs):4} {pct(s, .5):5}/{pct(s, .9):<5} {pct(pk, .5):7}/{pct(pk, .9):<8} {pct(c, .5):9}/{pct(c, .9):<10} {fr:5.1f}")
    print("\nfail% by steps bucket (n)")
    print("model   " + "".join(f"{'<=' + str(b) if b < 10**9 else '>50':>12}" for b in BUCKETS))
    for k, rs in sorted(by.items()):
        cells, lo = [], 0
        for b in BUCKETS:
            sub = [r for r in rs if lo < r["steps"] <= b] if lo else [r for r in rs if r["steps"] <= b]
            cells.append(f"{100 * sum(r['fail'] for r in sub) / len(sub):5.0f}% ({len(sub):3})" if sub else f"{'-':>12}")
            lo = b
        print(f"{k:7} " + "".join(f"{x:>12}" for x in cells))
    print("\n$ per job (cache-weighted: read 0.1x, write 1.25x, output 5x; input $/M haiku 1, sonnet 3, opus 5)")
    for k, rs in sorted(by.items()):
        tot = sum(r["usd"] for r in rs)
        for lo, hi in ((0, 15), (15, 30), (30, 60), (60, 120), (120, 10**9)):
            sub = [r["usd"] for r in rs if lo < r["steps"] <= hi]
            if sub:
                print(f"{k:7} steps {lo + 1:>3}-{hi if hi < 10**9 else '+':<4} n={len(sub):4} $/job p50={statistics.median(sub):6.2f} share={100 * sum(sub) / tot:4.0f}%")
        print(f"{k:7} total=${tot:8.2f}")
    print("\nfail% by peak context (n)")
    for k, rs in sorted(by.items()):
        cells, lo = [], -1
        for b in (40_000, 80_000, 120_000, 160_000, 10**9):
            sub = [r for r in rs if lo < r["peak"] <= b]
            cells.append(f"<={b // 1000}k {100 * sum(r['fail'] for r in sub) / len(sub):3.0f}% ({len(sub)})" if sub else "-")
            lo = b
        print(f"{k:7} " + "  ".join(cells))
    print("\ntok/step and steps-per-1k-brief-chars, by model")
    for k, rs in sorted(by.items()):
        tps = statistics.median(r["cost"] / max(r["steps"], 1) for r in rs)
        spb = statistics.median(r["steps"] / max(r["brief"] / 1000, 0.1) for r in rs)
        print(f"{k:7} tok/step={tps:8.0f}  steps/1k-brief={spb:5.1f}")


if __name__ == "__main__":
    main()
