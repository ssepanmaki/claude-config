"""Context window of a session from its transcript, like the app's get_usage context block.

Usage: python -I ctx.py [transcript_id or prefix]   (default: newest main transcript)

Context = input + cache read + cache write of the last main-chain API call.
Baseline = the same sum on the first call (system prompt, tools, skills, memory, first message);
messages = context - baseline. The app's finer split (system tools vs MCP tools vs skills) is not
in the transcript, so it is not reproduced. Plan limits come from the account API and are not here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from session_cost import tokens, usage_by_message, usd

ROOT = Path.home() / ".claude/projects"


def find(prefix: str | None) -> Path:
    files = [f for f in ROOT.glob("*/*.jsonl") if prefix is None or f.stem.startswith(prefix)]
    if not files:
        sys.exit(f"no transcript matches {prefix}")
    return max(files, key=lambda f: f.stat().st_mtime)


def window(path: Path) -> list[int]:
    sizes: dict[str, int] = {}
    with path.open(encoding="utf8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            if rec.get("type") != "assistant" or rec.get("isSidechain") or not usage:
                continue
            sizes[msg.get("id", "")] = (
                usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
            )
    return list(sizes.values())


def main() -> None:
    path = find(sys.argv[1] if len(sys.argv) > 1 else None)
    sizes = window(path)
    if not sizes:
        sys.exit(f"no usage records in {path.name}")
    now, base = sizes[-1], sizes[0]
    print(f"{path.stem}  calls {len(sizes)}  peak {max(sizes):,}")
    print(f"context  {now:,}")
    print(f"baseline {base:,}  ({base / now:.0%})")
    print(f"messages {now - base:,}  ({(now - base) / now:.0%})")
    print_cost(path)


def print_cost(path: Path) -> None:
    agents = sorted((path.parent / path.stem / "subagents").glob("*.jsonl"))
    total = 0.0
    for label, files in (("lead", [path]), (f"agents ({len(agents)})", agents)):
        spent = sum(usd(m, tokens(u)) for f in files for m, u in usage_by_message(f).values())
        total += spent
        print(f"cost {label:12} ${spent:,.2f}")
    print(f"cost {'total':12} ${total:,.2f}  (API list price; plan billing differs)")


if __name__ == "__main__":
    main()
