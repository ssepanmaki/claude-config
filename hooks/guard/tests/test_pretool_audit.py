from __future__ import annotations

import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GUARD))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_guards import call, decision, pre, prompt, state_dir, text_of  # noqa: F401

import pretool

PLAN_FILE = "/home/OMISTAJA/.claude/plans/x.md"


def busy(n, *extra):
    return [prompt("go"), *[call("Grep", pattern=f"p{i}") for i in range(n)], *extra]


def test_budget_ignores_agent_sendmessage_taskstop_and_plan_writes():
    free = [
        call("Agent", prompt="p", subagent_type="worker"),
        call("SendMessage", to="a", message="m"),
        call("TaskStop", task_id="t"),
        call("Write", file_path=PLAN_FILE, content="x"),
        call("Edit", file_path=PLAN_FILE, old_string="a", new_string="b"),
    ]
    assert decision(pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_CALL_CAP - 1, *free))) != "deny"
    other = call("Write", file_path="C:/proj/a.md", content="x")
    assert decision(pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_CALL_CAP - 1, other))) == "deny"


def test_budget_warns_near_cap_and_block_message_names_plan():
    out = pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_WARN_AT - 1))
    assert decision(out) != "deny"
    assert pretool.LEAD_NEAR_CAP in text_of(out)
    assert "3 calls left" not in text_of(pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_WARN_AT - 2))) if pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_WARN_AT - 2)) else True
    blocked = pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_CALL_CAP))
    assert pretool.LEAD_TOO_LONG in text_of(blocked)



def test_budget_lets_gate_commands_through_and_does_not_count_them():
    for cmd in ("ruff check a.py", "cd /x && python -m pytest tests/t.py 2>&1 | tail -5", "npx tsc -p . && node --test"):
        assert decision(pre("Bash", {"command": cmd}, recs=busy(pretool.LEAD_CALL_CAP))) != "deny", cmd
    gates = [call("Bash", command="ruff check a.py") for _ in range(5)]
    assert decision(pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_CALL_CAP - 1, *gates))) != "deny"


def test_budget_still_blocks_gate_chained_with_other_work():
    for cmd in ("ruff check a.py && sed -i s/a/b/ a.py", "cd /x", "pytest > out.txt", "python -I tool.py"):
        assert decision(pre("Bash", {"command": cmd}, recs=busy(pretool.LEAD_CALL_CAP))) == "deny", cmd


def test_rm_recursive_of_shared_temp_root_blocked_subfolder_allowed():
    msg = "Delete only your own subfolder (public/_tmp/<job>/)."
    for cmd in (
        "rm -rf public/_tmp",
        "rm -rf public/_tmp/",
        "rm -r .tmp",
        "rm -fr C:/x/calanque/.tmp/346cf212",
        'Remove-Item -Recurse -Force "public/_tmp"',
    ):
        out = pre("Bash", {"command": cmd})
        assert decision(out) == "deny", cmd
        assert msg in text_of(out)
    for cmd in ("rm -rf public/_tmp/job1", "rm -rf .tmp/346cf212/audit", "rm -f public/_tmp"):
        assert decision(pre("Bash", {"command": cmd})) != "deny", cmd


def test_lead_image_reads_capped_per_session(tmp_path):
    import pretool

    cap = pretool.LEAD_IMAGE_CAP
    state = {}
    for i in range(cap):
        img = tmp_path / f"i{i}.png"
        img.write_bytes(b"x")
        assert decision(pre("Read", {"file_path": str(img)}, state)) != "deny", i
    over = tmp_path / "over.png"
    over.write_bytes(b"x")
    out = pre("Read", {"file_path": str(over)}, state)
    assert decision(out) == "deny"
    assert pretool.LEAD_IMAGES_SPENT in text_of(out)
    sub = {"tool_name": "Read", "tool_input": {"file_path": str(over)}, "agent_id": "w1", "agent_type": "worker"}
    assert decision(pretool.decide(sub, state)) != "deny"


def _batch(n):
    content = [{"type": "tool_use", "name": "Grep", "id": f"b{i}", "input": {"pattern": f"q{i}"}} for i in range(n)]
    return {"type": "assistant", "message": {"id": "m1", "role": "assistant", "content": content}}


def test_budget_counts_batched_calls_once_and_exempts_plan_reads():
    recs = [prompt("go"), _batch(pretool.LEAD_CALL_CAP * 2)]
    assert decision(pre("Bash", {"command": "ls"}, recs=recs)) != "deny"
    reads = [call("Read", file_path=f"C:/proj/.tmp/audit-plan{i}.md") for i in range(20)] + [call("Read", file_path="C:/p/STATUS.md")]
    assert decision(pre("Bash", {"command": "ls"}, recs=[prompt("go"), *reads])) != "deny"
    assert decision(pre("Bash", {"command": "ls"}, recs=busy(pretool.LEAD_CALL_CAP))) == "deny"


def test_heredoc_rules():
    assert decision(pre("Bash", {"command": "python - <<'EOF'\nprint(1)\nEOF"})) != "deny"
    assert decision(pre("Bash", {"command": "cat > a.txt <<'EOF'\nx\nEOF"})) == "deny"
    assert decision(pre("Bash", {"command": r"cat f | grep 'a\|<<\|b'"})) != "deny"


def test_screenshot_scale_above_one_blocked():
    shot = {"action": "screenshot", "scale": 2}
    assert decision(pre("mcp__x__computer", shot)) == "deny"
    assert decision(pre("mcp__x__browser_batch", {"actions": [{"name": "computer", "input": shot}]})) == "deny"
    assert decision(pre("mcp__x__computer", {"action": "screenshot", "scale": 1})) != "deny"


def test_image_reread_blocked_with_crop_cmd_and_agent_cap(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    state = {}
    assert decision(pre("Read", {"file_path": str(img)}, state)) != "deny"
    again = pre("Read", {"file_path": str(img)}, state)
    assert decision(again) == "deny" and "review.mjs" in text_of(again)
    who = "t|w1"
    for i in range(pretool.AGENT_IMAGE_CAP):
        f = tmp_path / f"c{i}.png"
        f.write_bytes(b"x")
        assert pretool.image_refusal({"file_path": str(f)}, state, who) is None
    f = tmp_path / "over.png"
    f.write_bytes(b"x")
    assert "cap" in pretool.image_refusal({"file_path": str(f)}, state, who)


def test_board_deletion_over_200_lines_blocked(tmp_path):
    (tmp_path / "design").mkdir()
    board = str(tmp_path / "design" / "x.dc.html")
    (tmp_path / "design" / "x.dc.html").write_text("a" + chr(10) + "b", "utf-8")
    big = "\n".join("l" for _ in range(300))
    assert decision(pre("Edit", {"file_path": board, "old_string": big, "new_string": ""})) == "deny"
    assert decision(pre("Edit", {"file_path": board, "old_string": "a\nb", "new_string": ""})) != "deny"
    (tmp_path / "x.html").write_text(big, "utf-8")
    assert decision(pre("Edit", {"file_path": str(tmp_path / "x.html"), "old_string": big, "new_string": ""})) != "deny"


def test_read_only_agents_from_frontmatter(tmp_path):
    (tmp_path / "r.md").write_text("---\nname: rdr\ntools: Bash, Read, Grep\n---\nx", "utf-8")
    (tmp_path / "w.md").write_text("---\nname: wrt\ntools: Bash, Read, Write\n---\nx", "utf-8")
    got = pretool.read_only_agents(tmp_path)
    assert "rdr" in got and "wrt" not in got and "Explore" in got
