## Coordinator threads
- Don't answer relays with no_reply_needed spam; use it only when a message truly needs no answer.
- Send one status reply at the end, not per step.
- From a remote-control session, send_message uses `session_id: "@parent"` (it may only reach the session that started it); elsewhere take `session_id` from `list_sessions`.
- Put recurring housekeeping briefs in a skill; send one line.
- One hearthbot call ends a turn (each call re-sends context): never post_message then no_reply_needed; batch the end call with the last action.
- No narrative; never relay coordinator/thread messages to Dat. Wrong claim → edit_message (strike + short edit), not a new post.
