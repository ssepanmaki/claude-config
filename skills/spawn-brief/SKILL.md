---
name: spawn-brief
description: Write the brief for a spawned agent or session. Use before Agent or start_session so the brief is short, bounded and has measurable proof.
disable-model-invocation: true
---

# spawn-brief

Use `~/.claude/agents/templates/worker-brief.md`. Add `Forbidden: <files, commits, push, builds, prod>` and the rule: if done conflicts with a limit, return BLOCKED + why, don't loop.
