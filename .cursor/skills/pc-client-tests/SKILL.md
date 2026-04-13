---
name: pc-client-tests
description: Run the right tests for pc_client changes. Use when running local checks, choosing pytest targets, or verifying server/agent changes.
---

# PC Client — тесты и проверки

Использовать при любых локальных проверках после правок в `server/` или `pc_agent/`.

## Обязательный минимум

1. **Проверка воркспейса:**  
   `python scripts/verify_workspace.py`  
   — py_compile, UTF-8, опционально smoke по `--smoke-url`.

2. **По области изменений** — добавить один или несколько шагов ниже.

## Что запускать по области изменений

| Область | Команды (из корня репо) |
|--------|--------------------------|
| **Любая** | `python scripts/verify_workspace.py` |
| **Сервер (server/)** | `python -m pytest server/tests/ -v --tb=short` (или точечно: `server/tests/test_*.py`) |
| **Агент (pc_agent/)** | `python -m pytest pc_agent/tests/ -v --tb=short` |
| **Agent self-update / launcher / Agent Updates UI** | `python -m pytest pc_agent/tests/ -v --tb=short`, `python -m pytest server/tests/test_p0_workbench_update_contracts.py -v --tb=short`, при затронутом `ui_bridge` — точечно `pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short`, затем rebuild release artifact и canary update по playbook `pc-client-agent-updates` |
| **Always-on / tray / runtime logs** | `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short`, `python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short`, затем живой E2E через `python scripts/manage_local_agent.py start <name> --gui --ui-port <port>` и проверка close-to-tray + `POST /ui/agent/shutdown` |
| **Только быстрые тесты сервера** | `python -m pytest server/tests/ -v --tb=short -m "not slow"` (если помечены) или выбрать конкретные файлы |
| **Smoke по живому серверу** | `python scripts/manage_remote_stack.py status control`, затем `python scripts/manage_remote_stack.py smoke server` (сервер на Linux уже запущен) или локально: `python scripts/smoke_test.py` с `BASE_URL=...` |
| **Админ / run_tool** | После smoke — сценарий в браузере по `http://192.168.100.17:8666/admin` (см. скилл pc-client-browser-check). |
| **Техпанель / server runtime control** | `python -m pytest server/tests/test_control_plane_api.py -v --tb=short`, `python -m pytest server/tests/test_admin_tech_api.py -v --tb=short`, затем browser check техпанели с status/health/full logs/confirm. |

## Pytest — важное

- **Сервер:** тесты в `server/tests/`, фикстуры и миграции в `server/tests/conftest.py`. Для интеграционных тестов нужна тестовая БД: `TEST_DATABASE_URL` (по умолчанию `postgresql+asyncpg://...@127.0.0.1:5432/pc_support_test`). Миграции применяются фикстурой `run_migrations`.
- **Агент:** тесты в `pc_agent/tests/`, без БД сервера.
- Запуск из корня: `python -m pytest server/tests/` или `python -m pytest pc_agent/tests/` — так корректно резолвятся импорты.
- Если падают только отдельные тесты — запустить точечно: `python -m pytest server/tests/test_integration_p0.py -v`.

## Порядок перед коммитом

1. `python scripts/verify_workspace.py`
2. Pytest по затронутой области (server и/или pc_agent)
3. При необходимости: deploy → start control/server на Linux → smoke → browser check → stop server

Не пушить в GitHub без успешного минимума (verify + релевантные тесты).
