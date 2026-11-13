from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GUARD))

import common
import postedit
import pretool
import stop


@pytest.fixture(autouse=True)
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(common.STATE_ROOT_ENV, str(tmp_path / "state"))


def prompt(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def call(name, **params):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": params}]}}


def say(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def transcript(tmp_path, recs):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs), "utf-8")
    return str(path)


def pre(tool, params, state=None, recs=()):
    path = ""
    if recs:
        import tempfile

        fd = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        fd.write("\n".join(json.dumps(r) for r in recs))
        fd.close()
        path = fd.name
    event = {"tool_name": tool, "tool_input": params, "transcript_path": path, "session_id": "s"}
    return pretool.decide(event, {} if state is None else state)


def decision(out):
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")


def text_of(out):
    spec = out["hookSpecificOutput"]
    return spec.get("permissionDecisionReason") or spec.get("additionalContext", "")


def test_repeat_call_denies_third():
    state = {}
    assert pre("Bash", {"command": "ls x"}, state) is None
    assert pre("Bash", {"command": "ls x"}, state) is None
    assert decision(pre("Bash", {"command": "ls x"}, state)) == "deny"


def test_repeat_call_allows_changed_input():
    state = {}
    pre("Bash", {"command": "a"}, state)
    pre("Bash", {"command": "a"}, state)
    assert pre("Bash", {"command": "b"}, state) is None


def test_read_streak_denies_past_limit_and_edit_resets():
    state = {}
    n = pretool.READ_STREAK_LIMIT
    for i in range(n):
        assert pre("Grep", {"pattern": f"p{i}", "head_limit": 5}, state) is None
    out = pre("Grep", {"pattern": f"p{n}", "head_limit": 5}, state)
    assert decision(out) == "deny" and "codegraph_explore" in text_of(out)
    state = {}
    for i in range(n - 1):
        pre("Grep", {"pattern": f"p{i}", "head_limit": 5}, state)
    pre("Edit", {"file_path": "x.py", "old_string": "a", "new_string": "b"}, state)
    assert pre("Grep", {"pattern": "z", "head_limit": 5}, state) is None


def test_long_unranged_read_gets_limit_200(tmp_path):
    big = tmp_path / "a.txt"
    big.write_text("x\n" * 500)
    out = pre("Read", {"file_path": str(big)})
    assert out["hookSpecificOutput"]["updatedInput"]["limit"] == 200


def test_small_or_ranged_read_untouched(tmp_path):
    small = tmp_path / "s.txt"
    small.write_text("a\nb\n")
    assert pre("Read", {"file_path": str(small)}) is None
    big = tmp_path / "b.txt"
    big.write_text("x\n" * 500)
    assert pre("Read", {"file_path": str(big), "limit": 50}) is None


def test_big_image_read_denied(tmp_path):
    img = tmp_path / "i.png"
    img.write_bytes(b"0" * 1_100_000)
    assert decision(pre("Read", {"file_path": str(img)})) == "deny"


def test_wide_root_and_bare_wildcard_denied():
    assert decision(pre("Grep", {"pattern": "x", "path": str(Path.home())})) == "deny"
    assert decision(pre("Glob", {"pattern": "**/*"})) == "deny"
    assert decision(pre("Glob", {"pattern": "*", "path": str(Path.home() / "proj")})) is None


@pytest.mark.parametrize(
    "cmd",
    [
        "sleep 100; ls out",
        "until [ -f DONE ]; do sleep 3; done",
        "for i in $(seq 1 55); do grep -q pass log && break; sleep 10; done",
        "cat > lib.mjs <<'EOF'\nexport const a = 1;\nEOF",
        "cat <<EOF > notes.md\nhi\nEOF",
        "tee out.txt <<EOF\nx\nEOF",
        "powershell -Command Start-Sleep -Seconds 100",
    ],
)
def test_shell_waits_and_heredoc_files_denied(cmd):
    assert decision(pre("Bash", {"command": cmd})) == "deny"


@pytest.mark.parametrize(
    "params",
    [
        {"command": "sleep 2; curl -s -m 5 localhost:5173"},
        {"command": "for f in *.png; do echo $f; done"},
        {"command": "git commit -F - <<'EOF'\nmsg\nEOF"},
        {"command": "python - <<'EOF'\nprint(1)\nEOF"},
        {"command": "until [ -f DONE ]; do sleep 3; done", "run_in_background": True},
        {"command": "npm test 2>&1 | tail -5"},
    ],
)
def test_shell_ok_commands_pass(params):
    assert decision(pre("Bash", params)) != "deny"


@pytest.mark.parametrize(
    "cmd",
    [
        "npm run typecheck && npm test && npm run build",
        "cd w && npm test 2>&1 | tail -5",
        "npx vitest run",
        "pytest -q",
    ],
)
def test_subagent_full_gate_denied(cmd):
    event = {"tool_name": "Bash", "tool_input": {"command": cmd}, "agent_id": "a1", "agent_type": "worker"}
    assert decision(pretool.decide(event, {})) == "deny"


@pytest.mark.parametrize(
    "event",
    [
        {"agent_id": "a1", "agent_type": "worker", "cmd": "npx vitest run tests/srv-sync.test.ts"},
        {"agent_id": "a1", "agent_type": "worker", "cmd": "npm test -- tests/srv-sync.test.ts && npm run typecheck"},
        {"agent_id": "a1", "agent_type": "worker", "cmd": "pytest tests/test_x.py -q"},
        {"agent_id": "a1", "agent_type": "shipper", "cmd": "npm run typecheck && npm test && npm run build"},
        {"cmd": "npm run typecheck && npm test && npm run build"},
    ],
)
def test_narrow_or_gate_owner_checks_pass(event):
    cmd = event.pop("cmd")
    assert decision(pretool.decide({"tool_name": "Bash", "tool_input": {"command": cmd}, **event}, {})) != "deny"


def test_agent_needs_model_and_no_opus():
    out = pre("Agent", {"subagent_type": "worker", "prompt": "p"})
    assert out["hookSpecificOutput"]["updatedInput"]["model"] == "sonnet"
    out = pre("Agent", {"subagent_type": "scout", "prompt": "p"})
    assert out["hookSpecificOutput"]["updatedInput"]["model"] == "haiku"
    assert decision(pre("Agent", {"subagent_type": "worker", "prompt": "p", "model": "opus"})) == "deny"



def test_heavy_commands_wrapped_in_slot():
    out = pre("Bash", {"command": "node ~/.claude/tools/review.mjs http://localhost:5174 out"})
    cmd = out["hookSpecificOutput"]["updatedInput"]["command"]
    assert cmd.startswith("( S=$(") and "slot.py acquire" in cmd and "review.mjs" in cmd
    assert pre("Bash", {"command": "npm run dev", "run_in_background": True}) is None


def test_report_text_and_scratch_heredoc_pass():
    report = "python -I x.py --text 'for each worker do the gate once\nthen sleep on it'"
    assert decision(pre("Bash", {"command": report})) != "deny"
    scratch = "cat <<'EOF' > /home/OMISTAJA/AppData/Local/Temp/claude/x/scratchpad/a.txt\nhi\nEOF"
    assert decision(pre("Bash", {"command": scratch})) != "deny"
    assert decision(pre("Bash", {"command": "until [ -f DONE ]; do\n  sleep 30\ndone"})) == "deny"


def test_lead_sizes_its_agents():
    base = [prompt("do the thing")]
    worker = {"subagent_type": "worker", "model": "sonnet", "prompt": "p"}
    assert decision(pre("Agent", worker, recs=base)) != "deny"
    n = pretool.LEAD_SOLOS
    for used in range(1, n):
        assert decision(pre("Agent", worker, recs=[*base, *[call("Agent", **worker)] * used])) != "deny"
    assert decision(pre("Agent", worker, recs=[*base, *[call("Agent", **worker)] * n])) == "deny"
    assert decision(pre("Agent", {"subagent_type": "fork", "prompt": "p"}, recs=base)) == "deny"
    note = {"to": "acoord", "message": "m"}
    three = [*base, *[call("SendMessage", **note) for _ in range(3)]]
    assert decision(pre("SendMessage", note, recs=three[:3])) != "deny"
    assert decision(pre("SendMessage", note, recs=three)) == "deny"
    scout = {"subagent_type": "scout", "model": "haiku", "prompt": "find"}
    two = [*base, call("Agent", **scout), call("Agent", **scout)]
    assert decision(pre("Agent", scout, recs=base)) != "deny"
    assert decision(pre("Agent", scout, recs=two)) == "deny"


def test_lead_never_messages_others_workers_and_caps_calls(tmp_path):
    path = transcript(tmp_path, [prompt("go")])
    subs = tmp_path / "t" / "subagents"
    subs.mkdir(parents=True)
    (subs / "agent-acoord.meta.json").write_text(json.dumps({"agentType": "coordinator", "spawnDepth": 1}))
    (subs / "agent-aworker.meta.json").write_text(json.dumps({"agentType": "worker", "parentAgentId": "acoord"}))

    def send(to):
        return pretool.decide({"tool_name": "SendMessage", "tool_input": {"to": to, "message": "m"}, "transcript_path": path}, {})

    assert decision(send("acoord")) != "deny"
    assert decision(send("aworker")) == "deny"
    busy = [prompt("go"), *[call("Grep", pattern=f"p{i}") for i in range(pretool.LEAD_CALL_CAP)]]
    assert decision(pre("Bash", {"command": "ls"}, recs=busy)) == "deny"
    assert decision(pre("mcp__ccd_turn__wrap_up", {"recap": "r"}, recs=busy)) != "deny"
    sub = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_id": "w1", "agent_type": "worker"}
    assert decision(pretool.decide(sub, {})) != "deny"


def test_grep_head_limit_and_screenshot_scale_capped():
    out = pre("Grep", {"pattern": "x", "path": "src"})
    assert out["hookSpecificOutput"]["updatedInput"]["head_limit"] == 30
    assert pre("Grep", {"pattern": "y", "path": "src", "head_limit": 5}) is None
    shot = pre("mcp__Claude_Browser__computer", {"action": "screenshot"})
    assert shot["hookSpecificOutput"]["updatedInput"]["scale"] == 0.5
    assert pre("mcp__Claude_Browser__computer", {"action": "screenshot", "scale": 0.4}) is None


def test_rule_deletion_on_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x")
    recs = [prompt("tidy the file")]
    params = {"file_path": str(tmp_path / "CLAUDE.md"), "old_string": "Never push secrets anywhere", "new_string": "x"}
    assert "removes rule line" in text_of(pre("Edit", params, recs=recs))
    recs = [prompt("remove the rule: never push secrets anywhere")]
    assert pre("Edit", params, recs=recs) is None


def test_edit_churn_and_repeat_edit():
    state = {}
    notes = [pre("Edit", {"file_path": "a.py", "old_string": f"o{i}", "new_string": "n"}, state) for i in range(21)]
    assert "21" not in "" and "20 Edits" in text_of(notes[-1])
    assert all(n is None for n in notes[:-1])
    state = {}
    outs = [pre("Edit", {"file_path": f"f{i}.py", "old_string": "same", "new_string": "new"}, state) for i in range(5)]
    assert "Same edit already in 4 files" in text_of(outs[-1])
    assert all(o is None for o in outs[:-1])


def test_line_only_notes_shell_run():
    recs = [prompt("give me the command to deploy")]
    assert "not a run" in text_of(pre("Bash", {"command": "deploy.sh"}, recs=recs))
    assert pre("Bash", {"command": "deploy.sh"}, recs=[prompt("deploy it")]) is None


def run_stop(tmp_path, recs, cwd=None, state=None):
    event = {"transcript_path": transcript(tmp_path, recs), "session_id": "s", "cwd": cwd or str(tmp_path)}
    return stop.decide(event, {} if state is None else state)


def test_start_session_prompt_gets_sub_rules():
    out = pre("mcp__ccd_session__start_session", {"initiation": "user_asked", "prompt": "do x"})
    assert out["hookSpecificOutput"]["updatedInput"]["prompt"].startswith(common.SUB_MARKER)
    assert pre("mcp__ccd_session__start_session", {"prompt": f"{common.SUB_RULES}\n\ndo x"}) is None
    assert pre("mcp__ccd_session__start_session", {"initiation": "offer", "title": "t"}) is None


def test_coordinator_agent_call_denied_everywhere():
    sub = [prompt(f"{common.SUB_RULES}\n\ndo x")]
    agent = {"subagent_type": "coordinator", "prompt": "p", "model": "sonnet"}
    for recs in (sub, [prompt("plan this")]):
        out = pre("Agent", agent, recs=recs)
        assert decision(out) == "deny"
        assert "No `coordinator`: it is retired." in text_of(out)
    assert decision(pre("Agent", {**agent, "subagent_type": "worker"}, recs=sub)) != "deny"


def test_builtin_agents_redirected():
    base = {"prompt": "p", "model": "sonnet"}
    for kind in ("Explore", "Plan", "claude"):
        out = pre("Agent", {**base, "subagent_type": kind}, recs=[prompt("do x")])
        assert decision(out) == "deny"
        assert "`worker`" in text_of(out)
    for kind in ("general-purpose", None):
        out = pre("Agent", {**base, "subagent_type": kind}, recs=[prompt("do x")])
        assert out["hookSpecificOutput"]["updatedInput"]["subagent_type"] == "worker"
    for kind in ("scout", "claude-code-guide"):
        assert decision(pre("Agent", {**base, "subagent_type": kind}, recs=[prompt("do x")])) != "deny"


def test_sub_session_stays_quiet():
    sub = [prompt(f"{common.SUB_RULES}\n\ndo x")]
    assert decision(pre("SendMessage", {"to": "local_abc", "message": "m"}, recs=sub)) == "deny"
    out = pre("Agent", {"subagent_type": "worker", "prompt": "p", "model": "sonnet", "run_in_background": True}, recs=sub)
    assert out["hookSpecificOutput"]["updatedInput"]["run_in_background"] is False
    assert decision(pre("SendMessage", {"to": "local_abc", "message": "m"}, recs=[prompt("hi")])) != "deny"


def test_agent_children_forced_foreground():
    event = {"tool_name": "Agent", "agent_id": "a1", "transcript_path": "", "session_id": "s",
             "tool_input": {"subagent_type": "worker", "prompt": "p", "model": "sonnet", "run_in_background": True}}
    out = pretool.decide(event, {})
    assert out["hookSpecificOutput"]["updatedInput"]["run_in_background"] is False
    out = pre("Agent", {"subagent_type": "worker", "prompt": "p", "model": "sonnet", "run_in_background": True}, recs=[prompt("hi")])
    assert not out or out.get("hookSpecificOutput", {}).get("updatedInput", {}).get("run_in_background") is not False


def test_dirty_handback_refused():
    dirty = {"summary": "1: done — a.ts\n2: done — motion, push/pop travel unverified\nship abc"}
    assert decision(pre("SubagentHandback", dirty)) == "deny"
    assert decision(pre("SubagentHandback", {"summary": "1: I did not check Jour"})) == "deny"
    clean = {"summary": "1: done — a.ts\n2: blocked — deploy needs Dat, not verified on prod\nship abc"}
    assert decision(pre("SubagentHandback", clean)) != "deny"


def test_sub_session_long_reply_blocked(tmp_path):
    sub = prompt(f"{common.SUB_RULES}\n\ndo x")
    out = run_stop(tmp_path, [sub, say("a\nb\nc\nd\ne")])
    assert out and "Sub-session" in out["reason"]
    assert run_stop(tmp_path, [sub, say("Done: abc123.\nGate green.\nLeft: none.")]) is None
    assert run_stop(tmp_path, [prompt("hi"), say("a\nb\nc\nd\ne")]) is None


def test_ask_reason(tmp_path):
    out = run_stop(tmp_path, [prompt("fix it"), say("Patched.\nShould I run the tests?")])
    assert out["decision"] == "block"
    assert run_stop(tmp_path, [prompt("fix it"), say("Patched. Done")]) is None
    assert run_stop(tmp_path, [prompt("fix it"), say("Patched.\nShould I publish the cards and push?")]) is None


def test_proof_reason(tmp_path):
    edit = call("Edit", file_path="a.py", old_string="a", new_string="b")
    out = run_stop(tmp_path, [prompt("fix"), edit, say("All done")])
    assert "no test" in out["reason"]
    ran = call("Bash", command="python -m pytest tests -q")
    assert run_stop(tmp_path, [prompt("fix"), edit, ran, say("All done")]) is None
    doc = call("Write", file_path="plan.md", content="x")
    assert run_stop(tmp_path, [prompt("fix"), doc, say("All done")]) is None


def init_repo(path):
    for args in (["init", "-b", "main"], ["config", "user.email", "a@b"], ["config", "user.name", "n"]):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)


def commit_all(path):
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=path, check=True)


def test_suppression_scan(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    init_repo(repo)
    src = repo / "m.py"
    src.write_text("x = 1\n")
    commit_all(repo)
    src.write_text("x = 1\ny = bad()  # noqa\n")
    recs = [prompt("go"), call("Edit", file_path=str(src), old_string="a", new_string="b"), say("ok")]
    out = run_stop(tmp_path, recs, cwd=str(tmp_path))
    assert "suppression" in out["reason"]
    src.write_text("x = 1\n")
    assert run_stop(tmp_path, recs, cwd=str(tmp_path)) is None


def test_assertion_weakening_scan(tmp_path):
    repo = tmp_path / "r"
    (repo / "tests").mkdir(parents=True)
    init_repo(repo)
    code, test = repo / "m.py", repo / "tests" / "test_m.py"
    code.write_text("x = 1\n")
    test.write_text("assert x == 1\n")
    commit_all(repo)
    code.write_text("x = 2\n")
    test.write_text("pass\n")
    recs = [prompt("go"), call("Edit", file_path=str(code)), call("Edit", file_path=str(test)), say("ok")]
    out = run_stop(tmp_path, recs)
    assert "assertion removed" in out["reason"]


def test_dirty_main(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    init_repo(repo)
    (repo / "a.txt").write_text("1")
    commit_all(repo)
    (repo / "a.txt").write_text("2")
    recs = [prompt("go"), call("Write", file_path=str(repo / "a.txt")), say("ok")]
    out = run_stop(tmp_path, recs, cwd=str(repo))
    assert "Uncommitted changes on main" in out["reason"]
    commit_all(repo)
    assert run_stop(tmp_path, recs, cwd=str(repo)) is None


def test_skips_waiting_and_idle_blocks(tmp_path):
    asks = [prompt("fix it"), call("AskUserQuestion", question="which?"), say("Should I run the tests?")]
    assert run_stop(tmp_path, asks) is None
    recs = [prompt("fix it"), say("Should I run the tests?")]
    state = {}
    outs = [run_stop(tmp_path, recs, state=state) for _ in range(4)]
    assert [o is not None for o in outs] == [True, True, True, False]


def test_running_agent_skips(tmp_path):
    started = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "async_launched agentId: abc123"}]}}
    recs = [prompt("fix it"), started, say("Should I run the tests?")]
    assert run_stop(tmp_path, recs) is None


def test_postedit_lint(tmp_path):
    assert postedit.blocking_lint(["a.py:1:1: F401 unused", "a.py:2:1: E711 bad"]) == ["a.py:2:1: E711 bad"]
    assert postedit.lint_reason(str(tmp_path / "missing.py")) == ""
    assert postedit.lint_reason(str(tmp_path / "x.txt")) == ""
    py = tmp_path / "bad.py"
    py.write_text('__all__ = ["nope"]\n')
    reason = postedit.lint_reason(str(py))
    if postedit.shutil.which("ruff"):
        assert "F822" in reason
    else:
        assert reason == ""


def test_postedit_script_runs_isolated(tmp_path):
    py = tmp_path / "ok.py"
    py.write_text("x = 1\n")
    event = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(py)}})
    done = subprocess.run([sys.executable, "-I", str(GUARD / "postedit.py")], input=event, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout == ""


def test_pretool_script_denies_isolated():
    event = json.dumps({"tool_name": "Grep", "tool_input": {"pattern": "x", "path": str(Path.home())}, "session_id": "iso"})
    env = {**__import__("os").environ, common.STATE_ROOT_ENV: str(Path(__import__("tempfile").mkdtemp()))}
    done = subprocess.run([sys.executable, "-I", str(GUARD / "pretool.py")], input=event, capture_output=True, text=True, env=env)
    assert json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_long_lines_cut_by_bytes(tmp_path):
    big = tmp_path / "board.html"
    big.write_bytes((b"y" * 999 + b"\n") * 100)
    out = pre("Read", {"file_path": str(big)})
    assert out["hookSpecificOutput"]["updatedInput"]["limit"] == 24


def test_paging_a_big_file_hits_budget(tmp_path):
    big = tmp_path / "bundle.css"
    big.write_text(("z" * 99 + "\n") * 2000)
    state = {}
    for start in (1, 201, 401):
        assert decision(pre("Read", {"file_path": str(big), "offset": start, "limit": 200}, state)) != "deny"
    assert decision(pre("Read", {"file_path": str(big), "offset": 601, "limit": 200}, state)) == "deny"


def handback():
    return {"type": "user", "isMeta": True, "origin": {"kind": "peer", "senderTaskId": "a1"}, "message": {"role": "user", "content": "[Subagent hand-back] done"}}


def test_lead_cap_resets_after_handback_but_request_limits_do_not():
    worker = {"subagent_type": "worker", "model": "sonnet", "prompt": "p"}
    busy = [prompt("go"), *[call("Grep", pattern=f"p{i}") for i in range(pretool.LEAD_CALL_CAP)]]
    assert decision(pre("Bash", {"command": "ls"}, recs=busy)) == "deny"
    assert decision(pre("Bash", {"command": "ls"}, recs=[*busy, handback()])) != "deny"
    n = pretool.LEAD_SOLOS
    spent = [prompt("go"), *[call("Agent", **worker)] * (n - 1), handback()]
    assert decision(pre("Agent", worker, recs=spent)) != "deny"
    spent = [prompt("go"), *[call("Agent", **worker)] * n, handback()]
    assert decision(pre("Agent", worker, recs=spent)) == "deny"


def test_running_call_is_not_counted_against_itself():
    worker = {"subagent_type": "worker", "model": "sonnet", "prompt": "p"}
    me = call("Agent", **worker)
    me["message"]["content"][0]["id"] = "me"
    event = {"tool_name": "Agent", "tool_input": worker, "tool_use_id": "me", "session_id": "s"}
    recs = [prompt("go"), me, me]
    assert common.calls_since_prompt(recs, "me") == []
    assert len(common.calls_since_prompt(recs)) == 1
    assert event["tool_use_id"] == "me"


def test_app_style_prompts_count_as_prompts():
    attached = {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": [
        {"type": "text", "text": "<artifact-view-context>x</artifact-view-context>"}, {"type": "text", "text": "yes! 15"}]}}
    pasted = {"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "look"}, {"type": "image", "source": {}}]}}
    assert common.is_prompt(attached) and common.is_prompt(pasted)
    assert not common.is_prompt(handback())
    assert not common.is_prompt({**attached, "origin": {"kind": "task-notification"}})


def fake_transcript(tmp_path):
    agent = call("Agent", description="Build it", subagent_type="worker")
    agent["message"]["content"][0]["id"] = "tu1"
    plan = call("mcp__ccd_turn__update_plan", items=[{"content": "step one", "status": "in_progress"}])
    return transcript(tmp_path, [prompt("first"), prompt("second ask"), plan, agent, call("Edit", file_path="/x/a.py")])


def run_compact(mode, event, monkeypatch, tmp_path, capsys):
    import compact

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(sys, "argv", ["compact.py", mode])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(event)))
    compact.main()
    return capsys.readouterr().out


def test_precompact_writes_note_and_sessionstart_emits_it(tmp_path, monkeypatch, capsys):
    event = {"session_id": "sess1", "cwd": str(tmp_path), "transcript_path": fake_transcript(tmp_path)}
    run_compact("precompact", event, monkeypatch, tmp_path, capsys)
    note = (tmp_path / ".claude" / "state" / "compact" / "sess1.md").read_text("utf-8")
    assert len(note.splitlines()) <= 60
    for needle in ("second ask", "step one", "Build it", "tu1", "/x/a.py"):
        assert needle in note
    out = json.loads(run_compact("sessionstart", {"session_id": "sess1"}, monkeypatch, tmp_path, capsys))
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "second ask" in out["hookSpecificOutput"]["additionalContext"]
    assert run_compact("sessionstart", {"session_id": "none"}, monkeypatch, tmp_path, capsys) == ""


def compact_note(tmp_path, monkeypatch, capsys, recs):
    event = {"session_id": "s2", "cwd": str(tmp_path), "transcript_path": transcript(tmp_path, recs)}
    run_compact("precompact", event, monkeypatch, tmp_path, capsys)
    return (tmp_path / ".claude" / "state" / "compact" / "s2.md").read_text("utf-8")


def agent_with_result(uid, agent_id):
    use = call("Agent", description="Job " + uid, subagent_type="worker")
    use["message"]["content"][0]["id"] = uid
    res = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": uid, "content": f"ok\nagentId: {agent_id} (internal)"}]}}
    return [use, res]


def test_compact_note_skips_non_prompts(tmp_path, monkeypatch, capsys):
    recs = [prompt("real ask"), prompt("This session is being continued from a previous conversation"),
            prompt("<artifact-content-authored-by-others/> blah"), prompt("<command-name>/x</command-name>"),
            prompt("<local-command-stdout>o</local-command-stdout>"), prompt("<task-notification>t</task-notification>"),
            prompt("<system-reminder>only</system-reminder>"), {**prompt("summary"), "isCompactSummary": True}]
    note = compact_note(tmp_path, monkeypatch, capsys, recs)
    assert "real ask" in note
    for bad in ("continued", "artifact-content", "command-name", "local-command", "task-notification", "only", "summary"):
        assert bad not in note


def test_compact_note_drops_finished_agents_and_prints_ids(tmp_path, monkeypatch, capsys):
    done = {"type": "user", "message": {"role": "user", "content": '<agent-message from="aaa111">hi</agent-message>'}}
    notif = prompt("<task-notification><task-id>ccc333</task-id><status>completed</status></task-notification>")
    recs = [*agent_with_result("u1", "aaa111"), *agent_with_result("u2", "bbb222"), *agent_with_result("u3", "ccc333"), done, notif]
    note = compact_note(tmp_path, monkeypatch, capsys, recs)
    assert "id bbb222" in note
    assert "aaa111" not in note and "ccc333" not in note and "below" not in note


def hb(text, **event):
    return pretool.decide({"tool_name": "SubagentHandback", "tool_input": {"message": text}, "session_id": "s", "cwd": "C:/r/repo", **event}, {})


def test_handback_ship_and_left_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_ASKS_FILE", str(tmp_path / "asks.md"))
    coord = {"agent_id": "a1", "agent_type": "shipper"}
    assert decision(hb("1: done — a.py", **coord)) == "deny"
    assert decision(hb("1: done — a.py\nship abc1234", **coord)) != "deny"
    assert decision(hb("1: done\nnot shipped: local only", **coord)) != "deny"
    assert decision(hb("done 2, left 1; a.py")) == "deny"
    assert decision(hb("done 2, left 0; a.py")) != "deny"
    assert decision(hb("done 2, left 1; blocked: no creds")) != "deny"


def test_worker_cannot_ask_dat_shipper_can(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_ASKS_FILE", str(tmp_path / "asks.md"))
    assert decision(hb("done 1, left 1\nneeds Dat: which db?", agent_id="a9", agent_type="worker")) == "deny"
    assert decision(hb("done 1, left 1\nblocked: which db?", agent_id="a9", agent_type="worker")) != "deny"
    assert decision(hb("done 1, left 1\nneeds Dat: which db?\nship abc1234", agent_id="a1", agent_type="shipper")) != "deny"


def test_stop_hook_active_exits_early(tmp_path):
    path = transcript(tmp_path, [prompt("fix"), call("Edit", file_path="/x/a.py"), say("Done, it works.")])
    assert stop.decide({"transcript_path": path, "stop_hook_active": True}, {}) is None


@pytest.fixture
def asks(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_ASKS_FILE", str(tmp_path / "asks.md"))
    monkeypatch.syspath_prepend(str(GUARD.parents[1] / "tools"))
    import ask

    return ask


def test_needs_dat_handback_files_ask_and_cli_roundtrip(asks, capsys):
    hb("done 1, left 1\nneeds Dat: which db?\nship abc1234", agent_id="a9", agent_type="shipper")
    [one] = asks.load()
    assert (one.question, one.meta["agent"], one.meta["sid"], one.repo, one.answer) == ("which db?", "a9", "s", "repo", "")
    assert asks.main(["list", "--open"]) == 0 and one.id in capsys.readouterr().out
    assert asks.main(["answer", one.id, "the pg one"]) == 0
    assert asks.load()[0].answer == "the pg one"
    capsys.readouterr()
    assert asks.main(["list", "--open"]) == 0 and capsys.readouterr().out == ""
    assert asks.main(["list", "--answered"]) == 0 and "the pg one" in capsys.readouterr().out
    assert asks.main(["done", one.id]) == 0
    capsys.readouterr()
    assert asks.main(["list"]) == 0 and capsys.readouterr().out == ""


def test_asks_pickup_cases(asks):
    import asks_hook

    a = asks.file_ask("q same", "C:/r/repo", "s1", "ag1", "worker")
    b = asks.file_ask("q other", "C:/r/repo", "s0", "ag0", "worker")
    c = asks.file_ask("q open", "C:/r/repo", "s0", "ag2", "worker")
    assert asks_hook.lines_for("s1", "C:/r/repo")[0].endswith("3 agent ask(s) still open for Dat (`python3 ~/.claude/tools/ask.py list --open`).")
    asks.answer(a, "A1")
    asks.answer(b, "B1")
    out = asks_hook.lines_for("s1", "C:/r/repo")
    assert "SendMessage it the answer" in out[0] and "ag1" in out[0]
    assert "use it as context" in out[1] and "B1" in out[1]
    assert "1 agent ask" in out[2]
    assert not any("B1" in ln for ln in asks_hook.lines_for("s1", "C:/elsewhere"))
    asks.done(a)
    asks.done(b)
    asks.done(c)
    assert asks_hook.lines_for("s1", "C:/r/repo") == []


def test_repeat_hint_fires_once_on_third(tmp_path, monkeypatch, capsys):
    import io

    import repeats_hint

    def run(cmd):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "rs"})))
        repeats_hint.main()
        return capsys.readouterr().out

    outs = [run(f"npm run lint --prefix C:/r/p{i}") for i in range(5)]
    assert [bool(o) for o in outs] == [False, False, True, False, False]
    assert "Repeated 3x" in outs[2]
    assert run("git status") == ""


def test_repeats_script_lists_shapes_across_sessions(tmp_path):
    sys.path.insert(0, str(GUARD.parents[1] / "tools" / "audit"))
    import repeats

    for sess in ("s1", "s2"):
        d = tmp_path / "proj"
        d.mkdir(exist_ok=True)
        lines = [call("Bash", command=f"npm run lint --prefix C:/r/{i}") for i in range(3)]
        (d / f"{sess}.jsonl").write_text("\n".join(json.dumps(x) for x in lines), "utf-8")
    out = repeats.report(repeats.scan(tmp_path, 1))
    assert len(out) == 1 and out[0].startswith("6x 2 sessions") and "npm-run" in out[0]


def test_image_cap_and_unchanged_reread(tmp_path):
    img = tmp_path / "s.png"
    img.write_bytes(b"0" * 150_000)
    big = tmp_path / "b.png"
    big.write_bytes(b"0" * 250_000)
    state = {}
    assert decision(pre("Read", {"file_path": str(big)}, state)) == "deny"
    assert decision(pre("Read", {"file_path": str(img)}, state)) != "deny"
    assert "unchanged" in text_of(pre("Read", {"file_path": str(img)}, state))
    img.write_bytes(b"1" * 160_000)
    pre("Bash", {"command": "ls"}, state)
    assert decision(pre("Read", {"file_path": str(img)}, state)) != "deny"


def test_read_over_2000_lines_needs_range(tmp_path):
    long = tmp_path / "l.txt"
    long.write_text("x\n" * 2500)
    out = pre("Read", {"file_path": str(long)})
    assert decision(out) == "deny" and "offset=1 limit=200" in text_of(out)
    assert decision(pre("Read", {"file_path": str(long), "limit": 100})) != "deny"
    assert decision(pre("Read", {"file_path": str(long), "offset": 5})) != "deny"
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"\n" * 3000)
    assert decision(pre("Read", {"file_path": str(pdf)})) != "deny"


def test_worker_handback_accepts_caveats_needs_owner_fully_done(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_ASKS_FILE", str(tmp_path / "asks.md"))
    worker = {"agent_id": "a9", "agent_type": "worker"}
    assert decision(hb("done 2, left 0\nCaveats: not verified on Safari", **worker)) != "deny"
    assert decision(hb("done 1, left 1\nneeds-owner: pick the db", **worker)) != "deny"
    assert decision(hb("fully done, nothing partly missed", **worker)) != "deny"
    assert decision(hb("done 1\nthe motion is unverified", **worker)) == "deny"
    coord = {"agent_id": "c1", "agent_type": "shipper"}
    assert decision(hb("done 2\nCaveats: not verified\nship abc1234", **coord)) == "deny"


def test_read_only_agent_handback_skips_gap_check(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_ASKS_FILE", str(tmp_path / "asks.md"))
    reader = {"agent_id": "e1", "agent_type": "scout"}
    assert decision(hb("COST-x: no finding, coverage unverified, not checked", **reader)) != "deny"
    shipper = {"agent_id": "s1", "agent_type": "shipper"}
    assert decision(hb("1: done — a.py", **shipper)) == "deny"
    assert decision(hb("1: done — a.py\nship abc1234", **shipper)) != "deny"


def test_workflow_opus_refused(tmp_path):
    opus = "export const meta = {name: 'x', description: 'y'}\nawait agent('go', {model: 'opus'})"
    assert decision(pre("Workflow", {"script": opus})) == "deny"
    script = tmp_path / "wf.js"
    script.write_text(opus.replace("opus", "claude-opus-5-5"), encoding="utf-8")
    assert decision(pre("Workflow", {"scriptPath": str(script)})) == "deny"
    assert decision(pre("Workflow", {"script": opus.replace("opus", "sonnet")})) != "deny"
    assert decision(pre("Workflow", {"name": "ship-batch"})) != "deny"


def test_shipper_may_gate_and_push_once():
    shipper = {"agent_id": "s2", "agent_type": "shipper"}
    state: dict = {}
    assert pretool.gate_refusal(shipper, "Bash", {"command": "npm test"}) is None
    assert pretool.push_refusal(shipper, "Bash", {"command": "git push"}, state) is None
    assert pretool.push_refusal(shipper, "Bash", {"command": "git push"}, state) == pretool.SECOND_PUSH


def test_write_new_dir_allowed_typo_refused(tmp_path):
    (tmp_path / "audit").mkdir()
    assert pretool.path_refusal({}, "Write", {"file_path": str(tmp_path / "brandnew" / "a.md")}) is None
    assert "did you mean" in str(pretool.path_refusal({}, "Write", {"file_path": str(tmp_path / "audits" / "a.md")}))


def test_heredoc_piped_to_interpreter_allowed():
    assert decision(pre("Bash", {"command": "cat <<'EOF' | python -\nprint(1)\nEOF"})) != "deny"
    out = pre("Bash", {"command": "cat > a.txt <<EOF\nhi\nEOF"})
    assert decision(out) == "deny" and "python - <<" in text_of(out)


@pytest.mark.parametrize("kind,denied", [("auditor", False), ("Explore", False), ("scout", False), ("worker", True)])
def test_read_streak_exempts_read_only_agents(kind, denied):
    state = {}
    event = {"tool_name": "Grep", "agent_id": "a1", "agent_type": kind}
    for i in range(pretool.READ_STREAK_LIMIT):
        pretool.decide({**event, "tool_input": {"pattern": f"p{i}", "head_limit": 5}}, state)
    out = pretool.decide({**event, "tool_input": {"pattern": "p99", "head_limit": 5}}, state)
    assert (decision(out) == "deny") is denied


def test_refusals_name_the_allowed_form():
    assert "run_in_background: true" in text_of(pre("Bash", {"command": "until [ -f D ]; do sleep 3; done"}))
    assert "run_in_background: true" in text_of(pre("Bash", {"command": "sleep 100"}))
    assert "path=" in text_of(pre("Grep", {"pattern": "x", "path": str(Path.home())}))
    event = {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}, "agent_id": "a1", "agent_type": "worker"}
    assert "Allowed: one test file" in text_of(pretool.decide(event, {}))


def test_nudges_give_a_plain_reason(tmp_path):
    big = tmp_path / "a.txt"
    big.write_text("x\n" * 500)
    assert "why" in text_of(pre("Read", {"file_path": str(big)}))


def test_call_hint_at_120_in_subagent():
    state = {}
    event = {"tool_name": "Bash", "agent_id": "a1", "agent_type": "worker"}
    outs = [pretool.decide({**event, "tool_input": {"command": f"ls {i}"}}, state) for i in range(120)]
    assert all(o is None for o in outs[:119])
    assert "done N, left M" in text_of(outs[119])
    assert pre("Bash", {"command": "ls"}, {}) is None


@pytest.mark.parametrize(
    "cmd",
    ["for i in $(seq 1 40); do sleep 10; done", "sleep 300", "while true; do sleep 5; done", "sleep 5"],
)
def test_sleep_only_denied_even_in_background(cmd):
    assert decision(pre("Bash", {"command": cmd, "run_in_background": True})) == "deny"


HANG_DENIED = [
    "find / -name foo",
    "find ~ -name '*.py'",
    "find $HOME -type f",
    "find /c/Users/OMISTAJA -name x",
    "find /home/OMISTAJA/ -name x",
    "find /c/Users/OMISTAJA/AppData/Local/Temp/claude -name x",
    "find C:\\Users\\OMISTAJA\\AppData\\Local\\Temp -name x",
]
HANG_ALLOWED = [
    "find / -maxdepth 2 -name foo",
    "find ~ -maxdepth 1 -name x",
    "find /c/Users/OMISTAJA/calanque/src -name '*.ts'",
    "find . -name '*.py'",
    "curl -s -m 5 http://localhost:5174/",
    "curl --max-time 5 http://a/b",
    "curl --connect-timeout 3 http://a/b",
    "curl -sm5 http://a/b",
    "git commit -m 'fix curl call'",
]


@pytest.mark.parametrize("cmd", HANG_DENIED)
def test_unbounded_find_and_curl_denied(cmd):
    assert decision(pre("Bash", {"command": cmd})) == "deny"


@pytest.mark.parametrize("cmd", HANG_ALLOWED)
def test_bounded_find_and_curl_allowed(cmd):
    assert pre("Bash", {"command": cmd}) is None


@pytest.mark.parametrize(
    ("cmd", "fixed"),
    [
        ("curl http://localhost:5174/", "curl -m 30 http://localhost:5174/"),
        ("curl -s https://example.com/api | jq .", "curl -m 30 -s https://example.com/api | jq ."),
        ("cd x && curl -sS -o out.json http://a/b", "cd x && curl -m 30 -sS -o out.json http://a/b"),
    ],
)
def test_curl_without_timeout_gets_one_added(cmd, fixed):
    out = pre("Bash", {"command": cmd, "description": "d"})
    assert decision(out) == "allow"
    assert out["hookSpecificOutput"]["updatedInput"] == {"command": fixed, "description": "d"}
    assert pre("Bash", {"command": cmd, "run_in_background": True}) is None


@pytest.mark.parametrize("cmd", HANG_DENIED)
def test_unbounded_find_and_curl_allowed_in_background(cmd):
    assert pre("Bash", {"command": cmd, "run_in_background": True}) is None


def test_missing_read_denied_with_suggestion(tmp_path):
    (tmp_path / "pretool.py").write_text("x\n")
    out = pre("Read", {"file_path": str(tmp_path / "pretol.py")})
    assert decision(out) == "deny"
    assert "did you mean" in text_of(out) and "pretool.py" in text_of(out)
    assert pre("Read", {"file_path": str(tmp_path / "pretool.py")}) is None


def test_missing_edit_and_notebook_denied_existing_allowed(tmp_path):
    (tmp_path / "a.py").write_text("x\n")
    assert decision(pre("Edit", {"file_path": str(tmp_path / "b.py"), "old_string": "x", "new_string": "y"})) == "deny"
    assert decision(pre("NotebookEdit", {"notebook_path": str(tmp_path / "n.ipynb")})) == "deny"
    assert pre("Edit", {"file_path": str(tmp_path / "a.py"), "old_string": "x", "new_string": "y"}) is None
    assert pre("Edit", {"file_path": str(tmp_path / "new.py"), "old_string": "", "new_string": "y"}) is None


def test_missing_script_in_bash_denied(tmp_path):
    (tmp_path / "run_it.py").write_text("print(1)\n")
    out = pre("Bash", {"command": f"python {tmp_path.as_posix()}/run_t.py --x"})
    assert decision(out) == "deny" and "run_it.py" in text_of(out)
    assert pre("Bash", {"command": f"node -v && python {tmp_path.as_posix()}/run_it.py"}) is None


def test_write_checks_only_parent(tmp_path):
    assert pre("Write", {"file_path": str(tmp_path / "new.txt"), "content": "x"}) is None
    (tmp_path / "nodir").mkdir()
    out = pre("Write", {"file_path": str(tmp_path / "nodirs" / "new.txt"), "content": "x"})
    assert decision(out) == "deny" and "parent dir missing" in text_of(out)


def test_repeat_read_denied_until_changed_or_compacted(tmp_path):
    f = tmp_path / "r.txt"
    f.write_text("a\nb\n")
    state = {}
    params = {"file_path": str(f), "offset": 1, "limit": 5}
    assert pre("Read", params, state) is None
    out = pre("Read", params, state)
    assert decision(out) == "deny" and "already read (unchanged since)" in text_of(out)
    assert pre("Read", {**params, "offset": 2}, state) is None
    f.write_text("a\nb\nc\n")
    assert pre("Read", params, state) is None
    state.pop("reads")
    assert pre("Read", params, state) is None


def test_compact_resets_read_state(tmp_path, monkeypatch):
    import compact

    common.save_state("s", {"reads": {"k": [1, 2]}, "keep": 1})
    monkeypatch.setattr(sys, "argv", ["compact.py", "precompact"])
    monkeypatch.setattr(common, "read_events", lambda: {"session_id": "s"})
    monkeypatch.setattr(compact, "build", lambda e: "")
    monkeypatch.setattr(compact, "note_path", lambda s: tmp_path / "note.md")
    compact.main()
    state = common.load_state("s")
    assert "reads" not in state and state["keep"] == 1
