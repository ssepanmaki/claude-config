---
name: interview
description: Interview the user about requirements before planning a non-trivial change
---

Analyze these requirements: "$ARGUMENTS". Then interview me with AskUserQuestion about non-obvious things only: technical approach, UX, edge cases, tradeoffs, risks. Skip anything answerable from the code.

Rules:
- Batch related questions (up to 4 per call); stop when the remaining unknowns would not change the plan.
- Put the recommended option first, append "(Recommended)" and say why in its description.
- Ask in the language I wrote the request in.
- When done, summarize decisions in a short list and proceed in plan mode.
