---
name: ship
description: Check, commit and push following the owner's rules. Use for ship, commit and push, open a PR.
---
1. Run the repo check script (precheck/test/lint in package.json); fix failures.
2. On main, master or claude/*: create a <type>/<short-topic> branch.
3. Commit: one short Conventional Commit line, no trailers.
4. git push -u origin <branch>. Open a PR only if asked: summary + how tested, no footer.
