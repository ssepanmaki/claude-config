---
name: review
description: Review the current diff against this config's quality, security and verification rules
---

Review `git diff` (staged and unstaged) and report, most severe first:
1. Correctness bugs and unhandled errors.
2. Security: secrets, injection, unvalidated input, unsafe shell/SQL.
3. Missing or weakened tests (skipped, deleted, loosened assertions).
4. Scope creep: unrelated refactors or formatting.
5. Simplifications and reuse of existing helpers.

For each finding give file:line, the failure scenario, and a fix. If nothing is wrong, say so; do not invent findings. Run the project's tests/lint first and include real output for failures.
