---
name: fix-ci
description: Fix failing CI on the current branch's PR. Use for fix CI, checks failing.
---
Find the failing job with the GitHub MCP tools, read its log, reproduce locally, fix the cause (never skip or disable tests), then commit and push per owner rules.
