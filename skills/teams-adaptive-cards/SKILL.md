---
name: teams-adaptive-cards
description: Author, validate and render Adaptive Cards for Microsoft Teams (bots, message extensions, Copilot agents). Use when building or changing any Adaptive Card JSON or code that emits one, adding card elements (TabSet, Accordion, Carousel, Badge, CompoundButton, ProgressBar, Icon, Rating, Chart), wiring card buttons, or when asked to preview/render what a card looks like.
disable-model-invocation: true
---

# Teams Adaptive Cards

## References (grep the slice you need, never read whole)

| file | use |
|---|---|
| `references/schema-1.5.json` | Core element/property names. Teams desktop, web, mobile target schema 1.5. |
| `references/schema-1.6.json` | What 1.6 adds (Web Chat). Not a Teams target. |
| `references/host-config-schema.json` | Host styling vocabulary: spacing, container styles, font sizes. |
| `references/teams-cards-format.md` | Teams-only behaviour: Markdown subset, newlines, mentions, `msteams.width`, `targetWidth`, overflow menu, borders, scrollable containers, CompoundButton, Icon, Rating, CodeBlock. Grep `^#` headings first. |
| `serve.py`, `designer.html`, `render.mjs` | Teams-look render of any card JSON file by URL (see Render). |
| `render.html` | Open-source renderer, for checking fallbacks. |

Teams-extension elements (TabSet/TabPage, Accordion/AccordionPage, Carousel/CarouselPage, Badge, ProgressBar, ProgressRing, Icon, CompoundButton, Rating, Table, CodeBlock, Chart.*) are not in the 1.5 JSON schema. Props: adaptivecards.microsoft.com `?topic=<Element>` (SPA, read through the browser pane). Key props:

- `TabPage`: title, iconName · `AccordionPage`: headerTitle, headerIconName, isExpanded · `CarouselPage`: items
- `Badge`: text, icon, style Default|Subtle|Informative|Accent|Good|Attention|Warning, appearance Filled|Tint, shape
- `ProgressBar`: value, max, color · `Icon`: name (Fluent catalog), size xxSmall..xxLarge, color
- `CompoundButton`: title, description, icon {name, color}, selectAction

## Rules

- Top-level `version: "1.5"`, `$schema: http://adaptivecards.io/schemas/adaptive-card.json`. One builder function stamps both.
- Every Teams-extension element carries a `fallback` of 1.5 core elements (or `"drop"` only if losing it is fine): TabSet/Accordion/Carousel → Container of stacked Containers with `separator`; CompoundButton → ActionSet with the same action.
- Text: `TextBlock` with `wrap: true`. Markdown only in TextBlock and Fact: bold, italic, lists, links. No headers, tables, images, code, quotes. List lines split by `\r`/`\n`; paragraphs need `\n\n`. Bot message text (not card) also needs blank-line paragraphs — Teams joins single newlines.
- Buttons: `Action.Submit` with a `data.action` discriminator, handled server-side in one dispatcher; unknown values ignored. Ask-as-user-message: `data.msteams = {"type": "imBack", "value": text}`. Universal actions: `Action.Execute` with an `Action.Submit` fallback.
- Action icons `"iconUrl": "icon:<FluentName>"`; element icons `{"type": "Icon", "name": "<FluentName>"}`.
- Images: `data:` URI or a host Teams can reach anonymously.
- Narrow-safe: mobile and meeting side panels truncate. Use `targetWidth` (atLeast:Standard, atMost:Narrow…) before `msteams.width: "Full"`.

## Microsoft design guidance

Sources: adaptivecards.microsoft.com `?topic=design-best-practices` (current, single-page app read through the browser pane) and Learn "Designing Adaptive Cards for your Teams app" (legacy, but its column/text/image rules still hold). The full design system is the Teams UI Kit on Figma Community ("Card Design Toolkit" page).

- **Anatomy:** a clear, short header, then body copy for detail, then 1–3 primary actions (six at most).
- **Pick a layout archetype:** Hero (image-led), Thumbnail (compact action), List (pick an item), Digest (round-up), Media, Form, Quick input, Expandable (more input in the same card).
- **Clarity:** only the details crucial to the context and the actions. Hand complex work off to a dialog or the full app, not a bigger card.
- **Hierarchy:** size, weight, colour and placement make the key message and call to action stand out. Don't give every element equal weight.
- **Interactivity:** few, obvious interactions. Primary buttons only for significant actions (submit, approve, decide). Lesser actions are secondary.
- **Progressive disclosure:** lead with what matters most; reveal the rest through truncation, show more/less, and collapsible sections (Accordion, `Action.ToggleVisibility`).
- **Responsive:** there are four breakpoints (very narrow, narrow, standard, wide); validate every one and use `targetWidth` for per-width layouts. Design narrow-first, since narrow scales up but wide doesn't scale down. Mobile has no horizontal scroll.
- **Columns:** `wrap: true` on every TextBlock. Don't make every column `auto`. Make the button/icon column `auto` and the content column `stretch`. Use `px` widths only for fixed things like thumbnails and numbers. Fewer columns read better on mobile.
- **Containers:** only to emphasise (`style`), to make a group clickable (`selectAction`), or to make it collapsible.
- **Accessibility:** text contrast of at least 4.5:1; you are responsible for it over background images. Avoid fixed background colours unless they carry meaning.
- **Images and illustrations:** transparent PNG at 2x, no padding, no shadows, neutral colours that work in light and dark themes. Custom monochrome icons use #818181. Prefer catalog Icons, which theme themselves.
- **Dates:** use the `{{DATE()}}`/`{{TIME()}}` functions so they follow the user's locale.
- **Frequency:** be concise and send few cards; ones that scroll away lose value, and channels tolerate less noise.

- **Badges:** `Accent` + `Tint` washes out in Teams dark (pale text on a pale tint). Use `Informative` or `Default` with `Tint` for labels; `Accent` + `Filled` only when one badge must shout.
- **Overflow menu** (`"mode": "secondary"`): don't split a small set, with one action showing and two hidden. Either all show as buttons, or all go behind one "…". For a top-right menu, put an `ActionSet` whose actions are all secondary in an `auto` column next to the heading. On a bot card, root-level `actions` don't get a top-right "…"; only message-extension cards do.

## Layout idioms

- Side by side = `ColumnSet`; content `width: "stretch"`, icon/button `width: "auto"` + `verticalContentAlignment: "Center"`.
- Group = `Container` `style: "emphasis"`; section break = `separator: true` + `spacing: "Large"`.
- Secondary text = `isSubtle: true, size: "Small"`; tight stacking = `spacing: "None"|"Small"`.
- Mixed bold/plain on one line = `RichTextBlock` of `TextRun`s.
- Many items: Accordion (scan titles, open one) over Carousel (one at a time); first page `isExpanded: true`.

## Render for preview (always, before calling a card done)

**Never hand-type card JSON into the browser.** Write the card to a file from the code that builds it (a preview script that calls the real builder with sample data), then render that file by URL. Hand-written preview files drift from the code; this repo deleted its two after they hid a missing fallback.

**Teams look, one line.** Start the static server once: `python serve.py <repo root> 8765` (in this repo, the `card-render` entry in `.claude/launch.json` via `preview_start`). Then navigate the browser pane to:

    http://localhost:8765/.claude/skills/teams-adaptive-cards/designer.html?card=/<path/to/card.json>&theme=dark

Add `&width=320` for a narrow card. The page loads the Designer's own renderer bundle (`main.bundle.js` plus its four lazy chunks, listed in `render.mjs`) from adaptivecards.microsoft.com, and `render.mjs` draws the card full-page with the Teams web host config and Fluent theme. To re-render in the same tab: `await render("/path.json", {theme: "light"})`. Screenshot after about 4s. The card is interactive, so click accordion headers and tabs to check each state. Render both themes. If the renderer fails after a Microsoft redeploy, the chunk ids changed: on the hosted Designer, list `performance.getEntriesByType("resource")` names ending in `.main.bundle.js` and update `DESIGNER_CHUNKS`.

Why this shape:
- The browser pane blocks the hosted Designer page from fetching localhost (`ERR_BLOCKED_BY_CLIENT`), so the local page loads Microsoft's bundle instead.
- `serve.py` maps `.mjs` to JavaScript, which Python's default server doesn't.
- Without the Fluent provider, fills render transparent, so a ProgressBar looks empty.
- Without the host config, a dark render keeps a white card.

In this repo: queue `gate run {command: card_previews}`. It runs `agents/hosted/scripts/card_previews.py`, which writes `welcome.json`, `answer.json` and `watch-list.json` to `teams/strategy-compass/cards/` from `teams_card.py`.

Two other renders answer different questions:

**Fallback check.** Open `render.html` (this folder) in the browser pane, then `javascript_tool`: `renderCard(<json>)` → `{shown, warnings}`, then screenshot. It loads the open-source `adaptivecards@3` renderer from unpkg. That renderer draws core 1.5 elements and Carousel, renders the `fallback` for Accordion, and silently drops Badge, ProgressBar, Icon and the other Teams-only elements. Use it to prove every fallback carries the content; it is not the Teams look.

**Human preview in VS Code.** The Microsoft extension "Adaptive Card Previewer" (`TeamsDevApp.vscode-adaptive-cards`) previews a card `.json` file with the Teams light, dark and high-contrast themes. It is for the user to look at; the agent can't drive it, so point the user at the preview file. Confirmed in practice: it draws neither TabSet nor Accordion. It shows their `fallback`, and an element with no fallback simply vanishes. Use it to check fallbacks only. For the Teams look, use the one-line render or real Teams. The hosted Designer's own canvas and its **Preview** dialog are poor targets too: the canvas is cramped in a narrow pane, and the Preview dialog silently drops Accordion.

## Workflow for a change

1. Test first: assert structure (types, fallback present, action data), not layout.
2. Build from small helpers (text, badge, auto column, box, submit); reuse before adding.
3. New element type → check name/props, add fallback.
4. Regenerate the preview files from the builder; never edit them by hand.
5. Render (above), then run the repo's gates.
