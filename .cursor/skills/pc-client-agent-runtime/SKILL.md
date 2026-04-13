---
name: pc-client-agent-runtime
description: Always-on agent runtime, tray and runtime logging playbook for pc_client. Use when changing pc_agent/ws_agent.py, pc_agent/ui_gui/*, pc_agent/ui_bridge/* or runtime logging behavior.
---

# PC Client — always-on runtime / tray / logs

Подключать, когда задача затрагивает:

- `pc_agent/ws_agent.py`
- `pc_agent/ui_gui/*`
- `pc_agent/ui_bridge/*`
- `pc_agent/core/runtime_logging.py`
- lifecycle главного окна, tray, локальный shutdown/restart path, runtime diagnostics

## С чего начинать

1. Открыть:
   - `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`
   - `pc_agent/docs/CODEMAP.md`
   - `docs/QUICK_LOOKUP.md`
2. Проверить текущий lifecycle:
   - что делает `CloseMainWindow()`
   - кто выставляет shutdown signal
   - где живут runtime status/logs endpoints

## Канон реализации

- Агент должен продолжать работать после закрытия основного окна.
- Полный выход должен идти только по явному shutdown path.
- Tray — thin control surface, а не место для критичной бизнес-логики.
- Runtime logs должны идти через единый helper с rotation/retention/compression.
- GUI diagnostics должны читаться через `ui_bridge`, а не напрямую из глубины runtime.

## Обязательные проверки

1. `python scripts/verify_workspace.py`
2. `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short`
3. `python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short`
4. Локальный E2E:
   - `python scripts/manage_local_agent.py start <name> --gui --ui-port <port>`
   - проверить `GET /ui/agent/status`
   - закрыть окно `Maria Agent`
   - убедиться, что агент продолжает отвечать
   - завершить через `POST /ui/agent/shutdown`

## Что не делать

- Не считать закрытие окна штатным способом остановки агента.
- Не оставлять forced `DEBUG` как production default.
- Не добавлять платформенно-специфичную логику прямо в общий runtime без явной изоляции.
- Не выпускать изменения lifecycle без живого локального сценария через `manage_local_agent.py`.
