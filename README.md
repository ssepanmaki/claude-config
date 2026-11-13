# claude-config

Personal Claude Code config: global rules, permissions, safety hooks and a few skills.

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Global rules: hard rules for verification, git, security; relaxed defaults for style |
| `settings.json` | Permissions (allow / ask / deny) and hook wiring |
| `hooks/guard-bash.sh` | Blocks `rm -rf /`, force/main pushes, `--no-verify`, `curl \| sh`, destructive SQL |
| `hooks/guard-secrets.sh` | Blocks writing `.env`/key files or credential-looking strings |
| `skills/interview`, `skills/review` | Requirements interview; diff review against these rules |
| `docs/strictness-audit.md` | Which rules in the other repo are too strict, and what was adopted |

Install: `./install.sh` (symlinks CLAUDE.md and skills into `~/.claude`, writes `settings.json.new` for you to merge).
Hooks need `jq`. Used as a project config instead, `settings.json` works as `.claude/settings.json` as-is.
