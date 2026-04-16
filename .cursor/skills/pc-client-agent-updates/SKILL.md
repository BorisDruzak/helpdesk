---
name: pc-client-agent-updates
description: Canonical workflow for pc_client agent self-update, launcher releases, build upload, canary rollout, diagnostics, and rollback verification.
---

# PC Client — agent updates / launcher / rollout

Используйте этот skill, если задача затрагивает:

- `pc_agent/launcher/*`
- `pc_agent/ws_agent.py`
- `pc_agent/ui_bridge/*`
- `pc_agent/ui_gui/*`
- `pc_agent/build_windows_release*.py`
- `server/agents/agent_builds_handlers.py`
- `server/websocket/agent_handshake.py`
- admin UI раздел Agent Updates

## Сначала открыть

1. `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`
2. `pc_agent/docs/SELF_UPDATE.md`
3. `docs/AGENT_UPDATE_CONTRACT.md`
4. `server/docs/AGENT_UPDATES_API.md`
5. `pc_agent/docs/CODEMAP.md`

## Канонический порядок

1. Исправить код в локальной копии `C:\Users\admin-2\CodexProjects\pc_client`.
2. Если меняется распространяемый бинарь агента или launcher, обновить `pc_agent/version.py`.
3. Синхронно обновить docs/CODEMAP/skills, если меняется release/update flow.
4. Прогнать проверки:
   - `python scripts/verify_workspace.py`
   - `python -m pytest pc_agent/tests/ -v --tb=short`
   - при server-side update или admin UI: точечные `server/tests/test_p0_workbench_update_contracts.py`, `server/tests/test_admin_tech_api.py`
5. Собрать Windows release:
   - `python pc_agent/build_windows_release_v2.py`
6. Проверить артефакты:
   - `pc_agent/dist/launcher.exe`
   - `pc_agent/dist/pc_agent/pc_agent.exe`
   - `pc_agent/dist/release/windows_amd64/stable/<version>/pc_agent-windows_amd64-<version>.zip`
7. Опубликовать build на сервер через `POST /api/agent_builds/upload` или через admin UI.
8. Для cleanup старых версий на сервере использовать admin UI Agent Updates или `python scripts/drop_agent_build.py --target ... --channel ... --version ...`.
9. Запустить canary update на одном устройстве.
   Для локальных Windows canary использовать `python scripts/manage_local_agent.py start <name> --launcher`; если у instance уже есть полный versioned install layout, он должен стартовать на своей текущей версии, а не автоматически пересеваться на repo build.
10. Проверить diagnostics/timeline/problem logs и подтвердить success только после handshake новой версии.
11. Bulk rollout делать только после canary.

## Обязательные правила

- Не подменять ZIP под тем же version string как обычный путь релиза.
- Не держать в активной цепочке rollout build-ы ниже `3.1.8`.
- Не считать `scheduled` финальным успехом.
- Не обновлять работающий `pc_agent.exe` in-place.
- Для ручного update указывать `reason`.
- При GUI-симптомах проверять не только WS, но и локальный `ui_bridge`/SSE replay.

## Где смотреть логи

- Локально:
  - `pc_agent/dist/launcher.log`
  - `pc_agent/dist/data/logs/agent.log`
  - `pc_agent/dist/data/updates/update_history.json`
  - `pc_agent/dist/data/updates/last_failed_pending_update.json`
- На сервере:
  - `python scripts/manage_remote_stack.py logs server`
  - `GET /api/devices/{device_id}/agent/update_diagnostics`

## Что фиксировать в отчёте

- новая версия;
- какие тесты прошли;
- был ли build загружен на сервер;
- был ли canary update;
- чем подтверждён успех: handshake/diagnostics/UI;
- что не проверено и какие остаточные риски остались.
