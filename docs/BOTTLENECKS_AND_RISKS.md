# Узкие места и риски проекта pc_client

Документ фиксирует текущие узкие места, технический долг и потенциальные риски агента и сервера. Рекомендуется учитывать при планировании доработок и рефакторинга.

**Дата обновления:** 2026-02-26

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

- В оркестраторе есть закомментированный код, связанный с `pending_tool_calls` и consent; при включении нужно согласовать с текущей моделью consent в БД и с серверной логикой waiting_consent.

### 1.5 ModuleManager и handshake (низкий приоритет)

- В типичном пути `module_manager` создаётся при инициализации оркестратора (orchestrator.py). Риск (edge-case): если оркестратор создан без module_manager, `modules_inventory` в handshake будет пустым — возможны предупреждения в логах и рассинхрон с сервером по модулям.

---

## 2. Сервер (server)

### 2.1 WebSocket handler

- **agent_handler.py** — очень большой монолитный обработчик: handshake, command_result, outbox_item, batch ACK, device/ticket events в одном цикле. Сложно сопровождать и тестировать по частям.
- **Рекомендация:** вынести обработку handshake, outbox_item и command_result в отдельные модули/функции с явными контрактами.

### 2.2 DeviceOutboxSender

- Один общий цикл опроса: раз в 1 с запрашиваются pending команды по всем устройствам (лимит 100 команд за раз). При большом числе устройств и высокой частоте run_tool может стать узким местом.
- **Рекомендация:** при росте нагрузки рассмотреть разделение по устройствам (отдельные очереди/воркеры) или увеличение частоты опроса с сохранением лимитов.

### 2.3 send_ws_command и таймауты

- Синхронное ожидание `command_result` через Future с таймаутом `WS_COMMAND_TIMEOUT` (60 с) держит корутину. При большом числе одновременных вызовов run_tool растёт число висящих корутин и потребление ресурсов.
- **Рекомендация:** ограничение concurrency (семафор) на стороне HTTP/run_tool или переход на асинхронный ответ (polling/WebSocket) для длительных операций.

### 2.4 Два пути run_tool

- Основной поток: `POST /api/tools/run` → `ToolService.run_tool` → создание tool_call_started в БД → `send_ws_command`. Инвариант «tool_call_started до отправки команды» соблюдён.
- Admin API может вызывать отправку команды агенту иным путём; при этом создание tool_call_started должно происходить в том же месте, что и в ToolService, иначе возможны расхождения с документацией [TOOL_CALL_STARTED_INVARIANT.md](../server/docs/TOOL_CALL_STARTED_INVARIANT.md).
- **Рекомендация:** все вызовы run_tool к агенту проводить через ToolService.run_tool (или единый фасад), чтобы гарантировать создание tool_call_started.

### 2.5 Коды ошибок outbox_nack

- В документации протокола перечислены коды UNAUTHORIZED, RATE_LIMIT и др. На сервере при невалидном handshake соединение закрывается с кодом 4003, без outbox_nack. В outbox_nack реально используются UNKNOWN_TICKET, DEVICE_MISMATCH, VALIDATION_ERROR, SERVER_ERROR. Коды UNAUTHORIZED и RATE_LIMIT в коде не возвращаются.
- **Риск:** агент или мониторинг могут ожидать эти коды; при необходимости их стоит добавить в контракт и в код.

### 2.6 TODO в коде (выдержка)

| Файл | Содержание |
|------|------------|
| websocket/ui_handler.py | user_id check при подписке — отложено до появления user_id (см. Phase 3) |
| state_manager.py | В production — DB-backed хранилище (см. Phase 3, BOTTLENECKS) |
| auth/service.py | verify_token — legacy sync; предпочтителен async verify_agent_token/verify_ui_token |
| chat/service.py | owner_uuid — заполняется из connected_agents при создании сессии (Phase 3) |

**Архивный код:** `server_old.py` помечен как ARCHIVED, не участвует в runtime. TODO в этом файле не входят в рабочий бэклог.

---

## 3. Модули

### 3.1 Документация vs код (ModuleManager) — исправлено

- **Исправлено:** в `pc_agent/docs/MODULES.md` приведён реальный API ModuleManager: `install_zip_bytes`, `activate`, `deactivate`, `rollback`, `list_installed`, `get_active_path`, `remove_version`, `remove_version_force`, `remove_module`. См. pc_agent/docs/MODULES.md.

### 3.2 Handshake: modules vs modules_inventory

- В handshake в payload уходят и `modules` (enabled_modules из конфига), и `modules_inventory` (установленные пакеты с версиями). Синхронизация device_modules на сервере идёт по **modules_inventory**. В документации протокола это не везде явно разделено — обновлено в pc_agent/docs/PROTOCOL_V3.md.

### 3.3 SERVER_PUBLIC_BASE_URL

- URL для скачивания модулей агентом строится из `SERVER_PUBLIC_BASE_URL` (server/config.py). Текущий дефолт в коде: `http://192.168.100.17:{SERVER_PORT}`. В **production** обязательно задавать `SERVER_PUBLIC_BASE_URL` явно через env; дефолт считается только dev-safe. Если агент на другой машине, URL должен быть доступен с хоста агента. Неверная настройка ведёт к ошибкам вида MODULE_DOWNLOAD_FAILED. Описано в server/docs/MODULES_API.md.

---

## 4. Протокол V3

### 4.1 Сильные стороны (кратко)

- Единый envelope; чёткое разделение device_event / ticket_event по device_seq / agent_seq.
- Outbox pattern на агенте; идемпотентность команд и RPC; device binding на сервере; trace_id в ACK/NACK; toolset_hash и tools_changed.

### 4.2 Слабые стороны (кратко)

- Агент: асинхронный handle_ack без ожидания; дубль выполнения при in_progress и падении; scheduler — заглушки.
- Сервер: монолитный handler; один цикл DeviceOutboxSender; синхронное ожидание в send_ws_command; не все коды NACK из спецификации реализованы.

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
- [server/docs/MODULES_API.md](../server/docs/MODULES_API.md) — API модулей, SERVER_PUBLIC_BASE_URL.
- [pc_agent/docs/MODULES.md](../pc_agent/docs/MODULES.md) — модули агента, реальный API ModuleManager.
