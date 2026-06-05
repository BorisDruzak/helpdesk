---
name: pc-client-context-pack
description: Use when Codex needs to find pc_client files, routes, symbols, docs, tests, scripts, contracts, CODEMAP entries, or build a focused context pack before editing.
---

# pc-client-context-pack

## When to use

Use when finding project context, routes, symbols, tests, docs, scripts, contracts, or CODEMAP entries. Use before broad recursive reading.

## Inputs

- Task topic or bug summary.
- Search terms: symbol, route, error code, file name, concept, protocol message.
- Relevant ownership area: `server`, `pc_agent`, `webapp`, docs, scripts, or contracts.

## Workflow

1. Start from navigation docs:
   - `docs/QUICK_LOOKUP.md`
   - `docs/CONTEXT_INDEX.md`
2. Build a focused context pack:
   - `python scripts/build_context_pack.py --topic "<task topic>"`
3. Search indexed context:
   - `python scripts/search_context_index.py "<symbol route error-code concept>"`
4. If the index reports stale results, rebuild with:
   - `python scripts/build_context_index.py --force`
5. Use targeted source search:
   - `python scripts/agent_find.py "<pattern>" --dir server`
   - `python scripts/agent_find.py "<pattern>" --dir pc_agent`
6. Read relevant CODEMAP files:
   - `server/docs/CODEMAP.md`
   - `pc_agent/docs/CODEMAP.md`
7. For `webapp/`, use `rg` or documented frontend navigation because `agent_find.py --dir webapp` is not a supported option unless the script is extended.

## Verification

Confirm:

- Search output points to concrete files or docs.
- The search scope is narrow enough for the task.
- Stale index warnings are either resolved or explicitly recorded when the task is read-only.

## Final response requirements

Report:

- relevant files
- relevant docs
- symbols/routes/contracts found
- tests/checks likely needed
- unknowns or stale-index limitations
