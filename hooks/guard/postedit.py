"""PostToolUse Edit|Write|MultiEdit: ruff --fix on .py, block with remaining lint. `python -I postedit.py`."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common

MID_CHANGE = re.compile(r"\b(F821|F401|F841)\b")
RUFF_TIMEOUT_S = 30
FINDING = re.compile(r":\d+:\d+: [A-Z]+\d+ ")


def blocking_lint(left: list[str]) -> list[str]:
    """Findings worth blocking an edit for: undefined/unused names are what the next edit resolves."""
    return [line for line in left if not MID_CHANGE.search(line)]


def _ruff(args: list[str]) -> str:
    exe = shutil.which("ruff")
    if exe is None:
        return ""
    try:
        done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=RUFF_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def lint_reason(path: str) -> str:
    if not path.endswith(".py") or not os.path.isfile(path) or shutil.which("ruff") is None:
        return ""
    _ruff(["check", "--fix", "--quiet", path])
    out = _ruff(["check", "--output-format=concise", "--no-fix", "--quiet", path])
    left = blocking_lint([ln for ln in out.splitlines() if FINDING.search(ln)])
    return "ruff findings remain:\n" + "\n".join(left[:20]) if left else ""


def main() -> None:
    event = common.read_events()
    if event.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return
    path = str((event.get("tool_input") or {}).get("file_path") or "")
    reason = lint_reason(path)
    if reason:
        common.emit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    main()
