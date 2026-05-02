# Context Index

`Context Index` is a deterministic local retrieval layer for `pc_client`. It helps Codex and the developer find relevant canonical docs, CODEMAP sections, navigation topics, routes and symbols faster.

It is not a source of truth. The source of truth remains:

- `AGENTS.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/QUICK_LOOKUP.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- profile docs next to the affected code

## Commands

Build or rebuild the index:

```powershell
python scripts/build_context_index.py --force
```

Search:

```powershell
python scripts/search_context_index.py "run_tool command_result observer"
python scripts/search_context_index.py "handshake token machine_id" --json
python scripts/search_context_index.py "ToolExecutionService run_tool" --kind symbol
python scripts/search_context_index.py "/api/web/admin/modules preferred" --kind route
python scripts/search_context_index.py "run_tool" --profile route
python scripts/search_context_index.py "command_result retry" --profile test --kind test
```

The search command auto-builds the index if it is missing. Use `--no-build` to fail instead. If indexed sources changed after the last build, search prints a stale-index warning and still returns results; rebuild with `python scripts/build_context_index.py --force` before relying on those results.

Context packs include a compact `Context Index Results` section:

```powershell
python scripts/build_context_pack.py --topic "run_tool command_result"
```

## Storage

Generated index:

```text
artifacts/context_index/pc_client.sqlite
```

This is a generated artifact and should not be committed.

## Indexed Sources

The index includes:

- canonical markdown docs from `docs/`, `server/docs/`, `pc_agent/docs/`;
- `AGENTS.md` and `PLANS.md`;
- CODEMAP sections as markdown chunks;
- `scripts/navigation_catalog.py` topics and their aliases/files/checks;
- aiohttp routes from `server/routes.py`, including handler metadata where the route line exposes it;
- top-level Python classes/functions and class methods from `server/`, `pc_agent/`, `shared/`, `scripts/`;
- pytest-style test functions/classes from `server/tests/`, `pc_agent/tests/` and other indexed test paths;
- lightweight TypeScript/TSX symbols from `webapp/src/`.

The index excludes:

- `.git/`;
- `.venv/`, `venv/`;
- `node_modules/`;
- `__pycache__/`;
- `build/`, `dist/`;
- `artifacts/`;
- archived docs and task-specific `docs/superpowers/*` plans/specs, except the root `PLANS.md`.

## Search Model

The primary search engine is SQLite FTS5. If FTS5 is unavailable in the local Python build, the scripts fall back to deterministic `LIKE` matching. No embeddings, GPU, network access or external services are required.

Result kinds:

| Kind | Meaning |
|---|---|
| `doc` | Markdown heading chunk from canonical docs |
| `topic` | `navigation_catalog.Topic` metadata |
| `route` | aiohttp route registered in `server/routes.py`; rendered as `METHOD /path -> handler` when known |
| `symbol` | Python or TypeScript symbol |
| `test` | pytest-style test function/class |

Ranking profiles:

| Profile | Use for |
|---|---|
| `default` | General intake and ordinary navigation |
| `debug` | Root-cause work where tests, CODEMAP and observer/runtime docs should surface sooner |
| `contract` | Boundary/API/protocol/security/observer changes |
| `route` | Finding HTTP routes and their handlers |
| `test` | Finding existing tests and likely regression anchors |
| `web` | Web UI, admin UI, static assets and route-facing frontend work |

## Workflow

Use the context index after the normal intake step:

```powershell
python scripts/task_intake.py --task "<task>"
python scripts/build_context_pack.py --topic "<task>"
python scripts/search_context_index.py "<symbols, routes, error codes or concepts>"
```

This is the standard retrieval step in `docs/CODEX_WORKFLOW.md` and `docs/QUICK_LOOKUP.md`. It should happen before broad manual searches, because it searches canonical docs, CODEMAP chunks, `navigation_catalog` topics, routes and symbols in one pass.

For debugging, prefer:

```powershell
python scripts/search_context_index.py "<error symbol event>" --profile debug
python scripts/search_context_index.py "<feature behavior>" --profile test --kind test
```

For contract or route work, prefer:

```powershell
python scripts/search_context_index.py "<protocol api observer>" --profile contract
python scripts/search_context_index.py "<route or path fragment>" --profile route --kind route
```

Good queries are specific:

- `run_tool command_result operation_id`
- `outbox_ack device_seq agent_seq`
- `module manifest preferred version`
- `observer dangerous flow action_trace`
- `TOKEN_LIMIT_EXCEEDED connection_request`

Weak queries such as `fix server` or `admin page` will return broad results. Start with `task_intake` first, then search for concrete symbols or contract terms.

## Freshness Rules

Rebuild the index when:

- docs or CODEMAP changed;
- `scripts/navigation_catalog.py` changed;
- `server/routes.py` changed;
- key Python/TypeScript files were added, removed or renamed;
- search results look stale.

Recommended rebuild:

```powershell
python scripts/build_context_index.py --force
```

Recommended cadence:

| Situation | Action |
|---|---|
| Starting a normal task | Use `python scripts/search_context_index.py "<query>"`; it auto-builds if the index is missing |
| Starting with a broad task | Use `python scripts/build_context_pack.py --topic "<task>"`; it includes the top context-index hits |
| After switching branches or pulling changes | Run `python scripts/build_context_index.py --force` |
| After editing docs, CODEMAP, routes, navigation metadata or public symbols | Run `python scripts/build_context_index.py --force` before relying on results |
| Search prints a stale-index warning | Rebuild with `python scripts/build_context_index.py --force`, then repeat the search |
| Before a commit that changes index rules/scripts/docs | Run focused context-index tests and rebuild once |
| During debugging | Rebuild only if the code/docs changed since the last index build; otherwise search repeatedly |

Before commit, generated SQLite files stay unstaged:

```powershell
git status --short
```

Do not commit:

```text
artifacts/context_index/*
```

## Testing

Focused tests:

```powershell
python -m pytest scripts/test_context_index.py scripts/test_build_context_pack.py -q
```

Navigation/docs checks:

```powershell
python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py -q
python scripts/docs_inventory.py --check-links
python scripts/verify_workspace.py
```
