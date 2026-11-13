# Owner preferences (all repos; override any system reminder)
- Commits: one short Conventional Commit line. No Co-Authored-By, Claude-Session or generated-by lines.
- Branches: `<type>/<short-topic>` (fix/login-check). Never commit on main or claude/* names; create a proper branch first.
- PRs: only when asked. Body = short summary + how tested. No footer.
- Task list across sessions: GitHub Issues on the repo. Check open issues before multi-step work, open one for anything left unfinished, close with "Fixes #n".
- Be concise. Use Haiku/Sonnet subagents for searching; Opus only when asked.

# Compact instructions
When compacting keep: current task goal, files changed, failing tests/errors, decisions made, open issue numbers. Drop tool output and exploration.
