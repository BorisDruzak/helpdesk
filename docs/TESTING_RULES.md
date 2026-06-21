# Testing Rules

Canonical testing flow for `pc_client`.

For Live validation, debugging, Protocol V3, browser/admin UI, local agent GUI, account-session, operation lifecycle, module runtime or deployment/runtime-control bugfix work, also follow `docs/LIVE_TESTING_DEBUG_RULES.md`. That document is the stricter source for evidence, validation surfaces, contamination and milestone final gates.

## Always

Run this before committing code or docs:

```powershell
python scripts/verify_workspace.py
```

Then run the narrowest pytest/browser layer that covers the files you changed.

## Server Pytest Layers

Use these layers instead of the old single long `server/tests` run when you need signal quickly:

```powershell
python -m pytest server/tests -m "not manual and no_db" -vv --durations=80
python -m pytest server/tests/test_knowledge_*.py -m "not manual and not no_db and not agent_ws" -vv --durations=80
python -m pytest server/tests/test_ticket_*.py server/tests/test_helpdesk_*.py -m "not manual and not no_db and not agent_ws" -vv --durations=80
python -m pytest server/tests -m "not manual and agent_ws" -vv --durations=80
```

Layer meanings:

- `no_db`: pure unit/contract checks that must not require PostgreSQL setup or cleanup.
- DB/API domain layers: DB/API/server contract tests without the in-process WS agent, split by filename into knowledge, tickets/helpdesk, observer/diagnostics, agent runtime, and web/API catch-all layers by `scripts/run_ci_suite.py`.
- `agent_ws`: tests that use the in-process WS agent runtime. This marker is auto-applied to tests that request the `test_agent` fixture.

Pure server tests that do not request `test_client`, `test_app`, `test_engine`, `patched_get_session`, `test_database_url`, `test_database_admin_url` or `run_migrations` should set module-level `pytestmark = pytest.mark.no_db`. This keeps them out of the DB/API layer and avoids paying the migration/cleanup cost for tests that do not touch PostgreSQL.

The full local CI runner executes these same layers. It is an important final release checkpoint, but Codex should run it only after explicit user request or confirmation:

```powershell
python scripts/run_ci_suite.py
```

To run a single canonical layer:

```powershell
python scripts/run_ci_suite.py --layer server_pytest_db_knowledge
python scripts/run_ci_suite.py --layer webapp_unit_tests
python scripts/run_ci_suite.py --layer webapp_fixture_e2e
python scripts/run_ci_suite.py --layer pc_agent_pytest
```

## Agent Pytest

Run agent tests after changes under `pc_agent/`:

```powershell
python -m pytest pc_agent/tests -m "not manual" -vv --durations=80
```

For tray/runtime/update work, also run the focused file named by the relevant playbook, for example:

```powershell
python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q
```

## Webapp

Before frontend commands in `webapp/`:

```powershell
python scripts/bootstrap_web_toolchain.py
```

For React/admin/support changes:

```powershell
pnpm --dir webapp run test
pnpm --dir webapp run build
pnpm --dir webapp run test:e2e -- admin-workspace.spec.ts
```

Use the in-app browser for live UI checks on the canonical stand origin:

```text
https://192.168.100.17:9443
```

Route selection must match the changed surface: `/admin` for admin/tech-panel, `/app/*` for React workspaces, and `/app/requester`, `/app/requester/devices`, or `/app/device/*` for web-first requester/web-agent checks.

## CI Diagnostics

`scripts/run_ci_suite.py` uses:

- 45 minutes per server pytest layer.
- The configured idle timeout for all CI steps, including server and pc_agent pytest layers.
- `-vv --durations=80` for each server layer.
- `PC_CLIENT_PYTEST_WATCHDOG_SECONDS=120` for server pytest.
- `PC_CLIENT_TEST_TIMING=1` and `PC_CLIENT_TEST_TIMING_PATH=artifacts/ci/<sha>/fixture-timings/<layer>.jsonl` for server pytest layers.
- `CI=1` for webapp unit and Playwright fixture E2E layers, so Playwright keeps retry traces instead of running with trace collection effectively disabled.

If a test runs longer than the watchdog value, `server/tests/conftest.py` prints all Python thread stacks into the pytest log. This is meant to make the next timeout actionable: the log should show the current test and stack traces, not just a killed process.

Fixture timing is opt-in outside `run_ci_suite.py`. To profile a focused server pytest run without changing test behavior:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_TIMING_PATH = "artifacts/ci/manual/fixture-timings/focused.jsonl"
python -m pytest server/tests/test_web_support_api.py -m "not manual and not no_db and not agent_ws" -q
python scripts/summarize_fixture_timings.py artifacts/ci/manual
```

The summary is written to `artifacts/ci/<sha>/fixture-timings-summary.json` and printed as a table with `total`, `count`, `avg`, `p50`, `p95`, and `max` per fixture phase. Current measured phases are `run_migrations/setup`, `cleanup_db/setup`, `_cleanup_db_async/call`, `test_app/setup`, `test_app/teardown`, `test_client/setup`, `test_client/teardown`, `test_agent/setup`, and `test_agent/teardown`. Some timings are nested, so do not sum every row as a single wall-clock total; use the rows to identify which fixture phase should be optimized next.

On Windows shared-test-DB fallback, the harness tries `pg_terminate_backend` once. If admin privileges are unavailable, it caches that fact for the pytest session and skips repeated terminate attempts; per-test `TRUNCATE ... RESTART IDENTITY CASCADE` still provides cleanup.

On Windows default DB-backed pytest, the harness opens the configured SSH tunnel and creates an isolated `pc_support_test_<domain>_<pid_or_worker>_<short_hash>` database through `TEST_DATABASE_ADMIN_URL` semantics. `run_ci_suite.py` passes the CI layer name as `PC_CLIENT_TEST_DB_DOMAIN`, and `--keep-test-db` keeps isolated DBs for debugging. Shared `pc_support_test` is for explicit fallback/debug only (`PC_CLIENT_ALLOW_SHARED_TEST_DB=1`) or automatic fallback when the admin database cannot be reached; any shared fallback warning means the run is not valid for the full DB/API gate.

## When To Run What

- Docs-only or script metadata: `python scripts/verify_workspace.py` plus the matching `scripts/test_*.py`.
- Server API/handler/repo/schema behavior: server DB/API layer, plus focused files for the touched area.
- WebSocket, `run_tool`, outbox, in-process agent, UI realtime: server `agent_ws` layer.
- Agent runtime, launcher, tray, local UI bridge: focused `pc_agent/tests/*`, then live local agent status if runtime behavior changed.
- Admin/support web UI: focused server API tests, `pnpm --dir webapp run build`, relevant Playwright spec, then browser check.
- Iterative staging deploy: focused local verification for the touched area, then `python scripts/release_server_to_remote.py --gate quick`, remote smoke, and browser/live checks when the UI/runtime changed. Quick gate skips only the green full-CI artifact requirement.
- Final release checkpoint by explicit request: full `python scripts/run_ci_suite.py`, `python scripts/release_server_to_remote.py --gate full` or the default gate, remote smoke, and browser/live agent checks. Routine GitHub pushes do not wait for this checkpoint.

Do not raise timeouts as the first response to slow tests. First look at `--durations=80`, split the layer if needed, and optimize repeated heavy fixture setup such as `test_agent`.
