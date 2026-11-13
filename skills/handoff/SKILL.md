---
name: handoff
description: Hand this conversation off to a fresh session that starts working at once, then archive this one. Use when the user says /handoff, "hand off", "continue in a new session", or the context is too long or stale to keep working in.
disable-model-invocation: true
---

Write the handoff note, start a fresh session with it as the brief, then archive this one. The user invoking /handoff is their go-ahead for all three steps.

1. Note, under ~1.5k tokens, no file contents or logs:
   - **Goal**: what the user wants, in their words.
   - **Decisions**: settled choices, so they are not re-asked.
   - **State**: what is done and verified, what is changed but unverified, branch/worktree.
   - **TODO**: every open item, one line each, the in-progress one first and marked.
   - **Pointers**: key paths, commands, session ids.
   Also save it to `~/.claude/handoff/<key>.md` as a backup (`<key>` = `git rev-parse --show-toplevel 2>/dev/null || pwd -W 2>/dev/null || pwd`, every run of non `[A-Za-z0-9_-]` turned into `-`, leading/trailing `-` trimmed). A manual `/clear` still picks it up.
2. `mcp__ccd_session__start_session`: `initiation` "user_asked", `context` "fresh", `use_worktree` false, `model` "claude-sonnet-5-5" (a session can't switch its own model later), a short `title` for the work, `background` = Goal + Decisions, `prompt` = "Handoff from the previous session. Restore the task list from the TODOs and continue the in-progress step now.\n\n" + the full note. Never `hand_off_to_session`: it forks the whole conversation.
3. (Windows box only) If this session is a lead (its id is in `~/.claude/hooks/lead-sessions.txt`, or its first message has the lead role line), start the `prompt` with the line `HANDOFF-ROLE: lead` so context-guard keeps treating the new session as a lead.
4. `mcp__ccd_session_mgmt__detach_session` on the new session, so it lives on its own and survives this one's archive.
5. If workers or background jobs of this session are still running, reply in one line with a link to the new session and wait for them to land (a reply in one line per wake-up). Then, or right away when none are running, reply in one line with the link and call `mcp__ccd_session_mgmt__archive_session` with `session_id` "self".
6. (Windows box only) **Clear mode** (only on an explicit `/handoff clear`): skip steps 2, 4 and 5. Save the note to the file only (role line first for a lead) as the last write before the clear, since a fresh startup takes it only if under 10 minutes old. Then arm the auto-clear mod with `touch ~/.claude/hooks/state/autoclear-$CLAUDE_CODE_SESSION_ID` and end the turn with one line.
7. If `start_session` is refused (Remote Control, or a turn the user didn't type), don't retry and don't stop to ask: switch to clear mode (step 6) once no workers or background jobs of this session are running (until then, one line per wake-up). Say in one line which leg was refused.
