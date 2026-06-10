# Protocol V3 (ws_ticket_v3) - Документация

## Обзор

Protocol V3 (`ws_ticket_v3`) — это современный протокол WebSocket для общения между агентом и сервером. Протокол обеспечивает надежную доставку сообщений, упорядочивание событий, идемпотентность команд и синхронизацию состояния.

## Версия протокола

- **Протокол:** `ws_ticket_v3`
- **Версия схемы БД:** `8` (v8: добавлена таблица auth_tokens)
- **Версия агента:** `3.0.0`

## Ключевые концепции

### 1. Envelope формат

Все сообщения в протоколе V3 оборачиваются в **envelope** (конверт) с метаданными:

```json
{
  "type": "message_type",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "token": "auth-token",
  "trace_id": "uuid",
  "ticket_id": "uuid",
  "job_id": "uuid",
  "payload": {...},
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "agent"
  }
}
```

**Обязательные поля:**
- `type` — тип сообщения
- `request_id` — уникальный идентификатор запроса (UUID)
- `device_id` — идентификатор устройства (UUID)
- `protocol_version` — версия протокола (`"ws_ticket_v3"`)
- `payload` — полезная нагрузка сообщения

**Опциональные поля:**
- `trace_id` — идентификатор трассировки для корреляции
- `ticket_id` — идентификатор тикета (для ticket events)
- `job_id` — идентификатор задачи
- `meta` — метаданные (timestamp, actor_role)

### 2. Типы событий

#### Device Events (события устройства)

События устройства **не привязаны** к тикету и используются для системных событий (tools_changed, метрики и т.д.).

**Характеристики:**
- `ticket_id` отсутствует или `null`
- Используют `device_seq` для упорядочивания (монотонная последовательность per-device)
- `agent_seq` = `null`

**Пример:**
```json
{
  "type": "outbox_item",
  "payload": {
    "outbox_id": 123,
    "item_type": "job_event",
    "device_seq": 5,
    "event": {
      "event": "tools_changed",
      "toolset_hash": "a1b2c3d4e5f6",
      "tools_count": 10
    }
  }
}
```

#### Ticket Events (события тикета)

События тикета **привязаны** к конкретному тикету и используются для чата, команд и других действий в контексте тикета.

**Характеристики:**
- `ticket_id` обязателен
- Используют `agent_seq` для упорядочивания (монотонная последовательность per-ticket)
- `device_seq` = `null`

**Пример:**
```json
{
  "type": "outbox_item",
  "ticket_id": "ticket-uuid",
  "payload": {
    "outbox_id": 456,
    "item_type": "job_event",
    "agent_seq": 42,
    "event": {
      "event": "chat_message",
      "from": "user",
      "text": "Hello!"
    }
  }
}
```

### 3. Упорядочивание событий

**Критичный инвариант:**
- Тип события определяется **ТОЛЬКО** через наличие `device_seq` или `agent_seq`
- **НЕ** используйте `ticket_id` для определения типа события

**Правило:**
- `device_event` ⇔ `device_seq IS NOT NULL AND agent_seq IS NULL`
- `ticket_event` ⇔ `agent_seq IS NOT NULL AND device_seq IS NULL`

## Типы сообщений

### Handshake (handshake)

Сообщение при подключении агента к серверу.

**От агента к серверу:**
```json
{
  "type": "handshake",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "payload": {
    "machine_id": "uuid",
    "install_id": "install-uuid",
    "machine_id_source": "windows_machine_guid",
    "hostname": "hostname",
    "os": "Linux",
    "agent_version": "3.0.0",
    "db_schema_version": 9,
    "tools_version": "tools_v1",
    "toolset_hash": "a1b2c3d4e5f6",
    "tools_count": 10,
    "modules": ["system", "screen", "input"],
    "applied_update_version": "3.0.1",
    "last_update_operation_id": "7620e79d-1bdd-496c-9112-28b1d0caf281"
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "agent",
    "capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3", "outbox_batch_v1"]
  }
}
```

Identity v1 invariants for handshake:

- top-level `device_id` is the canonical `machine_id`;
- `payload.machine_id` must match `device_id`;
- `payload.install_id` identifies the current installation only and may change after reinstall or after deleting `identity.json`;
- top-level `token` remains the authentication token source of truth for the handshake.

Reconnect/runtime note:

- The server treats the latest successful handshake for one `device_id` as the current live session.
- If overlapping reconnects create two `/ws` sessions for the same `device_id`, the older websocket may be closed by the server with code **4002** and message `Superseded by newer connection`.
- This is a transport/runtime ownership rule, not a wire-format change.
- Handshake `client_kind` defaults to `agent_runtime`. Real agents omit it or send `agent_runtime`; raw diagnostics may send `diagnostic_probe`, which authenticates for protocol checks but is isolated from runtime dispatch and must not replace the real agent.

Если launcher успешно применил self-update, агент добавляет в следующий `handshake`:
- `payload.applied_update_version` — версия, которую launcher реально активировал;
- `payload.last_update_operation_id` — `operation_id` из `pending_update.json`, сохранённый launcher в `data_root/updates/update_history.json`.

Сервер использует эти поля как post-restart confirmation и только после этого переводит `agent_update` в `succeeded`.

Если launcher не смог применить update и оставил текущую версию, агент добавляет в следующий `handshake`:
- `payload.failed_update_version`
- `payload.failed_update_operation_id`
- `payload.failed_update_reason`
- `payload.failed_update_at`
- `payload.failed_update_message`

Сервер использует эти поля как post-restart failure report и переводит соответствующий `agent_update` в `failed` без ожидания watchdog timeout.

**От сервера к агенту (handshake_ack):**
```json
{
  "type": "handshake_ack",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "payload": {
    "status": "success",
    "message": "Handshake accepted",
    "server_version": "3.0.0",
    "server_capabilities": [
      "protocol_v3",
      "envelope_v3",
      "outbox_ack_v3",
      "outbox_nack",
      "outbox_batch_v1",
      "device_registry",
      "device_config",
      "toolset_snapshots"
    ],
    "desired_revision": 1
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "server"
  }
}
```

### Outbox Item (outbox_item)

Событие от агента к серверу (из outbox агента).

**Формат:**
```json
{
  "type": "outbox_item",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "ticket_id": "uuid",
  "payload": {
    "outbox_id": 123,
    "item_type": "job_event",
    "agent_seq": 42,
    "device_seq": null,
    "event": {
      "event": "chat_message",
      "from": "user",
      "text": "Hello!"
    }
  }
}
```

### Outbox Batch (`outbox_items_batch`)

Опциональный throughput-path для агента: несколько обычных `outbox_item` могут быть отправлены одним WS frame, если `handshake_ack.payload.server_capabilities` содержит `outbox_batch_v1`.

```json
{
  "type": "outbox_items_batch",
  "payload": {
    "items": [
      {"type": "outbox_item", "...": "..."},
      {"type": "outbox_item", "...": "..."}
    ]
  }
}
```

Инварианты:

- batched transport не меняет per-item формат `outbox_item`;
- ACK/NACK остаются per-item по `outbox_id`, даже если отправка была batched;
- при отсутствии `outbox_batch_v1` в `server_capabilities` агент обязан откатиться к одиночным `outbox_item`.

**Для device events:**
```json
{
  "type": "outbox_item",
  "payload": {
    "outbox_id": 124,
    "item_type": "job_event",
    "device_seq": 5,
    "event": {
      "event": "tools_changed",
      "toolset_hash": "a1b2c3d4e5f6"
    }
  }
}
```

### Outbox ACK (outbox_ack)

Подтверждение получения события от сервера к агенту.

**Формат:**
```json
{
  "type": "outbox_ack",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "payload": {
    "outbox_ids": [123, 124, 125]
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "server"
  }
}
```

**Критично:** `trace_id` в ACK **ДОЛЖЕН** совпадать с `trace_id` из входящего envelope (корреляция).

### Outbox NACK (outbox_nack)

Отклонение события с указанием причины (от сервера к агенту).

**Формат:**
```json
{
  "type": "outbox_nack",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "payload": {
    "outbox_ids": [123],
    "retryable": false,
    "error": {
      "code": "DEVICE_MISMATCH",
      "message": "Ticket bound to another device"
    }
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "server"
  }
}
```

**Коды ошибок (справочно):**
- `UNKNOWN_TICKET` — тикет не найден (non-retryable)
- `DEVICE_MISMATCH` — тикет привязан к другому устройству (non-retryable)
- `VALIDATION_ERROR` — ошибка валидации (non-retryable)
- `SERVER_ERROR` — внутренняя ошибка сервера (retryable)

**Текущая реализация:** при невалидном handshake (протокол, capabilities, токен) сервер закрывает соединение с кодом **4003**, не отправляя outbox_nack. В outbox_nack в текущей реализации возвращаются только перечисленные выше коды; `UNAUTHORIZED` и `RATE_LIMIT` в outbox_nack не приходят.

### Command (command)

Команда от сервера к агенту.

**Формат:**
```json
{
  "type": "command",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "ticket_id": "uuid",
  "payload": {
    "command": "list_tools",
    "params": {}
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "server"
  }
}
```

**Критично:** `request_id` используется как `command_id` (единый идентификатор).

`remote_assist.request` is a Protocol V3 command delivered through the normal server device outbox after canonical `UserConsentRequest` approval. Maria Agent must handle it without blocking the WS loop: when `consent_status=approved` is present, the Qt UI treats the user consent as already decided and calls the backend approve HTTP API only for the technical signaling token. Agent GUI approval before the command is done through `/api/registry/agent/consents*` with the same `consent_id` and active requester account session. The WebRTC signaling itself does not run over `/ws`; after technical approval the agent connects to `/ws/remote-assist/{session_id}?role=agent&token=...` with a short-lived role token from the backend. For `mode=elevated_admin`, Protocol V3 never grants hidden administrative access by itself. Approved file-transfer sessions use a separate WebRTC data channel named `file-transfer`; file bytes stay peer-to-peer, while signaling may relay only sanitized `file.transfer` / `file.error` audit envelopes.

### Command Result (command_result)

Terminal `command_result` payloads are durable on the agent until the server
responds with `command_result_ack` carrying the same `request_id`. If the WS is
down or the server restarts after a tool finishes, the agent replays pending
terminal results after reconnect. If the agent process restarts while a
non-resumable command is `in_progress`, startup recovery records a terminal
`status="error"` result with `error.code="AGENT_RESTARTED"` and
`meta.recovery=true`, then sends it through the normal `command_result` path.
Duplicates of that recovered command return the cached terminal error and must
not execute the tool again.

Результат выполнения команды от агента к серверу.

**Формат:**
```json
{
  "type": "command_result",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "trace_id": "uuid",
  "ticket_id": "uuid",
  "payload": {
    "status": "success",
    "data": {
      "observations": {
        "tools": [...]
      }
    },
    "meta": {
      "cached": false
    }
  }
}
```

**Статусы:**
- `success` — команда выполнена успешно
- `error` — ошибка при выполнении команды
- `consent_required` — требуется подтверждение пользователя
- `partial` — legacy/частичный результат (сервер нормализует в terminal lifecycle)

### RPC Request/Response (rpc_request, rpc_response)

RPC-вызовы для выполнения методов (альтернатива command).

**RPC Request:**
```json
{
  "type": "rpc_request",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "payload": {
    "method": "ping",
    "params": {},
    "idempotency_key": "optional-key"
  }
}
```

**RPC Response:**
```json
{
  "type": "rpc_response",
  "request_id": "uuid",
  "device_id": "uuid",
  "protocol_version": "ws_ticket_v3",
  "payload": {
    "status": "success",
    "data": {...}
  }
}
```

## Идемпотентность команд

Агент использует таблицу `seen_commands` для обеспечения идемпотентности команд.

**Ключ идемпотентности:** `request_id` (command_id == request_id)

**Политика:**
- Если команда уже выполнена (status=success), возвращается кэшированный результат
- Если команда в `in_progress` и уже выполняется в текущем процессе, дубликат ждёт тот же Future
- Если команда в `in_progress` и запись свежая (младше `IN_PROGRESS_STALE_SEC`), агент возвращает `command_result.error.code=COMMAND_IN_PROGRESS` с `retryable=true` (без повторного запуска)
- Если `in_progress` stale (старше `IN_PROGRESS_STALE_SEC`), разрешается ровно один controlled retry (с обновлением `started_at`/`owner_instance_id`)
- Политика "не затирать success" — успешные результаты не перезаписываются

**Пример кэшированного ответа:**
```json
{
  "type": "command_result",
  "payload": {
    "status": "success",
    "data": {...},
    "meta": {
      "cached": true,
      "completed_at": 1234567890
    }
  }
}
```

## Toolset Hash

Агент вычисляет `toolset_hash` для синхронизации набора инструментов с сервером.

**Алгоритм:**
1. Получить список инструментов через `_build_tools_list()`
2. Отсортировать по полю `tool` (name)
3. Создать канонический JSON с `sort_keys=True`
4. Вычислить SHA256 hash
5. Взять первые 16 символов hex

**Использование:**
- Отправляется в `handshake` payload
- Используется для определения изменений toolset
- Сервер сравнивает hash и может запросить `list_tools`

## Tools Changed Event

При изменении toolset агент автоматически отправляет `tools_changed` device event:

```json
{
  "event": "tools_changed",
  "toolset_hash": "a1b2c3d4e5f6",
  "tools_count": 10,
  "tools_version": "tools_v1",
  "agent_version": "3.0.0",
  "reason": "registry_rebuilt"
}
```

**Edge Guard:** Событие отправляется только если hash изменился.

## Надежная доставка

### Outbox Pattern

Агент использует **outbox pattern** для надежной доставки событий:

1. Событие записывается в SQLite `outbox` таблицу
2. WSOutboxFlusher периодически отправляет pending события; для mutating/error-sensitive control flow batching включается только после capability negotiation
3. События помечаются как `claimed` с lease временем
4. При получении `outbox_ack` события удаляются из outbox
5. При получении `outbox_nack` события обрабатываются согласно политике retry

### ACK/NACK обработка

**ACK (outbox_ack):**
- Событие успешно получено сервером
- Удаляется из outbox агента
- Batch ACK поддерживается (несколько outbox_ids в одном сообщении)

**NACK (outbox_nack):**
- Событие отклонено сервером
- Если `retryable=true`, событие может быть отправлено повторно
- Если `retryable=false`, событие помечается как failed

## Миграции и версионирование

### Версия схемы БД

Текущая версия: `9`

**История изменений:**
- v1 → v2: Добавлен outbox pattern
- v2 → v3: Добавлен seq_ticket для agent_seq
- v3 → v4: Добавлен seq_device для device_seq
- v4 → v5: Добавлена таблица seen_commands для идемпотентности
- v5 → v6–v7: Дополнительные таблицы (ticket_state, scheduled_tasks, seen_messages и др.)
- v7 → v8: Добавлена таблица auth_tokens для хранения токена авторизации
- v8 → v9: В `seen_commands` добавлены `stale_retry_count` и `owner_instance_id` для controlled retry

### Миграции

Агент автоматически выполняет миграции при старте через `DatabaseManager._migrate_schema()`.

## Безопасность и аутентификация

### Токен в handshake

Токен передаётся в handshake в `payload.token`:

```json
{
  "type": "handshake",
  "payload": {
    "token": "bearer_token_here",
    "uuid": "device_uuid",
    ...
  }
}
```

### Обработка ошибок аутентификации

- Сервер может закрыть соединение с кодом **4003** при невалидном токене.
- Агент при 4003 очищает токен и предлагает повторную авторизацию (GUI или консоль).

### device_id / machine_id / install_id

Protocol V3 identity v1:

- `device_id` is always the canonical `machine_id`;
- `machine_id` must remain stable for the same physical machine;
- `install_id` is secondary metadata for the local installation and is allowed to change independently;
- deleting `identity.json` must not create a new logical device on the server if the agent can still resolve the same `machine_id`.

**Подробнее:** [AUTHENTICATION.md](AUTHENTICATION.md)

## Handshake: payload.modules и modules_inventory

- **payload.modules** — список имён включённых модулей из конфига (`enabled_modules`), для совместимости.
- **payload.modules_inventory** — полный список установленных пакетов с версиями и состоянием (active/installed). Сервер синхронизирует таблицу `device_modules` по **modules_inventory**; при его отсутствии ставит в очередь команду `list_installed_modules`.

## Идемпотентность RPC (idempotency_key)

Для методов из `IDEMPOTENT_METHODS` (ticket_open, ticket_closed, start_job, stop_job, run_tool, schedule_task, cancel_task, task_run_now) в `rpc_request` может требоваться **idempotency_key**. Ответ кэшируется в БД (`rpc_idempotency_cache`) с TTL 1 час (`IDEMPOTENCY_TTL_SECONDS`); при повторном запросе с тем же ключом возвращается кэшированный результат.

## Scheduler MVP

На агенте реализованы RPC-методы:

- `schedule_task`
- `cancel_task`
- `list_tasks`
- `task_run_now`

Ограничения MVP:

- Поддерживается только `kind="run_tool"`.
- Поддерживаются только расписания `minutely | hourly | daily | weekly`.
- `cron`/`timestamp` и другие форматы отклоняются с `VALIDATION_ERROR` (без silent fallback).
- Планировщик выполняет due-задачи через тот же путь `execute_command("run_tool", ...)`, что и обычные команды.
- `cancel_task` отключает задачу (`enabled=0`), `task_run_now` планирует немедленный запуск без удаления расписания.

## Сильные и слабые стороны протокола

### Сильные стороны

- **Единый envelope:** все сообщения в едином формате с request_id, device_id, protocol_version, trace_id, payload — упрощает трассировку и валидацию.
- **Чёткое разделение событий:** device_event (device_seq) vs ticket_event (agent_seq); тип определяется только по seq, не по ticket_id — избегает двусмысленности.
- **Outbox pattern на агенте:** надёжная доставка с ACK/NACK, lease, exponential backoff; события не теряются при обрывах.
- **Идемпотентность:** seen_commands для command, idempotency_key для RPC; защита от дублей при ретраях и реконнектах.
- **Device binding на сервере:** тикет привязан к device_id; события от чужого устройства отклоняются с DEVICE_MISMATCH.
- **Trace correlation:** trace_id в ACK/NACK совпадает с входящим envelope — корреляция запрос/ответ.
- **Toolset hash и tools_changed:** синхронизация набора инструментов с сервером; при изменении — device event и обновление snapshot.

### Слабые стороны и ограничения

- **ACK/NACK под экстремальной нагрузкой:** обработка ACK сериализована `ack_lock` в sender, но при очень высокой интенсивности остаются риски задержек из-за contention по БД/lease.
- **Command in_progress:** агент использует `seen_commands` + process-local `_running_commands`; дубликат с тем же `command_id` ждёт текущий Future, stale `in_progress` (TTL) разрешает controlled retry.
- **Scheduler MVP ограничен:** только `run_tool` и fixed schedules (`minutely|hourly|daily|weekly`), без cron/timestamp и без произвольных видов задач.
- **Server dispatch scalability:** на сервере доступен `sharded` runtime (per-device queue + shard workers), но межпроцессное масштабирование dispatch всё ещё отдельный этап.
- **Ожидание send_ws_command:** синхронный режим по-прежнему используется частью API, но transport поддерживает `wait_for_result=False` для async enqueue без долгого удержания корутины.
- **Коды UNAUTHORIZED/RATE_LIMITED в NACK:** до handshake auth failure по-прежнему закрывает соединение кодом 4003; post-handshake message-level reject возвращается через `outbox_nack` (`UNAUTHORIZED`, `RATE_LIMITED`).

Подробнее об узких местах и рисках: [BOTTLENECKS_AND_RISKS.md](../../docs/archive/BOTTLENECKS_AND_RISKS.md) (исторический архив).

## Ссылки

- [AUTHENTICATION.md](AUTHENTICATION.md) — аутентификация и безопасность
- [DatabaseManager документация](DATABASE.md) — детали работы с базой данных
- [WSOutboxFlusher документация](SENDER.md) — детали отправки событий
- [AgentOrchestrator документация](ORCHESTRATOR.md) — обработка команд
- [BOTTLENECKS_AND_RISKS.md](../../docs/archive/BOTTLENECKS_AND_RISKS.md) — исторические узкие места и риски проекта
## 2026-05-13 Agent Recipe command

`run_recipe` is a Protocol V3 command handled by the agent orchestrator as an internal bridge to the protected managed
module `agent_recipe_runner`. The agent core does not implement recipe primitives itself: `RecipeRunnerBridge` resolves
the active runner module, checks `min_runner_version`, verifies the requested primitive is supported, delegates
`validate_recipe` / `run_recipe`, and returns a ToolResponse-compatible `command_result`. `run_recipe` is background and
idempotent by operation id like other outbox commands, but it must not be exposed as a normal support-visible tool.
