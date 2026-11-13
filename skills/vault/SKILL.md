---
name: vault
description: Read, search, query and edit the user's Markdown notes vault through the vault MCP tools (notes, tasks, tags, canvases, bases, templates, history). Use when the user mentions their notes, vault, daily note, tasks, projects or canvas, or asks to remember, find or file something in them.
disable-model-invocation: true
---

# Vault

The `vault` MCP server exposes a folder of Markdown notes (Obsidian-compatible). Prefer these tools over guessing paths.

## Find and read
- `vault_search {query}` ranks notes and sections; pass a result address to `vault_get` (`Page`, `Page#Heading`).
- `vault_ctx {name}` gives a project hub: sections, backlinks, open tasks.
- `vault_query {query}` answers "which notes have X": `TABLE status, due FROM "Projects" or #work WHERE status = open SORT due DESC LIMIT 20`.
- `vault_tasks {status, path, tag, due}` lists checkbox tasks with path and line.
- `vault_base_query {path}` runs a `.base` file; `vault_canvas_read {path}` reads a `.canvas`.
- `vault_backlinks`, `vault_tags`, `vault_graph`, `vault_list`, `vault_read`, `vault_all` for structure.

## Edit safely
- Small edits: `vault_patch {path, find, replace}` (find must be unique). Whole file: `vault_write`.
- Your edits appear in the user's app as a reviewable diff (`vault_pending`); the user accepts or rejects hunks. Do not re-apply rejected edits.
- Never delete; `vault_delete` only moves to `.trash`. Undo with `vault_history` then `vault_revert {path, id}`.
- Use `[[wikilinks]]`; `vault_rename` rewrites links. `vault_suggest_links {path}` finds missing links.
- New notes from a template: `vault_templates` then `vault_apply_template {template, path, vars}`.
- Canvas: `vault_canvas_add_node` then `vault_canvas_add_edge` using returned ids.
- Quick capture: `vault_note {title, text}` writes to `inbox/`; `vault_daily {append}` for the daily note.

## Review and context
- `vault_summarize_changes {since}` (ms or ISO date) before recaps; `vault_changes` polls raw changes.
- `vault_comments` / `vault_reply` handle the user's comment threads on selections.
- `open_vault {path}` shows a note in the user's app.

## Prompts
Daily review, Weekly review, Link this note, Turn into flashcards, Clean up inbox are available as MCP prompts.
