# CODEMAP (pc_agent)

Карта кода `pc_client/pc_agent`. Используется для быстрой навигации и поиска (в т.ч. скрипт `scripts/agent_find.py` и контекст агента). Пути указаны относительно корня репозитория (например `pc_agent/ws_agent.py`).

---

## 0. Операционный старт

- Если задача начинается с diff, сначала выполните `python scripts/diff_context.py`.
- Если тема пересекает сервер и агент или неясно, где вход, откройте `docs/QUICK_LOOKUP.md`.
- Для точечного поиска по агенту используйте `python scripts/agent_find.py "<ключевое слово>" --dir pc_agent`.
- Если тема касается observer, module breadcrumbs, update trace или action-trace bridge, дополнительно откройте `server/docs/OBSERVER_LAYER.md` и `server/docs/OBSERVER_AUTHORING_RULES.md`.

### Truth baseline

- Корневой pytest-контур: `pytest.ini` (markers `unit`, `integration`, `manual`, `no_db`).
- Agent baseline: `python -m pytest pc_agent/tests -m "not manual"`.
- Exploratory suite `pc_agent/tests/test_support_chat_reliability.py` помечен как `manual` и не входит в обычный CI.
- Для совместного server+agent baseline используется `scripts/run_ci_suite.py`.

| Сценарий | Открыть сначала | Затем |
|------|------------------|-------|
| Handshake / outbox / ACK | `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py` | `pc_agent/core/sender.py`, `pc_agent/docs/PROTOCOL_V3.md` |
| `run_tool` / команды | `pc_agent/core/orchestrator.py`, `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py` | `pc_agent/core/registry.py`, `server/tools/service.py` |
| Auth / bootstrap | `pc_agent/core/identity.py`, `pc_agent/core/machine_identity.py`, `pc_agent/core/device_fingerprint.py` | `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py`, `pc_agent/docs/AUTHENTICATION.md` |
| Self-update / launcher / rollout | `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md` | `pc_agent/docs/SELF_UPDATE.md`, `pc_agent/launcher/installer.py`, `server/docs/AGENT_UPDATES_API.md` |
| Always-on / tray / runtime logs | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md` | `pc_agent/ws_agent.py`, `pc_agent/core/runtime_logging.py`, `pc_agent/ui_gui/main.py`, `pc_agent/ui_gui/tray_manager.py` |
| GUI / `ui_bridge` | `pc_agent/ui_gui/main_window.py` | `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md` |
| Модули / registry | `pc_agent/core/module_manager.py` | `pc_agent/core/loader.py`, `pc_agent/docs/MODULES.md` |

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `pc_agent/ws_agent.py` | Основной runtime: WS-соединение, handshake, команды, UI bridge; auth/connection orchestration (через state machine), Scheduler RPC + runtime loop; now runs as always-on process with sticky `connection_state`, runtime diagnostics/status/log tail callbacks для `ui_bridge`, server-driven update recommendation cache (`is_release`, `release_channel`, `recommended_version`, `update_available`) и local trigger recommended update через обычный server update flow; runtime status now also overlays `pending_update_*` and `update_request_*`, suppresses `update_available` while a request is already in flight, and keeps the GUI aligned with launcher-side pending state; GUI закрытие больше не считается автоматическим shutdown; при auth bootstrap умеет fallback lookup токена по `machine_id -> install_id -> legacy uuid`, после `Invalid token` переводит и GUI, и headless режим в automatic reprovision, и не фиксирует вечный local reject при `DEVICE_ARCHIVED`; long-running `run_tool` / `call_tool` dispatch теперь уходит в background tasks, чтобы агент мог принять `cancel_operation` без блокировки WS loop, `handshake_ack.server_capabilities` переключает capability-gated `outbox_items_batch` transport, and successful authenticated sessions upload bounded `agent_observer_batch` telemetry from local action trace with a durable cursor |
| `pc_agent/ws_agent_runtime_helpers.py` | Вынесенные runtime helper-блоки `WSAgent`: restart/update-shutdown, scheduler RPC/runtime loop, auth bootstrap, reprovision/request-connection flow, форматирование uptime |
| `pc_agent/launcher/launcher_main.py` | Launcher / запускные сценарии; applies pending updates, records failed launches, prunes old version directories after successful publish, and rolls back `current.json` to `previous` after repeated immediate crash of a newly switched version |
| `pc_agent/launcher_portable_main.py` | Портативный launcher; auto-detect install/data roots рядом с exe, импорт токена из primary `%LOCALAPPDATA%\\PCClientAgent\\data` для локального Windows теста и rollback на `previous` при repeated immediate crash новой версии |
| `pc_agent/ui_gui/main.py` | Запуск Qt GUI, lifecycle окна, minimize-to-tray, start-hidden, явный exit path и cleanup локальных SSE/API ресурсов; installs the optional-by-env `GuiPerformanceProbe` field diagnostic for focused-window CPU investigations; локальные lifecycle/debug сообщения должны оставаться читаемыми русскими строками без mojibake |
| `pc_agent/build_windows_release_v2.py` | Каноническая Windows release-сборка: launcher.exe + versioned agent layout + update ZIP |

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 Ядро (core/)
| Файл | Назначение |
|------|------------|
| `pc_agent/core/orchestrator.py` | Фасад orchestrator-команд: dispatch, run_tool, collect/list/update, lifecycle операций, orchestration над `ConsentService`, кэш модулей; collect/job/uptime ветки полностью делегированы в helper-модули, cancel-operation flow доведён до канонического agent-side terminal результата и ticket event publish; update path is single-flight over `pending_update.json`, writes per-operation download artifacts, and returns `"scheduled"` only after shutdown-for-update is truly armed; `run_tool`, `list_tools` и `describe_tool` теперь резолвят канонический semantic tool id и legacy aliases через текущий registry без отдельного V2-контура, а observer drilldown получает guaranteed action-trace breakdown по `module.resolve` и `module.execute` даже для “молчащих” модулей; server `trace_id` прокидывается в orchestrator/module action trace для точной diagnostics bundle корреляции; execution path теперь lane-aware: risky/stateful tools serialise through a single execution lane, while safe read-only tools keep limited parallelism |
| `pc_agent/core/action_trace.py` | Локальный JSONL action trace для tech drilldown и поиска по `trace_id` / `ticket_id` / `operation_id` / `tool_name`; теперь служит обязательным fallback-слоем module-level observability, если модуль не пишет собственный runtime audit, а все writes проходят через redaction helpers; also exports compact upload-ready `agent_observer_events` with stable sequence/event ids for startup/reconnect/update/tool/module telemetry; observer expansion rules описаны в `server/docs/OBSERVER_AUTHORING_RULES.md` |
| `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py`, `pc_agent/core/orchestrator_shared.py` | Helper-слой распила orchestrator: каноническая collect/job/uptime логика и общий mojibake-safe logger; в `orchestrator.py` не должно оставаться дублированных тел этих handler-веток |
| `pc_agent/core/consent_service.py` | Отдельный lifecycle consent (`WAITING_USER/APPROVED/REJECTED/EXPIRED`) поверх `pending_consents` |
| `pc_agent/core/database.py` | SQLite (data/storage.db), outbox, seq, idempotency, consent, scheduled_tasks, DB_SCHEMA_VERSION |
| `pc_agent/core/sender.py` | WSOutboxFlusher: доставка outbox, ACK/NACK, retries; если сервер объявил `outbox_batch_v1`, flusher может отправлять несколько `outbox_item` одним `outbox_items_batch` frame без изменения per-item ACK/NACK semantics |
| `pc_agent/core/identity.py` | Каноническая identity агента: `machine_id` -> `device_id`, вторичный `install_id`, миграция legacy `identity.json`, handshake metadata включая `device_fingerprint` |
| `pc_agent/core/device_fingerprint.py` | Best-effort hashed hardware proof для provisioning/handshake: Windows default path avoids WMI/PowerShell by using MachineGuid, WinAPI boot volume, CPU signature and MAC hashes; optional baseboard WMI is gated by `PC_AGENT_ENABLE_WMI_FINGERPRINT=1`; raw serial/MAC не отправляются |
| `pc_agent/core/machine_identity.py` | Разрешение стабильного `machine_id` из OS/runtime (Windows MachineGuid, Linux machine-id, env override, fallback file) |
| `pc_agent/core/module_manager.py` | Установка/удаление/rollback модулей, semver, инвентарь |
| `pc_agent/core/loader.py` | load_module_from_path (modules_store), сброс кэша импорта |
| `pc_agent/core/registry.py` | Дескрипторы инструментов, canonical tool id/alias → runtime method, `call_tool()`; public tool name может быть semantic key (`dns.resolve`), а legacy `module.tool` остаётся alias; `@exposed_tool` прокидывает `output_schema` и `output_contract` в tool specs |
| `pc_agent/core/tools.py` | Agent-side tool spec helpers над shared contract layer; legacy risk aliases живут здесь только как compatibility shim |
| `pc_agent/core/policy_engine.py` | Политики выполнения |
| `pc_agent/core/artifacts.py` | Артефакты (screenshot/record) |
| `pc_agent/core/recording_controller.py` | Управление записью |
| `pc_agent/core/job_manager.py` | Джобы |
| `pc_agent/core/runtime_logging.py` | Единая настройка runtime-логирования: loguru sink, rotation/retention/compression, чтение tail для diagnostics |
| `pc_agent/core/runtime_paths.py` | Пути данных/модулей |
| `pc_agent/core/single_instance.py` | Один экземпляр приложения |
| `shared/tool_contracts.py` | Общий vocabulary для server+agent: canonical risk/lifecycle/error/artifact/dependency/execution-envelope models |

### 2.2 Модули (modules/)
| Файл/каталог | Назначение |
|--------------|------------|
| `pc_agent/modules/base_module.py` | Базовый контракт модуля + mandatory observer SDK (`bind_trace`, `trace_event`, `trace_span`) для новых tool methods; dangerous module steps обязаны следовать `server/docs/OBSERVER_AUTHORING_RULES.md` |
| `pc_agent/modules/impl/` | Встроенные реализации модулей; core enabled modules are `system`, `screen` and `diag_logs`; `diag_logs.py` collects system logs and agent runtime logs (`data/logs`) through `diag.logs.collect`, so field diagnostics such as `[gui-profiler]` can be retrieved remotely as an artifact |
| `pc_agent/modules/dynamic/` | Legacy (загрузчик использует только пакеты из modules_store) |
| `pc_agent/modules/__init__.py` | extra_paths, поддержка test_<name> для тестов |

### 2.3 Сеть и загрузки
| Файл | Назначение |
|------|------------|
| `pc_agent/network/uploader.py` | Загрузка файлов/артефактов на сервер |

### 2.3.1 Аутентификация и bootstrap подключения
| Файл | Назначение |
|------|------------|
| `pc_agent/auth/token_source.py` | Источник токена: `AUTH_TOKEN` → `auth_tokens` → optional GUI callback; controlled migration локального токена с legacy install-based ID на canonical `machine_id` |
| `pc_agent/auth/connection_request.py` | Connection-request flow: POST/GET polling, approve/reject и события в event_bus; различает обычный reject, `DEVICE_ARCHIVED` и `TOKEN_LIMIT_EXCEEDED`, пишет `connection_request_error.json` для GUI при блокировке сервером и не логирует raw token |
| server observer coupling | Server-side auth/provisioning events are written to `agent_runtime_audit` and projected as operation-less observer traces with `root_kind=device_provisioning` / `agent_auth`; diagnose with `/api/admin/tech/observer/search?q=connection_request` or `q=invalid_token` |
| server explainable observer detail | Admin trace detail is now explained server-side through `/api/web/admin/observer/traces/{trace_id}` / `trace-detail/{trace_id}`. Agent-side action trace and toolset snapshots remain the source for tool/module metadata, but the UI reads normalized `explanation`, stage labels and failure-stage flags from the server boundary instead of interpreting raw agent spans directly. |
| `pc_agent/auth/gui_auth_state_machine.py` | Явные состояния GUI-авторизации (`NoToken -> RequestSent -> Polling -> TokenReady/WsConnecting`); transient blocks `DEVICE_ARCHIVED` и `TOKEN_LIMIT_EXCEEDED` не превращаются в вечный локальный `connection_rejected.flag` |
| `pc_agent/auth/rejected_flag.py` | Путь к локальному флагу `connection_rejected.flag` |

### 2.4 UI bridge (core ↔ GUI)
| Файл | Назначение |
|------|------------|
| `pc_agent/ui_bridge/api_server.py` | Локальный API для GUI (SSE/HTTP), settings + local agent control/diagnostics (`/ui/agent/status`, `/ui/agent/logs`, `/ui/agent/shutdown`, `/ui/agent/update`) |
| `pc_agent/ui_bridge/event_bus.py` | События между core и GUI; хранит sticky `connection_state` для поздних SSE-подписчиков |
| `pc_agent/ui_bridge/models.py` | Модели данных для UI |
| `pc_agent/ui_bridge/settings_service.py` | Настройки для GUI |

### 2.5 GUI (Qt)

New requester-detail slice: `pc_agent/ui_gui/ticket_detail_widgets.py` contains focused Qt Widgets for the redesigned ticket detail page, currently `TicketHeaderWidget`, compact `NextActionCard`, `TicketRightInfoPanel`, `TimelineItemWidget` and `TicketComposerWidget` wired to view models with ticket title/status/actions, resolved-ticket confirm/reject actions in the header menu, requester next action, requester facts, a single visual SLA/deadline block with `SlaProgressBar` rows, access code, optional real device facts, requester-safe system/diagnostic/attachment/user/support timeline events and terminal-status composer disabled states. Mapped requester and specialist message events render as dedicated `TimelineUserMessage` / `TimelineSupportMessage` bubbles instead of centered system cards. The old `ChatPanel` left meta panel and raw access-code/link strip remain only as hidden compatibility objects and are not added to the visible detail layout; missing device/inventory payloads must not be shown as an offline device. Create-ticket wizard result widgets live in `pc_agent/ui_gui/ticket_create_wizard_widgets.py`.
| Файл | Назначение |
|------|------------|
| `pc_agent/ui_gui/main_window.py` | Главное окно (sidebar + dashboard/tickets/profile/create/settings stack), настройки и статусы, sidebar agent-status/update card as the visible online/version/update surface, auto-collapsing sidebar icon rail for focused ticket/create-ticket workspaces, create-ticket navigation switches the workspace synchronously and uses a GUI task helper for async preparation from Qt slots, protected-connection footer under the workspace, секция always-on/tray/logging diagnostics, release badge и кнопка recommended update из локального `ui_bridge`; update CTA now renders explicit `requesting` / `requested` / `pending_restart` states and runs a short refresh burst after an accepted local update request; connection rejected/block events show the server-provided message, including token-limit diagnostics; update/status microcopy is localized for end users; large Qt soft shadows are opt-in through `PC_AGENT_ENABLE_GUI_SHADOWS=1` to avoid focused-window CPU spikes on weak Windows graphics stacks; recording STOP overlay stays a `Qt.Tool` window so it does not create extra `pc_agent` Taskbar/Alt-Tab entries; sidebar/header widgets must be parented or added to layouts before they are shown so blank labels do not become separate `python` top-level windows |
| `pc_agent/ui_gui/performance_probe.py` | Field-only Qt GUI profiler for Windows/RDP/Proxmox CPU investigations; logs `[gui-profiler]` samples with process CPU/RSS/thread deltas, active/focus widget labels, Qt event counters and hot event receivers; default enabled for diagnostic release and disabled with `PC_AGENT_GUI_PROFILER=0` |
| `pc_agent/ui_gui/chat_panel.py` | Чат, создание обращения, reply-to, mark-read, локальные профили инициатора; создание заявки использует request-template catalog, сохраняет `request_template_key` + `ticket_type`, caches server form packs with `request_template_version`, `form_schema_id`/`form_schema_version`, `*_policy_code` and `policy_refs`, and refreshes the cache when server version or normalized policy metadata changes; preserves field-level `visibility`/`process_mapping` metadata and hides requester-invisible internal process fields unless the template explicitly exposes them; renders server-driven priority fields from `field_roles`/`priority_policy`, supports extended form field types including `multi_select`, native `date`/`datetime` controls, registry-backed `user/department/location/device/service_picker` combos and replaceable/clearable `file` fields that contribute attachment paths, sends structured priority facts (`impact_scope`, `work_continuity`, `business_importance`) while keeping the fixed questions only as legacy fallback and preserving `urgency`/`importance` booleans for server compatibility; creation title is user-facing `Обращение: <шаблон>`, wizard step 1 now combines requester-visible type/template cards and compact initiator profile selection without rendering the legacy template search/list/dynamic-field block, dynamic request fields show inline `required_message` errors on scrollable Step 2/Описание, wizard attachment rows include file sizes and pre-submit missing/oversized attachment checks; wizard preview first asks server `/api/tickets/create/preview` for effective queue/priority/response/resolution/approval/diagnostic-consent context, exact due dates and suggested diagnostics, and falls back to local template metadata if unavailable with a non-blocking user warning, without raw SLA wording; scrollable confirmation step has a dedicated process preview without an inline correctness checkbox, post-create success is a real fourth `QStackedWidget` page, and the structured result panel plus `build_post_create_result_labels()` / `build_post_create_process_summary()` explain access code, public/requester status, queue, assignee, next action, approval, diagnostics, response/resolution/expected due dates, passport and requester result summary from `requester_view`/`public_view` before legacy flat fields, with open/add-message/create-another actions; create wizard submit button stays clickable on Step 3 to show validation feedback instead of a silent disabled no-op, asks for data-correctness confirmation after the click and only then starts API create, and submit/preview/screenshot/video Qt slots schedule async work through a GUI task helper instead of direct `asyncio.create_task()`; diagnostic templates can attach a `diagnostic_consent` decision to create payloads; ticket metadata shows dynamic first-response and resolution/workaround deadlines from the server payload with Russian requester-friendly wording ("вам должны ответить до", "решение ожидается до") instead of raw SLA labels; профиль теперь хранит подразделение/здание/кабинет/телефон и при сохранении/выборе синхронизируется в серверный реестр людей и локаций через `TicketApiClient.sync_registry_profile()`; detail refresh разделён на initial tail load, forward catch-up через `since_event_id` и reverse pagination вверх через `before_event_id`, с prepend history и сохранением viewport; unchanged detail polls are fingerprinted before UI rebuild to avoid focused-window repaint churn; список тикетов на `QListView` + модель; runtime path больше не использует deprecated chat client и работает через `TicketApiClient` как канонический GUI contract |
| `pc_agent/ui_gui/tickets_list_model.py` | `TicketsListModel` и `TicketCardDelegate` — обновление строк без полного `clear()`, отрисовка карточек |
| `pc_agent/ui_gui/ticket_format.py` | Подписи/цвета статусов, формат дат, отпечаток строки тикета для диффа модели |
| `pc_agent/ui_gui/ticket_view_models.py` | Requester-facing view-model helpers для нового desktop helpdesk UI: человекочитаемые статусы, локальные сроки, progress/remaining-time SLA view-model fields, optional device visibility, `TicketHeaderViewModel`, `NextActionViewModel` that uses server `next_action_owner`/`first_response_at` facts for clearer requester statuses, `TicketInfoPanelViewModel` и mapping ticket events в безопасные `TimelineItem` для system/diagnostic/attachment/user/support событий без internal notes/raw tool logs |
| `pc_agent/ui_gui/ticket_create_wizard_widgets.py` | Компоненты нового мастера создания обращения; `CreateTicketProgressBar` renders the four-step requester-facing wizard progress, `CreateTicketTypeGrid` renders requester-visible type/template cards while preserving the existing `form_key` selection contract, `CreateTicketConfirmationPanel` renders the confirmation summary and required correctness checkbox before submit, and `CreateTicketSuccessPanel` renders the Step 4/Готово result screen with ticket number, subject, separate access code, requester-facing next action/deadlines and open/add-message/create-another/copy-code actions |
| `pc_agent/ui_gui/theme.py` | Централизованные light/dark theme tokens, QSS-фрагменты для `MainWindow`, `ChatPanel`, sidebar/profile/settings, requester helpdesk objectName/dynamic-property styles via `requester_helpdesk_stylesheet()` (`Card`, `SoftCard`, `NextActionCard`, `InfoCard`, `StatusBadge`, `PrimaryButton`, `SecondaryButton`, wizard cards, `wizardState`, `ticketTypeSelected`, `nextActionStyle`, `statusStyle`), topbar connection-state QSS, `refresh_qss_state()` для repolish и helper-пути для GUI assets/icons |
| `pc_agent/ui_gui/window_chrome.py` | Кастомная frameless-шапка окна для Windows/Linux: логотип/заголовок, minimize/maximize/close, ручной drag/resize без Qt native `startSystemMove()` / `startSystemResize()`, чтобы на Windows не появлялись `_q_titlebar` helper windows в Taskbar/Alt-Tab; resize cursor updates are deduplicated so active RDP/Proxmox windows do not call `setCursor`/`unsetCursor` on every mouse move |
| `pc_agent/ui_gui/assets/icons/` | SVG line-icons для Qt Widgets GUI: navigation, ticket cards, search/filter, chat CTA и update/status actions |
| `pc_agent/ui_gui/server_api.py` | Обращение к серверу из GUI, создание обращений через `/api/tickets/create` с legacy `form_key`, first-class `request_template_key` and optional `diagnostic_consent`, server-backed preview through `/api/tickets/create/preview`, отправка `reply_to`/message metadata, вызов `mark_ticket_read()` и ticket history API с `get_ticket(..., since_event_id=..., before_event_id=..., limit=...)`; `sync_registry_profile()` отправляет локальный профиль инициатора в `/api/registry/profile` для auto-link человека, ПК и здания/кабинета, а `get_registry_options()` читает `/api/registry/options` для picker-полей формы |
| `pc_agent/ui_gui/sse_client.py` | SSE-клиент к ui_bridge |
| `pc_agent/ui_gui/tray_manager.py` | Тонкая cross-platform обёртка над `QSystemTrayIcon`: открыть окно, открыть логи, restart agent, exit agent |
| `pc_agent/ui_gui/tray_notifications.py` | Maps auth-block events (`TOKEN_LIMIT_EXCEEDED`, `DEVICE_FINGERPRINT_MISMATCH`, `DEVICE_ARCHIVED`) to tray/system notifications |
| `pc_agent/ui_gui/consent_dialog.py` | Диалог согласия на операцию |
| `pc_agent/ui_gui/token_dialog.py` | Диалог токена |
| `pc_agent/ui_gui/wait_for_auth_dialog.py` | Диалог ожидания авторизации; читает `connection_request_error.json` и показывает пользователю `TOKEN_LIMIT_EXCEEDED`, когда сервер отказал в выпуске третьего активного токена |

### 2.6 Конфигурация
| Файл | Назначение |
|------|------------|
| `pc_agent/config/config_loader.py` | Загрузка настроек |
| `pc_agent/config/settings.yaml`, `settings.default.yaml` | Конфиг |

### 2.7 Скрипты и тесты
| Путь | Назначение |
|------|------------|
| `pc_agent/scripts/smoke_check_module.py` | Проверка модуля (tool names, resolved methods) |
| `pc_agent/tests/` | Unit/integration тесты |

---

## 3. Быстрый поиск (ключевое слово → файлы)

Используйте поиск по документу, `docs/QUICK_LOOKUP.md` или `scripts/agent_find.py <ключевое_слово> --dir pc_agent`. Ниже — куда смотреть в первую очередь.

- **handshake, protocol_version, ws_ticket_v3** — `ws_agent.py`, `docs/PROTOCOL_V3.md`; handshake diagnostics log the current `PROTOCOL_VERSION` value and must not mention legacy `ws_mcp_v1`
- **outbox, outbox_ack, ACK/NACK** — `core/sender.py`, `core/database.py`, `docs/SENDER.md`
- **run_tool, command** — `core/orchestrator.py`, обработка command/envelope V3 в `ws_agent.py`; current contract accepts canonical semantic tool ids and legacy aliases, while runtime still binds them к текущему module registry
- **schedule_task, cancel_task, list_tasks, task_run_now** — `ws_agent.py` (Scheduler RPC), `core/database.py` (scheduled_tasks storage)
- **device_seq, agent_seq** — тип события только по ним; outbox в `core/database.py`
- **модули (загрузка, registry, rollback)** — `core/module_manager.py`, `core/loader.py`, `core/registry.py`, `core/orchestrator.py` (cached context, rebuild), `modules/__init__.py`
- **инструменты (list_tools, call_tool, aliases, semantic ids)** — `core/registry.py`, `core/tools.py`, `core/orchestrator.py`
- **consent, pending_consents** — `core/consent_service.py`, `core/database.py`, `core/orchestrator.py`, `ui_gui/consent_dialog.py`
- **аутентификация, machine_id, install_id, токен** — `core/identity.py`, `core/machine_identity.py`, `auth/token_source.py`, `auth/connection_request.py`, `docs/AUTHENTICATION.md` (не логировать сырой токен; migration lookup идёт по `machine_id -> install_id -> legacy uuid`)
- **always-on, tray, runtime logs, локальный shutdown/status/logs** — `docs/AGENT_RUNTIME_ALWAYS_ON.md`, `ws_agent.py`, `core/runtime_logging.py`, `ui_gui/main.py`, `ui_gui/tray_manager.py`, `ui_bridge/api_server.py`
- **reprovision_required / invalid token** — `ws_agent.py` (`_request_token_from_console` теперь запускает auto reprovision через `connection_request` flow без ручного ввода)
- **артефакты, upload** — `core/artifacts.py`, `core/recording_controller.py`, `network/uploader.py`
- **self-update, pending_update, update_history, launcher rollback, recommended update UI** — `docs/AGENT_UPDATE_WORKFLOW.md`, `docs/SELF_UPDATE.md`, `launcher/installer.py`, `build_windows_release_v2.py`, `version.py`, `ws_agent.py`, `ui_bridge/api_server.py`, `ui_gui/main_window.py`
  - Update tracing now spans `ws_agent.trigger_recommended_update` -> `core/orchestrator._handle_update` -> `ws_agent_runtime_helpers.shutdown_for_update` -> `launcher/installer.py::apply_update`, all through the shared `core/action_trace.py` recorder / external bridge.
- **update_request_state, pending_restart, truthful scheduled** — `ws_agent.py`, `core/orchestrator.py`, `ui_gui/main_window.py`, `launcher/installer.py`, `launcher/launcher_main.py`
- **GUI, SSE, UI bridge, профили инициатора** — `ui_gui/*`, `ui_bridge/*`
- **agent request-template create/detail smoke** — `ui_gui/chat_panel.py`, `ui_gui/ticket_view_models.py`, `ui_gui/ticket_create_wizard_widgets.py`, `ui_gui/server_api.py`, `tests/test_chat_panel_helpers.py`, `tests/test_ticket_api_client_attachments.py`; live checks should cover server preview, dynamic required/file/picker behavior, explicit required diagnostic-consent hint, diagnostic consent payloads, attachment upload/message refs, requester-safe result labels and success panel, visible diagnostics/deadline/assignment summaries in detail, NextAction/status/timeline view-model mapping, user/support message bubbles, Russian system event text, and observer summary for the created ticket.
- **SQLite, миграции схемы** — `core/database.py` (DB_SCHEMA_VERSION), `docs/DATABASE.md`

---

## 4. Потоки выполнения

- **Boot:** ws_agent.py → IdentityManager, DatabaseManager, AgentOrchestrator, загрузка модулей → WSOutboxFlusher, UI bridge.
- **Agent → Server:** события в outbox → WSOutboxFlusher → WS → outbox_ack (удаление записи) / outbox_nack (retry).
- **Server → Agent:** command по WS → оркестратор (run_tool/module/job) → результат и события в outbox.

---

## 5. Хранилище и миграции

- SQLite: `pc_agent/data/storage.db`. Версия схемы: `core/database.py` (DB_SCHEMA_VERSION). Таблицы: outbox, seq_ticket, seq_device, seen_commands, pending_consents, auth_tokens, scheduled_tasks. См. `docs/DATABASE.md`, `docs/SENDER.md`.

---

## 6. Инварианты

- Protocol version на handshake: `ws_ticket_v3`. Тип события только по device_seq/agent_seq. ACK для outbox = удаление записи. Не логировать сырой токен. Детали: корневой `AGENTS.md`, `docs/PROTOCOL_V3.md`.

---

## 7. Когда обновлять этот CODEMAP

Каноническая карта агента — этот файл: `pc_agent/docs/CODEMAP.md` (других CODEMAP для дерева `pc_agent/` нет).

При изменениях, затрагивающих структуру кода агента, его **нужно** обновить:

- добавление/удаление/перенос ключевых модулей или точек входа в `pc_agent/`;
- новые или переименованные ключевые файлы в core/, modules/, ui_gui/, ui_bridge/;
- смена назначения существующих модулей или потоков.
- если change затрагивает agent-side observer coverage, action trace bridge, module breadcrumbs или dangerous flow instrumentation — синхронно обновлять и `server/docs/OBSERVER_LAYER.md` + `server/docs/OBSERVER_AUTHORING_RULES.md`.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
## 2026-05-09 requester timeline projection

- `pc_agent/ui_gui/ticket_view_models.py::map_ticket_event_to_user_timeline_item()` now prefers server-provided `requester_timeline_text`, `requester_timeline_kind` and `requester_timeline_payload` from `GET /api/tickets/{ticket_id}`.
- The local mapper remains only as an older-server fallback and must hide unknown/debug/internal events instead of showing generic `Обращение обновлено.` or raw `unknown` status text.
- `pc_agent/ui_gui/chat_panel.py` and requester detail widgets consume the resulting `TimelineItem` model; they should not render raw `event_type`, raw tool payload, trace ids, internal notes or worklog data in requester-facing cards.

## 2026-05-09 Remote Assist MVP

- Agent-side Remote Assist starts from `pc_agent/ws_agent.py` handling the server command `remote_assist.request`; it publishes a UI event instead of blocking the WebSocket loop.
- UI entry points are `pc_agent/ui_gui/main_window.py` and `pc_agent/ui_gui/remote_assist_dialog.py`: the user gets a non-blocking consent dialog, an active-session banner, and a user-side end-session action. The consent dialog is retained by session id while open and raised as a topmost Qt dialog so it is not garbage-collected or hidden before the user can approve/deny.
- Windows stable agent `3.1.36` carries the Remote Assist connection-hardening release: browser offers use an explicit recvonly video transceiver, viewer/agent timeouts close failed WebRTC transports, failed sessions are audited, the Maria Agent banner stays in connecting text until ICE is connected, and screen capture reuses its `mss` context to reduce failed-session CPU. Windows stable `3.1.35` remains the interactive-control test release (`SendInput` on Windows, `pynput` on Linux); `3.1.34` remains the prior WebRTC packaging hotfix for bundled `aiortc`/ICE/media dependencies and startup-failure reporting.
- WebRTC/capture/runtime lives under `pc_agent/remote_assist/`: `thread.py` owns a dedicated `QThread` + asyncio loop, `webrtc_client.py` owns aiortc signaling/peer connection and the `control` data channel, `screen_track.py` captures one primary monitor through `mss`, and `input_controller.py` validates interactive-control mouse/keyboard messages before dispatching to the platform input backend (`SendInput` on Windows, `pynput` on Linux). Control is inert unless the approved session mode is `interactive_control` and the operator sends `control_enable`.
- View-only remains the default and all capture/WebRTC/input work must stay outside the GUI thread. No file transfer, clipboard, audio, recording, UAC bypass, or hidden unattended access is active unless a later policy-backed layer explicitly implements and verifies it.
