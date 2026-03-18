# Узкие места и риски проекта pc_client

Документ фиксирует текущие узкие места, технический долг и потенциальные риски агента и сервера. Рекомендуется учитывать при планировании доработок и рефакторинга.

**Дата обновления:** 2026-03-18

---

## 1. Агент (pc_agent)

### 1.1 Outbox и ACK

- **handle_ack без ожидания:** В `core/sender.py` метод `handle_ack()` создаёт задачу `_handle_ack_async(outbox_ids)` через `asyncio.create_task()` и не ждёт её завершения. При очень быстром повторном claim теоретически возможна гонка между удалением записей из outbox и следующим batch. На практике снижается за счёт того, что ACK приходит после обработки на сервере.
- **Рекомендация:** при необходимости гарантировать порядок — дожидаться завершения `_handle_ack_async` перед следующим claim или ввести семафор.

### 1.2 Идемпотентность команд

- **Повторное выполнение при in_progress:** Если команда в статусе `in_progress` (mark_command_started уже вызван, но mark_command_seen ещё нет), агент выполняет команду повторно. При падении агента между этими вызовами возможен дубль выполнения при retry с сервера.
- **Рекомендация:** явная политика для in_progress (например, таймаут «считаем мёртвой и разрешаем повтор») или блокировка повторного выполнения до таймаута.

### 1.3 Scheduler

- Методы `schedule_task`, `cancel_task`, `list_tasks`, `task_run_now` объявлены в протоколе и в `SCHEDULER_METHODS`, но на агенте возвращают **NOT_IMPLEMENTED**. Функциональность запланирована, не реализована.
- **Риск:** UI или скрипты могут вызывать эти методы в ожидании рабочего поведения.

### 1.4 Consent и оркестратор

- Consent lifecycle вынесен в `pc_agent/core/consent_service.py` (pending/create/approve/reject/expired через БД). Оркестратор оставлен как orchestration-layer.
- Остаточный риск: часть execution-path всё ещё проходит через legacy-ветви `core/orchestrator.py`; дальнейшая цель — сузить его до policy + execution routing.

### 1.5 ModuleManager и handshake (низкий приоритет)

- В типичном пути `module_manager` создаётся при инициализации оркестратора (orchestrator.py). Риск (edge-case): если оркестратор создан без module_manager, `modules_inventory` в handshake будет пустым — возможны предупреждения в логах и рассинхрон с сервером по модулям.

---

## 2. Сервер (server)

### 2.1 WebSocket pipeline (обновлено)

- **`agent_handler.py`** — тонкий transport-loop (~110 строк): JSON, `AgentMessageRouter`, batch ACK, unregister.
- Бизнес-логика WS-пайплайна перенесена в `agent_services.py` + component-модули (`command_result_components.py`, `outbox_ingest_components.py`).
- `agent_command_result.py` и `agent_outbox_ingest.py` оставлены как thin compatibility wrappers (deprecated-internal), не как runtime hotspot.
- `CommandResultService` теперь выполняет lifecycle/future/artifact/event шаги через отдельные компоненты, а `OutboxIngestService` — validate/guard/dedupe/persist/ack/publish.

### 2.2 DeviceOutboxSender и dispatch

- **По умолчанию** `DEVICE_DISPATCH_MODE=sharded`: очередь готовности по устройству, воркеры по шардам, reconcile (см. `device_outbox_sender.py`). Режим **`poll`** — legacy (единый цикл опроса по устройствам).
- **Узкое место при росте:** весь dispatch в **одном процессе** aiohttp; горизонтальное масштабирование нескольких инстансов без общей очереди/блокировок в БД — отдельный эпик (см. docs/IMPLEMENTATION_PLAN_THIN_HANDLER_OUTBOX_ASYNC.md, B2).

### 2.3 send_ws_command, HTTP run_tool и таймауты

- Транспорт поддерживает `wait_for_result=False`. **Async-режим** для `POST /api/tools/run` (и admin): ответ **202** + `poll_url` на операцию — см. server/docs/RFC_ASYNC_COMMAND_AND_OPERATION_POLL.md.
- **Синхронный путь** (`wait=1` / dev) по-прежнему держит корутину до `command_result` (таймаут `WS_COMMAND_TIMEOUT`). При массовом синхронном вызове — нагрузка на event loop; семафоры `WS_COMMAND_MAX_INFLIGHT_*` ограничивают очередь (при переполнении — отказ).
- **Рекомендация:** в production для длительных операций использовать async + poll; при необходимости — явный пул воркеров или ограничение параллельных sync-вызовов на уровне API-шлюза.

### 2.4 Два пути run_tool

- Основной поток: `POST /api/tools/run` → `ToolService.run_tool` → создание tool_call_started в БД → `send_ws_command`. Инвариант «tool_call_started до отправки команды» соблюдён.
- Admin API может вызывать отправку команды агенту иным путём; при этом создание tool_call_started должно происходить в том же месте, что и в ToolService, иначе возможны расхождения с документацией [TOOL_CALL_STARTED_INVARIANT.md](../server/docs/TOOL_CALL_STARTED_INVARIANT.md).
- **Рекомендация:** все вызовы run_tool к агенту проводить через ToolService.run_tool (или единый фасад), чтобы гарантировать создание tool_call_started.

### 2.5 Коды ошибок outbox_nack

- В outbox pipeline сервер возвращает typed NACK для `UNAUTHORIZED`, `RATE_LIMITED`, `VALIDATION_ERROR`, `SERVER_ERROR`; duplicate events ACK-аются без повторной записи.
- При невалидном handshake соединение по-прежнему закрывается с кодом 4003 (без outbox_nack), это отдельный pre-handshake path.

### 2.6 TODO в коде (выдержка)

| Файл | Содержание |
|------|------------|
| websocket/ui_handler.py | user_id check при подписке — отложено до появления user_id (см. Phase 3) |
| state_manager.py | Runtime-only кэш/сессии; auth/connection-request source-of-truth вынесен в БД |
| auth/service.py | verify_token — legacy sync, оставлен только для internal compatibility |
| chat/service.py | owner_uuid — заполняется из connected_agents при создании сессии (Phase 3) |

**Архивный код:** `server_old.py` помечен как ARCHIVED, не участвует в runtime. TODO в этом файле не входят в рабочий бэклог.

---

## 3. Модули

### 3.1 Документация vs код (ModuleManager) — исправлено

- **Исправлено:** в `pc_agent/docs/MODULES.md` приведён реальный API ModuleManager: `install_zip_bytes`, `activate`, `deactivate`, `rollback`, `list_installed`, `get_active_path`, `remove_version`, `remove_version_force`, `remove_module`. См. pc_agent/docs/MODULES.md.

### 3.2 Handshake: modules vs modules_inventory

- В handshake в payload уходят и `modules` (enabled_modules из конфига), и `modules_inventory` (установленные пакеты с версиями). Синхронизация device_modules на сервере идёт по **modules_inventory**. В документации протокола это не везде явно разделено — обновлено в pc_agent/docs/PROTOCOL_V3.md.

### 3.3 SERVER_PUBLIC_BASE_URL и preflight

- URL для скачивания модулей агентом строится из `SERVER_PUBLIC_BASE_URL` (server/config.py). Текущий дефолт в коде: `http://192.168.100.17:{SERVER_PORT}`. В **production** обязательно задавать `SERVER_PUBLIC_BASE_URL` явно через env; дефолт считается только dev-safe. Если агент на другой машине, URL должен быть доступен с хоста агента. Неверная настройка ведёт к ошибкам вида MODULE_DOWNLOAD_FAILED. Описано в server/docs/MODULES_API.md.
- При старте агент дополнительно проверяет префикс module API (`GET /api/modules/ping` и см. MODULES_API.md).

---

## 4. Протокол V3

### 4.1 Сильные стороны (кратко)

- Единый envelope; чёткое разделение device_event / ticket_event по device_seq / agent_seq.
- Outbox pattern на агенте; идемпотентность команд и RPC; device binding на сервере; trace_id в ACK/NACK; toolset_hash и tools_changed.

### 4.2 Слабые стороны (кратко)

- Агент: асинхронный handle_ack без ожидания; дубль выполнения при in_progress и падении; scheduler — заглушки.
- Сервер: крупные модули command_result/outbox_ingest; dispatch в одном процессе; синхронный run_tool по-прежнему держит корутину; не все коды NACK из спецификации реализованы; multi-instance outbox — впереди.

Подробнее: pc_agent/docs/PROTOCOL_V3.md и server/docs/PROTOCOL_V3.md.

---

## 5. Безопасность

- **Токен в логах:** сырой токен не логируется, только префикс — соответствует правилам проекта.
- **device_id и роль:** на сервере device_id и actor_role берутся только из проверенного токена (БД) и AuthContext, не из payload — документировано в SECURITY_AND_AUTH.md.
- **Пароли UI:** в конфиге USERS пароли могут храниться в открытом виде; для production рекомендуется хеширование и вынос учётных данных в безопасное хранилище (отмечено в SECURITY_AND_AUTH.md).

---

## 6. Связанные документы

- [pc_agent/docs/PROTOCOL_V3.md](../pc_agent/docs/PROTOCOL_V3.md) — полная спецификация Protocol V3, сильные/слабые стороны протокола.
- [server/docs/PROTOCOL_V3.md](../server/docs/PROTOCOL_V3.md) — требования сервера, SERVER_CAPABILITIES, коды NACK.
- [server/docs/COMMAND_RESULT_LIFECYCLE.md](../server/docs/COMMAND_RESULT_LIFECYCLE.md) — инварианты обработки command_result.
- [server/docs/TOOL_CALL_STARTED_INVARIANT.md](../server/docs/TOOL_CALL_STARTED_INVARIANT.md) — создание tool_call_started до отправки run_tool.
- [server/docs/SECURITY_AND_AUTH.md](../server/docs/SECURITY_AND_AUTH.md) — безопасность и аутентификация.
- [server/docs/MODULES_API.md](../server/docs/MODULES_API.md) — API модулей, SERVER_PUBLIC_BASE_URL, `/api/modules/ping`.
- [server/docs/RFC_ASYNC_COMMAND_AND_OPERATION_POLL.md](../server/docs/RFC_ASYNC_COMMAND_AND_OPERATION_POLL.md) — async submit + poll операций.
- [pc_agent/docs/MODULES.md](../pc_agent/docs/MODULES.md) — модули агента, реальный API ModuleManager.
