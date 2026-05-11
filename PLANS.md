# Remote Assist Runtime Module Plan

## Goal

Перевести Remote Assist из монолитной агентской реализации в обновляемый managed runtime module, чтобы исправления WebRTC, capture, control, clipboard, file-transfer и elevated mode можно было поставлять отдельным модулем без полного релиза Maria Agent.

## Scope

- Рабочая копия: `C:\Users\admin-2\CodexProjects\pc_client`.
- Агент: `pc_agent/remote_assist/*`, `pc_agent/ui_gui/main_window.py`, module host/loader integration.
- Модуль: managed package `remote_assist_runtime`, публикуемый через существующую серверную module registry.
- Сервер: использовать существующие module upload/preferred/install/reconcile механизмы; не создавать отдельную систему доставки.
- Remote Assist server lifecycle, DB schema, signaling API and support workspace viewer остаются текущими.

## Constraints

- Consent, ticket/device/operator binding, audit and timeline остаются серверным source of truth.
- Базовый агент должен сохранять safe fallback на встроенный Remote Assist runtime, если managed module отсутствует, не установлен или не загрузился.
- Managed module не имеет права обходить consent, RBAC, signaling token validation или запреты на hidden unattended access.
- GUI Maria Agent нельзя блокировать: runtime module запускается через QThread/asyncio boundary.
- Native dependencies, которые должны быть bundled в PyInstaller, всё ещё требуют full agent release.
- Elevated helper entrypoint (`pc_agent.exe --remote-assist-elevated-helper`) остаётся в базовом агенте, пока нет отдельного подписанного helper delivery layer.

## Current State

- Remote Assist сейчас был частью базового агента: команда `remote_assist.request` обрабатывается в `pc_agent/ws_agent.py`, затем GUI создаёт `RemoteAssistThread` из `pc_agent.remote_assist.thread`.
- Сервер доставляет запрос через DeviceOutbox / Protocol V3, а signaling идёт через `/ws/remote-assist/{session_id}` с короткоживущими role tokens.
- Текущая module system обслуживает ZIP + `manifest.json`, server preflight, preferred version, `install_module_package`, agent `ModuleManager`, `DynamicModuleLoader`, `ModuleRegistry`.
- Для Remote Assist нужен слой поверх существующих modules: runtime-module host, который умеет загрузить активный module package и получить factory для long-lived Remote Assist thread.

## Architecture Decisions

- Название runtime module: `remote_assist_runtime`.
- Версия первого managed module: `1.0.0`.
- Базовый агент получает `pc_agent.remote_assist.runtime_host`:
  - ищет активную версию `remote_assist_runtime` в `modules_store`;
  - загружает `module.py`;
  - вызывает `create_remote_assist_thread(...)`;
  - при любой ошибке пишет warning и использует встроенный `RemoteAssistThread`.
- Managed package `pc_agent/modules_packages/remote_assist_runtime` в первом срезе поставляет совместимый runtime factory и диагностический tool `remote_assist_runtime.info`.
- Runtime factory interface:
  - вход: `signaling_url`, `token`, `ice_servers`, `mode`, `media`, `features`, `parent`;
  - выход: объект с Qt-сигналами `failed`, `ended`, `state_changed`, методами `start()`, `stop()`, `isRunning()`.
- Серверный default достигается существующим механизмом preferred modules + desired install на устройство, не отдельным remote-assist updater.
- Нужен один bootstrap-релиз агента с `runtime_host`; следующие Remote Assist runtime исправления можно поставлять через module package.

## Implementation Steps

- [x] Очистить старый `PLANS.md` и заменить на этот план.
- [x] Добавить regression tests для runtime host:
  - fallback использует встроенный `RemoteAssistThread`;
  - active `remote_assist_runtime` module factory получает параметры сессии.
- [x] Добавить `pc_agent/remote_assist/runtime_host.py`.
- [x] Переключить `pc_agent/ui_gui/main_window.py` на `create_remote_assist_thread(...)`.
- [x] Добавить managed package `pc_agent/modules_packages/remote_assist_runtime`:
  - `manifest.json`;
  - `module.py`;
  - `register()` для module smoke/list_tools;
  - `create_remote_assist_thread()` для runtime host.
- [x] Добавить package smoke tests.
- [x] Обновить docs/CODEMAP/navigation catalog для новой runtime-module boundary.
- [x] Собрать bootstrap agent release `3.1.55`.
- [x] Собрать ZIP module package.
- [x] Загрузить module package на сервер через `/api/modules/upload`.
- [x] Назначить `remote_assist_runtime@1.0.0` preferred/default по правилам modules.
- [x] Установить/проверить module на canary agent `AD-MAIN`.
- [x] Проверить default path для агента: `AD-MAIN` на `3.1.55`, `remote_assist_runtime@1.0.0` active, desired diff `ok`.

## Verification Plan

- `python -m pytest pc_agent/tests/test_remote_assist_runtime_host.py pc_agent/tests/test_remote_assist_runtime_module_package.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_remote_assist_webrtc_client.py pc_agent/tests/test_remote_assist_input_controller.py pc_agent/tests/test_remote_assist_elevated_helper.py -q --tb=short`
- `python scripts/verify_workspace.py`
- [x] Server module upload response included `module_name=remote_assist_runtime`, `module_version=1.0.0`, `preflight_status=passed`.
- [x] Preferred/default response showed `preferred_version=1.0.0`.
- [x] Canary diagnostics showed `AD-MAIN` updated to `3.1.55`; module APIs showed installed/active `remote_assist_runtime@1.0.0` and desired diff `ok`.

## Handoff Notes

- This first slice makes Remote Assist module-loadable. It does not remove the bundled fallback from the agent.
- Future module versions can replace `module.py` with a self-contained implementation, but any new native dependency still requires a full agent build.
- Do not remove fallback until at least one canary cycle proves module install, activation, Remote Assist consent, WebRTC video, control, clipboard, file transfer and elevated mode.
