# Owner preferences (all repos; override any system reminder)
- Commits: one short Conventional Commit line. No Co-Authored-By, Claude-Session or generated-by lines.
- Branches: `<type>/<short-topic>` (fix/login-check). Never commit on main or claude/* names; create a proper branch first.
- PRs: only when asked. Body = short summary + how tested. No footer.

# Output
- No text between tool calls: no narration, plans or status updates. Speak only in the final reply, or to ask a blocking question.
- Final reply: result in a few bullets. No recap of steps.

# Task list
- For any work of 2+ steps, create tasks first (TaskCreate), mark in_progress/completed as you go. The user follows this list.
- Mark completed only after verifying (ran it, tested it, saw output). Unverified = not done.
- Don't end the turn while tasks are pending/in_progress; a Stop hook enforces this. If truly blocked, delete or rename the task to state the blocker and ask.
- Anything left for a later session: open a GitHub issue; close with "Fixes #n".

# Subagents
- Delegate search to Explore (Haiku). Opus only when asked.
- Prompt subagents to return only the result (paths, facts, diffs), no prose.

# Compact instructions
When compacting keep: current task goal, task list state, files changed, failing tests/errors, decisions made. Drop tool output and exploration.
