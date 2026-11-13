---
paths:
  - "**/*.html"
  - "**/*.css"
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.vue"
  - "**/*.svelte"
---
- Agent UI work: lead runs `tools/review.mjs` on every screen (no thumbnails/UNSETTLED): FAIL → fix from the text, no look; look once only at PASS shots that are new/changed, then `--approve`; "same as approved" → never look, unless the project delegates screens (e.g. `shot-reviewer`); bare HTML `dsguard.mjs`.
