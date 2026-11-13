"""SessionStart hook: per-session work dir <home>/<repo>/.tmp/<sid8>, exported as $T, old siblings pruned."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

MAX_AGE = 3 * 86400


def repo_root(cwd: Path) -> Path:
    for p in (cwd, *cwd.parents):
        if (p / ".git").exists():
            return p
    return cwd


def prune(tmp: Path, keep: Path, now: float) -> None:
    for d in tmp.iterdir():
        try:
            if d.is_dir() and d != keep and now - d.stat().st_mtime > MAX_AGE:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            continue


def work_path(cwd: str, sid: str, home: Path) -> Path | None:
    if not cwd or not sid:
        return None
    try:
        rel = repo_root(Path(cwd)).resolve().relative_to(home.resolve())
    except ValueError:
        return None
    return home / rel / ".tmp" / sid[:8] if rel.parts else None


def setup(data: dict, home: Path, env_file: str | None, now: float | None = None) -> str | None:
    work = work_path(str(data.get("cwd") or ""), str(data.get("session_id") or ""), home)
    if work is None:
        return None
    work.mkdir(parents=True, exist_ok=True)
    prune(work.parent, work, now if now is not None else time.time())
    if env_file:
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f"T={work.as_posix()}\n")
    return f"Work dir: {work.as_posix()} (use instead of scratchpad). Bash: write it as $T. Read/Write/Edit/Glob/Grep: the real path (they do not expand $T)."


def main() -> None:
    try:
        data = json.load(sys.stdin)
        note = setup(data, Path.home(), os.environ.get("CLAUDE_ENV_FILE"))
    except (OSError, ValueError):
        return
    if note:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note}}))


if __name__ == "__main__":
    main()
