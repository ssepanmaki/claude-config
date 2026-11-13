from __future__ import annotations

import os
import sys
import time
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GUARD))

import session


def make_repo(home):
    repo = home / "proj"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    return repo


def test_creates_dir_env_and_note(tmp_path):
    repo = make_repo(tmp_path)
    env = tmp_path / "env"
    note = session.setup({"cwd": str(repo / "src"), "session_id": "abcdef123456"}, tmp_path, str(env))
    work = repo / ".tmp" / "abcdef12"
    assert work.is_dir()
    assert env.read_text() == f"T={work.as_posix()}\n"
    assert note.startswith(f"Work dir: {work.as_posix()} (use instead of scratchpad). Bash: write it as $T.")


def test_ignores_cwd_outside_home_or_missing_sid(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert session.setup({"cwd": str(tmp_path), "session_id": "abcdef12"}, home, None) is None
    assert session.setup({"cwd": str(home / "x"), "session_id": ""}, home, None) is None


def test_prunes_only_old_dirs_inside_tmp(tmp_path):
    repo = make_repo(tmp_path)
    tmp = repo / ".tmp"
    old, new = tmp / "old00000", tmp / "new00000"
    old.mkdir(parents=True)
    new.mkdir()
    past = time.time() - 4 * 86400
    os.utime(old, (past, past))
    session.setup({"cwd": str(repo), "session_id": "cur12345"}, tmp_path, None)
    assert not old.exists()
    assert new.exists()
    assert (tmp / "cur12345").exists()
    assert (repo / "src").exists()


def test_pretool_expands_t_in_file_tool_paths(monkeypatch, tmp_path):
    import pretool

    repo = make_repo(tmp_path)
    monkeypatch.setattr(pretool.Path, "home", lambda: tmp_path)
    ev = {"cwd": str(repo / "src"), "session_id": "abcdef123456"}
    work = (repo / ".tmp" / "abcdef12").as_posix()
    assert pretool.expand_t(ev, "Read", {"file_path": "$T/a/b.md"}) == {"file_path": f"{work}/a/b.md"}
    assert pretool.expand_t(ev, "Grep", {"pattern": "x", "path": "$T"}) == {"pattern": "x", "path": work}
    assert pretool.expand_t(ev, "Read", {"file_path": "$Tx/a"}) is None
    assert pretool.expand_t(ev, "Bash", {"command": "cat $T/a"}) is None


def test_pretool_push_limits():
    import pretool

    push = {"command": "git add a && git commit -m x && git push origin main"}
    worker = {"agent_id": "w1", "agent_type": "worker"}
    coord = {"agent_id": "c1", "agent_type": "shipper"}
    state: dict = {}
    assert pretool.push_refusal(worker, "Bash", push, state) == pretool.WORKER_PUSH
    assert pretool.push_refusal(coord, "Bash", push, state) is None
    assert pretool.push_refusal(coord, "Bash", push, state) == pretool.SECOND_PUSH
    assert pretool.push_refusal({}, "Bash", push, state) is None
    assert pretool.push_refusal(worker, "Bash", {"command": "git log --format=push"}, state) is None
    assert pretool.push_refusal(worker, "Bash", {"command": "git -C ~/attc push"}, state) == pretool.WORKER_PUSH


def test_pretool_refuses_stdin_cat():
    import pretool

    for cmd in ["cat > /dev/null", "a; cat; b", "x && cat - | wc", "cat"]:
        assert pretool.shell_refusal({"command": cmd}), cmd
    ok = ["cat a.txt", "ls | cat", "cat <<'EOF' | node\nx\nEOF", "cat >> f <<'EOF'\nx\nEOF", "a || cat b", "concat > x"]
    for cmd in ok:
        assert pretool.STDIN_CAT.search(cmd) is None, cmd
