# Server Tests

Актуальный pytest-контур для server-side integration и contract tests.

## Canonical baseline

- Корневой pytest config: [pytest.ini](/C:/Users/admin-2/CodexProjects/pc_client/pytest.ini)
- Server markers: [server/pytest.ini](/C:/Users/admin-2/CodexProjects/pc_client/server/pytest.ini)
- Main fixtures: [server/tests/conftest.py](/C:/Users/admin-2/CodexProjects/pc_client/server/tests/conftest.py)
- CI runner: [scripts/run_ci_suite.py](/C:/Users/admin-2/CodexProjects/pc_client/scripts/run_ci_suite.py)
- DB cleanup profile audit: [scripts/audit_db_cleanup_profiles.py](/C:/Users/admin-2/CodexProjects/pc_client/scripts/audit_db_cleanup_profiles.py)

## CI layers

`scripts/run_ci_suite.py` runs server pytest in domain layers so one slow group does not hide the rest of the signal:

1. `server_pytest_no_db`: `python -m pytest server/tests -m "not manual and no_db" -vv --durations=80`
2. `server_pytest_db_tickets`
3. `server_pytest_db_observer_diagnostics`
4. `server_pytest_db_agent_runtime`
5. `server_pytest_db_web_api`
6. `server_pytest_agent_ws`: `python -m pytest server/tests -m "not manual and agent_ws" -vv --durations=80`

Run one layer with:

```powershell
python scripts/run_ci_suite.py --layer server_pytest_db_tickets
```

The `agent_ws` marker is applied automatically to tests that request the `test_agent` fixture. Do not add it by hand unless a test starts the same in-process agent/runtime path without that fixture.

CI sets `PC_CLIENT_PYTEST_WATCHDOG_SECONDS=120` for every server pytest layer. When a test runs longer than that value, the harness prints all Python thread stacks into the pytest log so the next timeout shows the stuck test and call stacks instead of only the final process timeout.

The default server pytest step timeout is 45 minutes per layer. If a layer approaches that value, split or optimize the slow tests before increasing the timeout again.

## Markers

- `unit` — unit-like tests without full integration harness.
- `integration` — integration tests against aiohttp app / DB / in-process agent.
- `no_db` — fixture cleanup and migrations не нужны.
- `manual` — не попадает в обычный `pytest -m "not manual"`.

- `agent_ws` - tests that start the in-process WS agent fixture; auto-applied when `test_agent` is used.
- `db_cleanup("<profile>")` - DB-backed tests that have been validated against a narrower cleanup table profile. Missing markers stay on historical `full` cleanup. Run `python scripts/audit_db_cleanup_profiles.py` to report coverage.

## Test database

Windows default:

- If `TEST_DATABASE_URL` and `TEST_DATABASE_ADMIN_URL` are not set, DB-backed server pytest opens a local SSH tunnel to PostgreSQL using `C:\Users\admin-2\.ssh\pc_client_altserver_ed25519`.
- The default DB is isolated and named `pc_support_test_<domain>_<pid_or_worker>_<short_hash>`.
- The first isolated Windows DB-backed test run can take several minutes because it creates a fresh database and applies the full Alembic chain through the SSH tunnel.
- In shared fallback mode the harness terminates stale `pc_support_test` backends before cleanup and sets a short `lock_timeout`, so leaked sessions surface as a fast failure instead of an endless hang.
- Shared `pc_support_test` is not valid for a full DB/API gate; use it only through explicit debug fallback. On Windows, explicit shared debug mode also uses the local SSH tunnel.

По умолчанию server suite больше не должен использовать общий `pc_support_test`.

Канонические env vars:

- `TEST_DATABASE_ADMIN_URL` — admin DSN для create/drop ephemeral DB.
- `TEST_DATABASE_URL` — явный DSN test DB, если нужен override.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1` — разрешает legacy shared DB только явно.

Если `TEST_DATABASE_*` не заданы, harness теперь по умолчанию наследует host/user/port от runtime `DATABASE_URL`.
Это важно для Linux-стенда, где PostgreSQL доступен по loopback, а не по внешнему адресу хоста.

Поведение по умолчанию:

1. `conftest.py` создаёт уникальную БД вида `pc_support_test_<domain>_<pid_or_worker>_<short_hash>`.
2. Применяет Alembic migrations один раз на сессию.
3. Держит один session-scoped async engine.
4. Перед каждым DB-backed test делает `TRUNCATE ... RESTART IDENTITY CASCADE`.

Если локальная среда не даёт создать ephemeral DB, для точечных прогонов можно временно использовать shared DB:

```powershell
$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'
python -m pytest server/tests/test_cancel_operations.py -q
```

Чтобы сохранить isolated DB для диагностики после падения слоя:

```powershell
python scripts/run_ci_suite.py --layer server_pytest_db_tickets --keep-test-db
```

## Recommended runs

Минимум по server-side после изменений:

```powershell
python -m pytest server/tests -m "not manual"
```

Для точечных регрессий:

```powershell
python -m pytest server/tests/test_tools_async_response_contract.py -q
python -m pytest server/tests/test_cancel_operations.py -q
```

Для полного локального CI-прогона:

```powershell
python scripts/run_ci_suite.py
```

## Notes

- `pc_agent/tests/test_support_chat_reliability.py` помечен как `manual` и не должен попадать в обычный suite.
- `/api/tools/run` теперь канонически async: `202 Accepted` возвращается только если команда реально enqueue-нулась; transport/precheck ошибки обязаны возвращать явный error-ответ с `operation_id`, `poll_url` и `error_code`. Sync path только через явный `wait=1`.
- Исторические point-in-time отчёты о тестах вынесены в [docs/archive/server-tests](../../docs/archive/server-tests/README.md) и не являются каноном.
