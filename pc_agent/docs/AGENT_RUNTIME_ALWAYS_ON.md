# AGENT_RUNTIME_ALWAYS_ON

Документ описывает канонический runtime-сценарий агента после перехода на always-on GUI с tray и runtime-логами.

## Цель

- Закрытие основного окна не должно останавливать агент.
- GUI должен быть thin-слоем поверх локального `ui_bridge`, а runtime должен продолжать жить в фоне.
- Логи должны быть пригодны для long-running режима: управляемый уровень, rotation, retention, compression.

## Каноническая модель

1. `pc_agent/ws_agent.py` поднимает runtime, `ui_bridge` и GUI.
2. `pc_agent/ui_gui/main.py` открывает главное окно, но при закрытии окна по умолчанию прячет GUI в tray.
3. Полный выход агента идёт только через явный shutdown path:
   - tray action `Выход`
   - локальный `POST /ui/agent/shutdown`
   - controlled restart/update flow
4. `pc_agent/ui_bridge/api_server.py` считается локальной control/diagnostics поверхностью для GUI и локальных проверок.

2026-06-10 Stage 3 consent GUI polling is part of the always-on runtime surface: `pc_agent/ui_gui/main_window.py` polls `/api/registry/agent/consents` only when an active requester account session exists, shows `pc_agent/ui_gui/user_consent_dialog.py` for pending canonical `UserConsentRequest` rows, and posts approve/deny with the same account-session headers used by ticket actions. This does not change tray/shutdown/update lifecycle; consent polling must not block the WebSocket loop.

### Recommended update surface в локальном UI bridge

Локальный `ui_bridge` теперь отдаёт GUI не только connection/runtime diagnostics, но и update-related surface:

- `GET /ui/agent/status` возвращает `agent_version`, `is_release`, `release_channel`, `update_available`, `recommended_version`, `recommended_channel`, `recommended_reason`, `comparison`, `update_checked_at`, `pending_update_*`, `update_request_state`, `update_request_version`, `update_request_operation_id`, `update_request_requested_at`;
- `POST /ui/agent/update` запускает локальный trigger recommended update: агент запрашивает server-side recommendation и, если есть кандидат, инициирует обычный server update flow для собственного `device_id`; GUI должен сразу перейти в `requesting/requested`, а затем коротким refresh burst дотянуть `pending_restart` / `applying` / `restarting`, чтобы кнопка не выглядела зависшей и пользователь видел подготовку к автоматическому перезапуску.

`GET /ui/settings` возвращает не только эффективный `enabled_modules`, но и `core_enabled_modules` / `configured_enabled_modules`. GUI обязан показывать core-модули отдельной read-only строкой: `system`, `screen`, `diag_logs`, `inventory`, `presence` являются встроенной базой агента, а пакеты из `modules_store` отображаются отдельно и не должны создавать впечатление, что `inventory.collect` выключен.

Таким образом, GUI не выбирает build самостоятельно и не держит отдельную semver/release policy.

## Tray и окно

- `ui.tray_enabled=true` включает tray-слой.
- `ui.minimize_to_tray=true` делает `CloseMainWindow()` сворачиванием в tray вместо остановки агента.
- `ui.start_hidden=true` разрешает запуск скрытым с доступом через tray.
- Если tray недоступен на платформе, агент не должен падать: GUI просто работает обычным окном.
- Плавающие служебные оверлеи GUI, включая STOP-кнопку записи экрана, не должны быть обычными top-level `Qt.Window`: используйте `Qt.Tool`, чтобы они не появлялись в Taskbar/Alt-Tab как отдельные окна `pc_agent`.
- Кастомная frameless-шапка не должна вызывать Qt native `startSystemMove()` / `startSystemResize()` на Windows: эти calls могут создавать `_q_titlebar` helper windows, которые попадают в Taskbar/Alt-Tab как отдельные окна `python`. Drag/resize держать на ручном fallback в `window_chrome.py`.
- Внутренние элементы главного окна нельзя оставлять parentless и затем делать visible: пустые orphan `QLabel`/`QWidget` становятся отдельными top-level окнами `python` / `pc_agent` в Taskbar/Alt-Tab. Служебные элементы должны иметь parent или быть добавлены в layout до показа.

## Service Catalog create-ticket flow

The always-on GUI create-ticket wizard consumes the server safe catalog through
`TicketApiClient.get_service_catalog_current()` and caches it next to the
request-template form pack. When the catalog endpoint is unavailable, the GUI
falls back to the legacy form-pack flow instead of blocking ticket creation.

Catalog Service and Offering are process choices (`service_code`,
`offering_code`) and are distinct from CMDB/service picker fields inside a
dynamic form. P1.1 makes the flow explicit in the local GUI:
`Раздел обращения -> Тип обращения -> dynamic form/details -> Preview -> Submit`.
The fallback `other.unknown` (`Другое / Не знаю`) is shown when the server safe
catalog provides it. Preview and submit requests include the catalog codes plus
the linked `request_template_key`, diagnostic consent, attachments and existing
device/profile metadata. The GUI must display only requester-safe titles,
descriptions, deadlines and approval/diagnostic hints; queue ids, raw policy
JSON, approver internals and registry ids are not exposed in the agent UI. This
does not change Protocol V3.

## External Knowledge boundary in create-ticket flow

The local agent has no Knowledge client, routes or UI flow. Ticket creation continues
without enrichment while `KnowledgePort` is unavailable and Helpdesk projects only
`knowledge_unavailable`; this does not change Protocol V3. A future external adapter
is accepted at PR-7 only with its documented API contract and shadow-read evidence.
Legacy TicketKbLink/ticket_kb_links and sanitized knowledge_attempts records remain
read-only ticket history until the PR-11 forward-only deletion and rollback gate.

## Runtime logs

- Канонический helper: `pc_agent/core/runtime_logging.py`
- Базовый production-профиль:
  - `logging.level=INFO`
  - `logging.console_level=INFO`
  - `logging.rotation=20 MB`
  - `logging.retention=14 days`
  - `logging.compression=zip`
- Источники диагностики:
  - `GET /ui/agent/status`
  - `GET /ui/agent/logs?source=agent|launcher|memory`

## Что проверять после правок

Минимум:

1. `python scripts/verify_workspace.py`
2. `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short`
3. `python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short`

Живой локальный сценарий через именованный инстанс:

1. `python scripts/manage_local_agent.py start <name> --gui --ui-port <port>`
2. Проверить `http://127.0.0.1:<port>/ui/agent/status`
   - убедиться, что в JSON есть release/update поля и они меняются после подключения к серверу;
   - при запросе update проверить переходы `update_request_state: requesting -> requested -> pending_restart -> applying/restarting`;
   - при наличии рекомендации проверить локальный `POST /ui/agent/update`;
3. Программно закрыть окно `Maria Agent`
4. Убедиться, что процесс жив, а `ui_bridge` всё ещё отвечает
5. Завершить агент через `POST /ui/agent/shutdown`

## Инварианты

- `CloseMainWindow()` для главного окна при включённом tray не считается shutdown-сигналом.
- Runtime-диагностика должна быть доступна даже когда окно скрыто.
- Полный выход агента должен быть явным и воспроизводимым через локальный control path.
- Распространяемый GUI-агент не должен переходить в `--no-gui` как fallback при ошибке загрузки Qt/PySide6. Если GUI runtime не стартует, агент завершает процесс с кодом ошибки; launcher либо откатывает новую версию на `previous`, либо после лимита ранних падений останавливается и пишет `data/updates/last_failed_launch.json`.
- Изменения в `pc_agent/ws_agent.py`, `pc_agent/ui_gui/*`, `pc_agent/ui_bridge/*`, `pc_agent/core/runtime_logging.py` синхронно отражаются в `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md` и skill/правилах.
