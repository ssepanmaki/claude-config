from __future__ import annotations

import pytest

from test_guards import prompt, run_stop, say, state_dir  # noqa: F401


@pytest.mark.parametrize("step", ["push", "publish", "deploy", "delete", "merge", "credentials", "sign in"])
def test_user_only_step_skips_permission_nudge(tmp_path, step):
    text = f"Patched.\nShould I {step} the cards now?"
    assert run_stop(tmp_path, [prompt("fix it"), say(text)]) is None


def test_user_only_step_on_earlier_line_skips_nudge(tmp_path):
    text = "Needs you to sign in first.\nShould I go on?"
    assert run_stop(tmp_path, [prompt("fix it"), say(text)]) is None


def test_plain_permission_still_nudged(tmp_path):
    out = run_stop(tmp_path, [prompt("fix it"), say("Patched.\nShould I run the tests?")])
    assert out["decision"] == "block"


def test_long_reply_gets_no_length_nudge(tmp_path):
    assert run_stop(tmp_path, [prompt("hi"), say("a\nb\nc\nd\ne\nf\ng")]) is None
