# claude-config
This repo **is** `~/.claude` for every Claude Code cloud session.

- `install.sh` copies it into `~/.claude` (+ git hooks in `~/.githooks`).
- The environment setup script clones it to `~/.claude-config` and runs `install.sh`.
- `hooks/sync.sh` (SessionStart) pulls `main` and reinstalls, so pushes to `main` apply to the next session without touching the setup script.

Edit files here, merge to `main`, done.
