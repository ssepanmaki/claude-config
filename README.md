# claude-config

## Install (this repo is `~/.claude`)
```
git clone https://github.com/ssepanmaki/claude-config ~/.claude && ~/.claude/install.sh
```
`install.sh` checks python3/jq/git (ruff, pytest, node optional), points git's `core.hooksPath` at `hooks/git` (no attribution trailers in any repo), aliases `/home/OMISTAJA`, smoke-tests the gates and runs the guard tests. It prints `ready` or `NOT ready`. `.gitignore` is an allowlist, so credentials, transcripts and history in `~/.claude` are never tracked. Cloud sessions use `cloud-setup.sh` instead.

Personal `~/.claude` config: terse rules, hook-enforced guards, delegation agents, skills.

| Path | Purpose |
|---|---|
| `CLAUDE.md`, `rules/` | Behavior rules (path-scoped rules in `rules/*.md`) |
| `settings.json` | Permissions, hooks, env, sandbox |
| `hooks/` | Shell hooks plus the Python `guard/` (pretool, stop, postedit, compact) and its pytest suite |
| `agents/`, `skills/` | Subagents (scout, worker, shipper, auditors) and skills |
| `mods/`, `tools/`, `output-styles/` | Plugins, helper scripts, `terse` style |
| `cloud-setup.sh` | Installs this config into `~/.claude` in cloud sessions |
| `docs/strictness-audit.md` | Which rules were relaxed, which conflict, what is open |

Guard tests: `cd hooks/guard && python3 -m pytest -q tests`. The suite reads `~/.claude/agents`, so with a fresh HOME copy `agents/` to `$HOME/.claude/agents` first.
