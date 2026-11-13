---
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.bicep"
  - "**/*.bicepparam"
  - "**/pyproject.toml"
  - "**/package.json"
  - "**/requirements.txt"
  - "**/Dockerfile"
  - "**/.github/workflows/*"
---

## Engineering rules — non-negotiable

- **Clean Code** (Martin): small functions, meaningful names, no flag args, prefer pure.
- **Comments**: none that restate code or narrate changes. One short line for a non-obvious *why* (hidden constraint, workaround) or a link to an external bug/spec is fine; public API docstrings required.
- `src/` + deployed = permanent surface; one-off → `scripts/` or attc, deleted after.

Single-owner platform, no external users.

- **No backward compat**: no shims, aliases, old+new paths, `try/except ImportError`. Rename = update every callsite.
- **Delete, don't salvage** unless blast radius genuinely wide.
- **No change narration** in code.
- **Contracts first**: one responsibility per unit, typed public signatures (no `Any`/bare `dict`/`list`), validate at boundary, TypedDict at parse boundary. `__all__` only in libraries.
- **Gated coding**: gate once per finished unit, scoped to the diff, never per edit. **gated-coding** skill for non-trivial change: `gate {op: ruff|ruff_fix|ruff_format, repo}` (never push to learn lint), then mypy/pytest serial; TS `gate {op: npm, script}`. Few-line fix → one `ruff` on changed files + `pytest` of touched test file in one chain; mypy only when signatures changed, always with `paths`. Pre-push: `gate {op: ci_steps, repo}` (derived from workflows + diff; `git push` refuses without its pass); no generic sweeps for areas the diff can't affect. The daemon refuses whole-repo ruff/mypy/pytest and a 4th gate in 10 min per session. Gate cost must never dwarf the edit. CI red after local green → local ≠ CI: name the differing step, reproduce locally, fix; two reds on one change → stop, write cause + differing step before a third push. Runnable app → `.claude/launch.json` + `preview_start`. Report done only with gate results.
- **Engineer first**: read the flow, make the whole change, then gate. Docs: edit only what the change made wrong; no new doc pages per job.
- **Same edit in ≥5 files → one pass** (codemod, `ruff_fix`, eslint `--fix`, `vault bulk`), never N Edits.
- **UI offset/layout bug**: import-trace the rendering component (codegraph) before the first edit; one hypothesis, one edit, then look.
- **One home per setting kind**: per-user → preference JSON; runtime switch → bicep + app setting; history → table. Env-var-only switch = bug.
- **Newer run cancels older**: workflows get `concurrency` with `cancel-in-progress: true` (deploys too).
- **Code recon**: attc `code_xray` for repo audits; `who_calls` before signature change/delete.
- **Gates are floor**: ruff + mypy strict. No `noqa`/`type: ignore`/`cast`/`Any` to silence; sole exception documented third-party gap at narrowest scope.
- **Packaging**: `src/` layout, `pyproject.toml` single source, `hatch-vcs` for libraries, dev deps in `[dependency-groups]`. Never name a package after a PyPI package.
- **Config**: one `pydantic-settings` model at root, no `os.environ` elsewhere, required secrets `Field(...)` no defaults, `SecretStr`. Managed identity → WIF → Key Vault; stored secret last resort.
- **Errors**: narrowest catch, `raise ... from exc`, timeout on every I/O call, retries only transient+idempotent with backoff+jitter. `AppError` root with `retryable`. Never swallow `CancelledError`.
- **Auth**: no client construction at import (lazy `@lru_cache` + `reset_caches()`); missing principal → 401, never shared default.
- **Concurrency**: never block the event loop (`asyncio.to_thread`), `TaskGroup`, bounded fan-out.
- **Data**: parameterised, bounded queries; `with session.begin()`; async `expire_on_commit=False` + `selectinload`; idempotency key + `ON CONFLICT DO NOTHING`; outbox not dual-write; Alembic with `lock_timeout`; never hand DDL on shared DBs.
- **Security**: no `shell=True` with input, no `pickle`/`yaml.load`/`eval` on external data, user paths resolved + base-checked, no md5/sha1 for security; bandit + pip-audit + secret scan in CI.
- **Logging** structured, no `print`, no secrets/bodies; correlation id via contextvars.
- One deploy manifest. Never two mypy/pytest runs on one cache dir.
- **Hunting mode**: flag dead code, duplication, SDK drift (check site-packages); fix only when asked or in touched code.
- **Infra deploys**: before any deploy-infra dispatch, pull the live VNet/subnets and diff against the bicepparams; any network delta stops the dispatch and gets fixed in bicep, never routed around.
