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
python -m pytest server/tests/test_ticket_*.py server/tests/test_helpdesk_*.py -m "not manual and not no_db and not agent_ws" -vv --durations=80
python -m pytest server/tests/test_migration_schema_contract.py -m "not manual and not no_db and not agent_ws" -vv --durations=80
python -m pytest server/tests -m "not manual and agent_ws" -vv --durations=80
```

Layer meanings:

- `no_db`: pure unit/contract checks that must not require PostgreSQL setup or cleanup.
- `migration_schema`: fresh PostgreSQL Alembic contract for empty-DB upgrade, exact heads, idempotent upgrade, actual schema cleanup audit, required constraints/indexes/defaults and smoke DML. This layer must run with template DB disabled.
- DB/API domain layers: DB/API/server contract tests without the in-process WS agent, split into tickets/helpdesk, observer/diagnostics, agent runtime, and web/API catch-all layers by the canonical `quality/test_suites.toml` catalog. `scripts/run_ci_suite.py` and `scripts/audit_test_inventory.py` load the same catalog for filename ownership, affected-suite source-prefix routing, layer order and DB/WS parallel grouping.
- `agent_ws`: tests that use the in-process WS agent runtime. This marker is auto-applied to tests that request the `test_agent` fixture.

Pure server tests that do not request `test_client`, `test_app`, `test_engine`, `patched_get_session`, `test_database_url`, `test_database_admin_url` or `run_migrations` should set module-level `pytestmark = pytest.mark.no_db`. This keeps them out of the DB/API layer and avoids paying the migration/cleanup cost for tests that do not touch PostgreSQL.

The full local CI runner executes these same layers. It is an important final release checkpoint, but Codex should run it only after explicit user request or confirmation:

```powershell
python scripts/run_ci_suite.py
```

The runner is sequential by default. The temporary-workspace full-CI wrapper always uses bounded layer-level
parallelism with two workers. For a direct server DB/WS runtime measurement or an explicit CI-speed check, use the
same bounded mode instead of `pytest-xdist`:

```powershell
python scripts/run_ci_suite.py --parallel --max-workers 2
python scripts/run_ci_suite.py --parallel --max-workers 2 --layer server_pytest_db_agent_runtime --layer server_pytest_agent_ws
python scripts/run_ci_suite.py --parallel --parallel-measurements artifacts/ci/<sha>/fixture-timings-summary.json
```

`--parallel` only groups independent server DB/WS pytest layers. The runner still keeps `verify_workspace`,
webapp build/unit/e2e, and `server_pytest_no_db` sequential before the group, then keeps `pc_agent_pytest`
sequential after it. A single requested DB/WS layer remains sequential. Start with `--max-workers 2`; values above `3`
are allowed but risky until the remote PostgreSQL and SSH tunnel behavior is proven stable.

On Windows, parallel DB/WS mode is guarded against child pytest processes owning a shared DB tunnel. If
`TEST_DATABASE_ADMIN_URL` is already set, the runner uses it. Otherwise, it reuses an already-open
`PC_CLIENT_TEST_DB_TUNNEL_HOST:PC_CLIENT_TEST_DB_TUNNEL_PORT` tunnel or starts one parent-owned SSH tunnel and passes
`TEST_DATABASE_ADMIN_URL` to the child pytest processes. The parent closes only the tunnel it started.
For CI, prefer leaving the configured local tunnel port free so the runner owns the tunnel lifecycle; reusing an
already-open tunnel is a compatibility path and the runner cannot keep that external process alive.

`run_ci_in_temp_workspace.py` always enables the stricter parent-owned policy for a full gate. It accepts either an
explicit `TEST_DATABASE_ADMIN_URL` supplied by the protected runner environment, or a parent-owned tunnel configured
with `PC_CLIENT_TEST_DB_SSH_TARGET` (and the associated runtime-only tunnel settings). It rejects an already-open
external tunnel instead of silently depending on it, starts the owned tunnel before the migration layer, and closes it
when the gate ends. Configure those values in the approved secret channel or runner profile; never put connection
credentials in a command line, repository file, or CI artifact.

Parallel layer output is intentionally high-level in the terminal; detailed pytest output remains in each
`artifacts/ci/<sha>/logs/<layer>.log`. `summary.json` preserves the `steps` list and adds `parallel_enabled`,
`max_workers`, and `parallel_groups` metadata. When `--parallel-measurements` is supplied, the runner reads a prior
`fixture-timings-summary.json`; if its `budget_status` is `fail`, the effective worker count is capped at 1 and DB/WS
layers run sequentially until timings recover. The decision is recorded as `summary.parallel_measurement_decision`.

To run a single canonical layer:

```powershell
python scripts/run_ci_suite.py --layer server_pytest_db_tickets
python scripts/run_ci_suite.py --layer test_inventory_audit
python scripts/run_ci_suite.py --layer db_cleanup_profile_audit
python scripts/run_ci_suite.py --layer fixture_builder_audit
python scripts/run_ci_suite.py --layer active_risk_audit
python scripts/run_ci_suite.py --layer observer_contamination_audit
python scripts/run_ci_suite.py --layer branch_coverage_audit
python scripts/run_ci_suite.py --layer mutation_smoke
python scripts/run_ci_suite.py --layer migration_schema
python scripts/run_ci_suite.py --layer scripts_pytest_no_db
python scripts/run_ci_suite.py --layer webapp_unit_tests
python scripts/run_ci_suite.py --layer webapp_fixture_e2e
python scripts/run_ci_suite.py --layer pc_agent_pytest
```

For a fast affected-suite PR gate, provide explicit changed paths or a git base ref:

```powershell
python scripts/run_ci_suite.py --changed-path server/domain_ports/knowledge.py
python scripts/run_ci_suite.py --affected-from origin/main
```

Affected-suite summaries use `gate_mode=affected`, list `effective_layers`, and set `full_merge_gate_required=true` unless the full canonical layer list actually ran green. They are fast PR evidence only: deploy/release preflight rejects affected or `--layer` summaries as full merge-gate artifacts. Run plain `python scripts/run_ci_suite.py` on the frozen commit for the required full merge gate.

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
https://example.test:9443
```

Route selection must match the changed surface: `/admin` for admin/tech-panel, `/app/*` for React workspaces, and `/app/requester`, `/app/requester/devices`, or `/app/device/*` for web-first requester/web-agent checks.

## CI Diagnostics

`scripts/run_ci_suite.py` uses:

- 8 hours per DB-backed or agent-WS server pytest layer. Measured parallel isolated staging PostgreSQL profiles can exceed the former four-hour limit; the separate idle timeout and fixture-timing budget gates remain active. Audits, mutation smoke, script pytest and the no-DB server layer retain their 45-minute fail-fast ceiling.
- The configured idle timeout for all CI steps, including server and pc_agent pytest layers.
- `-vv --durations=80` for each server layer and `pc_agent_pytest`.
- `PC_CLIENT_PYTEST_WATCHDOG_SECONDS=120` for server pytest.
- `PC_CLIENT_TEST_TIMING=1` and `PC_CLIENT_TEST_TIMING_PATH=artifacts/ci/<sha>/fixture-timings/<layer>.jsonl` for server pytest layers.
- `PC_CLIENT_TEST_DB_TEMPLATE=1` for DB/WS server pytest layers, so isolated layer databases are cloned from a migrated PostgreSQL template keyed by the Alembic migration fingerprint. The `migration_schema` layer is the exception and forces `PC_CLIENT_TEST_DB_TEMPLATE=0` to prove the direct empty-DB Alembic path.
- `CI=1` for webapp unit and Playwright fixture E2E layers, so Playwright keeps retry traces instead of running with trace collection effectively disabled; fixture E2E has one CI retry and records first-attempt failures as flaky evidence, not clean green.
- `quality/flaky_registry.json` is the only allowlist for retry-pass records. `webapp_fixture_e2e` writes `playwright-webapp-fixture-e2e.json`, and `summary.flaky_summary` records `passed_after_retry` node ids, first/final status, worker indexes, previous error and trace/video/log attachments. Unknown or invalid retry-pass records turn the CI summary red instead of being treated as clean green.
- `summary.evidence_layers.webapp_fixture_e2e` marks Playwright fixture E2E as `mode=fixture_e2e` and `canonical_live_browser=false`; it is CI browser-fixture coverage, not live browser signoff evidence.
- `summary.gate_mode`, `summary.effective_layers`, `summary.full_merge_gate_required` and `summary.full_merge_gate_satisfied` distinguish full, selected and affected-suite runs. Release/preflight consumers accept only green full merge-gate artifacts.
- `summary.baseline_artifacts` records canonical JUnit XML paths, pytest duration baselines, fixture timing artifacts and fixture E2E retry policy for release/preflight consumers.
- `quality/test_suites.toml` is the canonical CI/test-suite catalog. The runner fails on layer-order/catalog drift, and the inventory audit uses the same catalog for server DB/API ownership instead of maintaining a second routing table.
- `fixture-timings-summary.json` includes the default fixture timing budget result: `budget_profile`, `budget_status` and `budget_violations`.
- `test_inventory_audit` runs `python scripts/audit_test_inventory.py --strict` before pytest layers and fails on unknown pytest markers, `no_db` tests that request DB/app fixtures, unowned DB/app tests, or direct live/network client calls in non-`manual` PR suites.
- `db_cleanup_profile_audit` runs `python scripts/audit_db_cleanup_profiles.py --strict` before pytest layers and fails on DB-backed, non-agent-ws server test files without an explicit `db_cleanup` profile.
- `fixture_builder_audit` runs `python scripts/audit_fixture_builders.py --strict` before branch/mutation gates and fails when `quality/fixture_builders.json` or registered fixture/data packs drift from their JSON Schema builders, source-pack refs, test refs, live evidence requirements, or secret-free contract.
- `active_risk_audit` runs `python scripts/audit_active_risks.py --strict` before branch/mutation gates and fails when `quality/active_risks.json` loses active-risk owners, linked tests, measurable acceptance criteria, evidence/source refs, or required archive risk coverage.
- `observer_contamination_audit` runs `python scripts/audit_observer_contamination.py --strict` before branch/mutation gates and fails when `quality/observer_known_contamination.json` contains active Observer suppressions that are indefinite, expired, unowned, unreviewed, broad, or missing evidence.
- `branch_coverage_audit` runs `python scripts/audit_branch_coverage.py --strict` before pytest layers and fails when `quality/critical_branch_coverage.json` has missing owners, duplicate branch ids, empty branch test refs, or refs to missing pytest nodes.
- `mutation_smoke` runs `python scripts/run_mutation_smoke.py` before pytest layers. It mutates only a temp workspace copy, then fails on surviving mutants or pytest collection/infrastructure errors for the configured critical pure-logic targets.
- `scripts_pytest_no_db` runs `scripts/test_*.py -m "not manual"` with `--durations=40` and `junit-scripts-no-db.xml` before server pytest layers.
- `server/tests/test_property_state_contracts_no_db.py` runs in `server_pytest_no_db` and provides deterministic property/state-machine coverage for redaction, ticket status normalization and workflow profile FSM contracts without a new dependency.
- `migration_schema` runs `server/tests/test_migration_schema_contract.py` with `junit-migration-schema.xml`, timing artifacts, direct fresh Alembic migration, exact head verification and required schema contract checks before the broad DB/API layers.
- Optional `--parallel --max-workers 2` for bounded server DB/WS layer concurrency; this does not change pytest markers,
  cleanup profiles, DB template behavior, pool settings, or test fixture semantics.

If a test runs longer than the watchdog value, `server/tests/conftest.py` prints all Python thread stacks into the pytest log. This is meant to make the next timeout actionable: the log should show the current test and stack traces, not just a killed process.

Fixture timing is opt-in outside `run_ci_suite.py`. To profile a focused server pytest run without changing test behavior:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_TIMING_PATH = "artifacts/ci/manual/fixture-timings/focused.jsonl"
python -m pytest server/tests/test_web_support_api.py -m "not manual and not no_db and not agent_ws" -q
python scripts/summarize_fixture_timings.py artifacts/ci/manual
python scripts/summarize_fixture_timings.py artifacts/ci/manual --enforce-budget
```

The summary is written to `artifacts/ci/<sha>/fixture-timings-summary.json` and printed as a table with `total`, `count`, `avg`, `p50`, `p95`, and `max` per fixture phase. Current measured phases are `run_migrations/setup`, `cleanup_db/setup`, `_cleanup_db_async/call`, `test_app/setup`, `test_app/teardown`, `test_app_light/setup`, `test_app_light/teardown`, `test_client/setup`, `test_client/teardown`, `test_client_light/setup`, `test_client_light/teardown`, `test_agent/setup`, and `test_agent/teardown`. Cleanup timings with a `profile` field are also grouped as `cleanup_db:<profile>` and `_cleanup_db_async:<profile>` while preserving the original aggregate rows. The default budget profile annotates matching fixture/phase rows with a `budget` object and reports violations when `p95_seconds` or `max_seconds` exceeds the budget; `--enforce-budget` exits non-zero on those violations. Some timings are nested, so do not sum every row as a single wall-clock total; use the rows to identify which fixture phase should be optimized next.

## Light HTTP App Fixture

`test_app_light` and `test_client_light` are explicit opt-in fixtures for HTTP/API pytest files that only need `create_app()` plus the standard test auth/config patches. They deliberately skip runtime-heavy startup work: no `recover_pending_commands`, no real `DeviceOutboxSender`, and no outbox sender binding. The default `test_app` and `test_client` fixtures keep their historical behavior.

Use light fixtures only after focused validation proves the file does not exercise runtime sender, outbox recovery, WebSocket, or in-process agent semantics. A low-churn module opt-in can shadow the regular fixture name:

```python
@pytest.fixture
def test_client(test_client_light):
    return test_client_light
```

Do not use light fixtures for files that use `test_agent`, `agent_ws`, `ws_connect`, `DeviceOutboxSender`, `recover_pending_commands`, `outbox_sender`, `enqueue_command_async`, `CommandResultService`, or `AgentConnectionContext`. Keep those tests on the regular `test_client` unless a separate PR proves and documents a safe noop substitute.

The candidate audit is report-only:

```powershell
python scripts/audit_test_app_light_candidates.py
```

When validating a new opt-in, run focused pytest with timing and cleanup audit, then the owning canonical layer:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_CLEANUP_AUDIT = "1"
python -m pytest server/tests/test_registration_api.py -vv --durations=40
python scripts/run_ci_suite.py --layer server_pytest_db_web_api
```

## Server DB Template Mode

`PC_CLIENT_TEST_DB_TEMPLATE=1` is an opt-in server pytest acceleration path for PostgreSQL DB/WS layers. The harness computes a stable fingerprint from `server/alembic.ini` and `server/app/db/migrations/**`, creates or reuses `pc_support_test_template_<fingerprint12>`, applies `alembic upgrade head` once to that template, then creates each isolated `pc_support_test_<domain>_<worker>_<hash>` database with `CREATE DATABASE ... TEMPLATE ...`.

This removes repeated Alembic setup for DB/WS layers, but it does not change `test_app`, `test_client`, `test_agent`, pooling, xdist, or test semantics. Tests without an explicit cleanup profile still pay the full per-test `cleanup_db` `TRUNCATE ... RESTART IDENTITY CASCADE` cost.

Manual controls:

```powershell
$env:PC_CLIENT_TEST_DB_TEMPLATE = "0"          # disable and use direct Alembic setup
$env:PC_CLIENT_TEST_DB_TEMPLATE = "1"          # enable template clone mode
$env:PC_CLIENT_TEST_DB_TEMPLATE_KEEP = "1"     # keep the migrated template for repeated/layered runs
$env:PC_CLIENT_TEST_DB_TEMPLATE_REBUILD = "1"  # force rebuild for the current fingerprint
```

`scripts/run_ci_suite.py` enables `PC_CLIENT_TEST_DB_TEMPLATE_KEEP=1` for DB/WS layers so the migrated template is reused across pytest processes. Without `KEEP=1`, the harness best-effort drops the template after the pytest session. Only databases named `pc_support_test_template_*` are template caches and are safe to drop manually. Do not drop arbitrary PostgreSQL databases from cleanup scripts. Shared DB fallback (`PC_CLIENT_ALLOW_SHARED_TEST_DB=1` or automatic fallback to `pc_support_test`) is not a valid full DB/API gate path; template mode requires isolated admin database access and fails clearly if the run falls back to the shared DB. `scripts/ci_artifacts.py` rejects green CI artifacts whose DB/WS layer logs contain shared-test-DB fallback markers, so release preflight, deploy and full release gates cannot turn shared `pc_support_test` fallback into release-pass evidence.

## Server DB Cleanup Profiles

`cleanup_db` is fail-closed. A DB-backed test without `@pytest.mark.db_cleanup(...)` uses the `full` profile, which preserves the historical broad `TRUNCATE ... RESTART IDENTITY CASCADE` table list. `no_db` still skips DB setup and cleanup entirely.

Use a narrower profile only after a focused run proves the file does not leak data outside that profile. Prefer module-level markers so the audit/reporting tools can see the file assignment:

```python
pytestmark = pytest.mark.db_cleanup("observer_diagnostics")
pytestmark = pytest.mark.db_cleanup("tickets")
pytestmark = pytest.mark.db_cleanup("registration")
pytestmark = pytest.mark.db_cleanup("web_support")
```

Supported profiles are `full`, `tickets`, `observer_diagnostics`, `agent_runtime`, `registry_access`, `policies_config`, `registration`, and `web_support`. Unknown profiles and multiple `db_cleanup` markers on one test fail fast.

Profile selection guide:

| Profile | Use for |
| --- | --- |
| `observer_diagnostics` | observer, diagnostics, tech/admin control-plane and trace-overlay tests. |
| `tickets` | ticket/helpdesk/form/service-catalog/requester-timeline/support-playbook tests. |
| `registry_access` | registry/access/audience/group/user-permission tests. |
| `policies_config` | policy/config/SLA/OLA/routing/closure/visibility/reporting tests. |
| `agent_runtime` | agent/device/outbox/module/tool/runtime API tests that do not use the in-process `test_agent` fixture. |
| `registration` | registration, device binding, browser pairing, and account-session tests that are driven by device/registry parent rows. |
| `web_support` | broad support/requester web API flows that mix tickets, registry/access, operations/outbox, playbooks, observer traces, and agent update artifacts. |

Do not automatically map mixed `web_api` files to `tickets`. Use `web_support` only when the file is a support/requester web workspace flow and focused validation with `PC_CLIENT_TEST_CLEANUP_AUDIT=1` is green. Keep a file on `full` when it is mixed-domain beyond a documented profile, uses `test_agent`/`agent_ws`, writes through broad web/API flows that are not covered by `web_support`, or is otherwise hard to prove from the existing cleanup profile. If a focused run fails after adding a marker, revert that file to `full` instead of weakening assertions or expanding cleanup behavior in the same pass.

Cleanup profiles may rely on database cascades from parent tables already listed in `FULL_CLEANUP_TABLES`. Runtime child tables such as `device_user_bindings`, `device_account_sessions`, `device_registration_claims`, `device_browser_pairings`, `ticket_approvals`, `ticket_notifications`, and `user_consent_requests` are now explicit full-cleanup tables; if a new runtime table appears, classify it in `quality/db_table_classification.toml` and make the schema audit pass instead of relying on implicit cascade behavior.

To audit current file-level coverage without changing pytest behavior:

```powershell
python scripts/audit_test_inventory.py --strict
python scripts/audit_db_cleanup_profiles.py
python scripts/audit_db_cleanup_profiles.py --strict  # canonical CI gate for missing DB-backed profiles
python scripts/audit_db_cleanup_schema.py --schema-from-models --strict
python scripts/run_ci_suite.py --layer migration_schema
```

The audit report prints `file`, inferred domain layer, explicit profile or `missing`, module/file-level `no_db`, likely `agent_ws`, and a summary. Normal mode is report-only; `--strict` returns non-zero for DB-backed, non-`agent_ws` files that still have no explicit profile.
The schema audit verifies every table is classified exactly once, runtime tables are covered by static/full cleanup and dynamic reset policy, cleanup lists have no stale tables, and FK cleanup blockers are visible.

For contamination checks on a small focused sample, enable audit mode:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_CLEANUP_AUDIT = "1"
python -m pytest server/tests/test_knowledge_search.py -vv
```

Audit mode checks row counts for the selected profile tables after cleanup and fails if rows remain. It is intentionally opt-in because it adds extra DB queries per test. Use it together with focused domain runs before broadening profile coverage, for example:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_CLEANUP_AUDIT = "1"
python -m pytest server/tests/test_ticket_*.py server/tests/test_helpdesk_*.py -m "not manual and not no_db and not agent_ws" -vv --durations=40
```

Focused validation for reducing `server_pytest_db_web_api` full-cleanup debt should use timing plus cleanup audit before and after adding module-level markers:

```powershell
$env:PC_CLIENT_TEST_TIMING = "1"
$env:PC_CLIENT_TEST_CLEANUP_AUDIT = "1"
python -m pytest server/tests/test_web_support_api.py -vv --durations=40
python -m pytest server/tests/test_requester_workspace_api.py -vv --durations=40
python -m pytest server/tests/test_registration_api.py -vv --durations=40
python -m pytest server/tests/test_p0_workbench_update_contracts.py -vv --durations=40
python -m pytest server/tests/test_account_session_service.py -vv --durations=40
python scripts/run_ci_suite.py --layer server_pytest_db_web_api
```

On Windows shared-test-DB fallback, the harness tries `pg_terminate_backend` once. If admin privileges are unavailable, it caches that fact for the pytest session and skips repeated terminate attempts; per-test `TRUNCATE ... RESTART IDENTITY CASCADE` still provides cleanup.

On Windows default DB-backed pytest, the harness opens the configured SSH tunnel and creates an isolated `pc_support_test_<domain>_<pid_or_worker>_<short_hash>` database through `TEST_DATABASE_ADMIN_URL` semantics. `run_ci_suite.py` passes the CI layer name as `PC_CLIENT_TEST_DB_DOMAIN`, and `--keep-test-db` keeps isolated DBs for debugging. Shared `pc_support_test` is for explicit fallback/debug only (`PC_CLIENT_ALLOW_SHARED_TEST_DB=1`) or automatic fallback when the admin database cannot be reached; any shared fallback warning means the run is not valid for the full DB/API gate and is rejected as a green release artifact.

## When To Run What

- Docs-only or script metadata: `python scripts/verify_workspace.py` plus the matching `scripts/test_*.py`.
- Server API/handler/repo/schema behavior: server DB/API layer, plus focused files for the touched area.
- WebSocket, `run_tool`, outbox, in-process agent, UI realtime: server `agent_ws` layer.
- Agent runtime, launcher, tray, local UI bridge: focused `pc_agent/tests/*`, then live local agent status if runtime behavior changed.
- Admin/support web UI: focused server API tests, `pnpm --dir webapp run build`, relevant Playwright spec, then browser check.
- Iterative staging deploy: focused local verification for the touched area, then `python scripts/release_server_to_remote.py --gate quick`, remote smoke, and browser/live checks when the UI/runtime changed. Quick gate skips only the green full-CI artifact requirement.
- Final release checkpoint by explicit request: full `python scripts/run_ci_suite.py`, `python scripts/release_server_to_remote.py --gate full` or the default gate, remote smoke, and browser/live agent checks. Routine GitHub pushes do not wait for this checkpoint.

Do not raise timeouts as the first response to slow tests. First look at `--durations=80`, split the layer if needed, and optimize repeated heavy fixture setup such as `test_agent`.
