---
name: pc-client-context-pack
description: Use for pc_client codebase exploration: find files, routes, symbols, docs, tests, scripts, contracts, CODEMAP entries, context index results, or build a focused context pack before editing.
---

# pc-client-context-pack

## When to use

Use when the task requires finding relevant project context before implementation.

Typical triggers: find where something is implemented, list involved files, build context, search docs, find a route/endpoint/symbol, understand a feature, or find tests for a behavior.

## Inputs

- Task topic.
- Error text, route, symbol, command, feature name, or concept.
- Affected surface if known: `server`, `pc_agent`, `webapp`, `docs`, `scripts`, `deploy`, or `protocol`.

## Workflow

1. Check workspace state:
   - `git status --short`
2. Read routing docs when available:
   - `docs/QUICK_LOOKUP.md`
   - `docs/CODEX_WORKFLOW.md`
   - `docs/CONTEXT_INDEX.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
3. Read relevant CODEMAP files when available:
   - `server/docs/CODEMAP.md`
   - `pc_agent/docs/CODEMAP.md`
4. Build a focused context pack when the project script exists:
   - `python scripts/build_context_pack.py --topic "<task topic>"`
5. Search the context index when the project script exists:
   - `python scripts/search_context_index.py "<symbol route error-code concept>"`
6. Use project search before blind recursive search when the script supports the target:
   - `python scripts/agent_find.py "<pattern>" --dir server`
   - `python scripts/agent_find.py "<pattern>" --dir pc_agent`
7. For `webapp/`, use documented frontend navigation or targeted `rg` until `agent_find.py` supports that directory.
8. If project indexes appear stale, use the documented project rebuild command only if it exists and is safe.
9. Produce a compact context map before editing.

## Rules

- Prefer project search scripts over ad-hoc recursive scanning.
- Do not read the whole repository when targeted context is enough.
- Separate source files, docs, tests, scripts, and deploy surfaces.
- Record which search commands produced useful evidence.
- Do not modify files unless the parent task explicitly requires implementation.

## Verification

Confirm that the context map includes relevant files/docs, likely tests/checks, affected surfaces, and remaining unknowns.

## Final response requirements

Include context commands run, top files/docs found, confidence level, and what was not inspected.
