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
    "token": "auth-token",
    "hostname": "hostname",
    "os": "Linux",
    "agent_version": "3.0.0",
    "db_schema_version": 8,
    "tools_version": "tools_v1",
    "toolset_hash": "a1b2c3d4e5f6",
    "tools_count": 10,
    "modules": ["system", "screen", "input"]
  },
  "meta": {
    "timestamp": "2026-01-08T21:10:57.027006+00:00",
    "actor_role": "agent",
    "capabilities": ["protocol_v3", "envelope_v3"]
  }
}
```

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

### Command Result (command_result)

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
- `partial` — частичный результат (для долгих операций)

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
- Если команда была начата (status=in_progress), выполняется повторно
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
2. WSOutboxFlusher периодически отправляет pending события
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

Текущая версия: `8`

**История изменений:**
- v1 → v2: Добавлен outbox pattern
- v2 → v3: Добавлен seq_ticket для agent_seq
- v3 → v4: Добавлен seq_device для device_seq
- v4 → v5: Добавлена таблица seen_commands для идемпотентности
- v5 → v6–v7: Дополнительные таблицы (ticket_state, scheduled_tasks, seen_messages и др.)
- v7 → v8: Добавлена таблица auth_tokens для хранения токена авторизации

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

### device_id (UUIDv4)

Protocol V3 (замечание 1.7): `device_id` всегда должен быть **UUIDv4**. IdentityManager валидирует и регенерирует при невалидном формате.

**Подробнее:** [AUTHENTICATION.md](AUTHENTICATION.md)

## Handshake: payload.modules и modules_inventory

- **payload.modules** — список имён включённых модулей из конфига (`enabled_modules`), для совместимости.
- **payload.modules_inventory** — полный список установленных пакетов с версиями и состоянием (active/installed). Сервер синхронизирует таблицу `device_modules` по **modules_inventory**; при его отсутствии ставит в очередь команду `list_installed_modules`.

## Идемпотентность RPC (idempotency_key)

Для методов из `IDEMPOTENT_METHODS` (ticket_open, ticket_closed, start_job, stop_job, run_tool, schedule_task, cancel_task, task_run_now) в `rpc_request` может требоваться **idempotency_key**. Ответ кэшируется в БД (`rpc_idempotency_cache`) с TTL 1 час (`IDEMPOTENCY_TTL_SECONDS`); при повторном запросе с тем же ключом возвращается кэшированный результат.

## Scheduler (заглушки)

Методы `schedule_task`, `cancel_task`, `list_tasks`, `task_run_now` объявлены в протоколе, но на агенте возвращают **NOT_IMPLEMENTED** — функциональность запланирована, не реализована.

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

- **handle_ack асинхронный без ожидания:** на агенте `handle_ack()` запускает `_handle_ack_async()` через create_task и не ждёт завершения; при очень быстром повторном claim теоретически возможна гонка.
- **Command in_progress:** при статусе in_progress команда выполняется повторно; при падении агента после mark_command_started и до mark_command_seen возможен дубль при retry.
- **Scheduler не реализован:** методы планировщика — заглушки NOT_IMPLEMENTED.
- **Один цикл DeviceOutboxSender на сервере:** один poll по всем устройствам (интервал 1 с, лимит команд за раз); при большой нагрузке может стать узким местом.
- **Синхронное ожидание send_ws_command:** ожидание Future по таймауту (WS_COMMAND_TIMEOUT) держит корутину; при большом числе одновременных run_tool растёт число висящих задач.
- **Коды UNAUTHORIZED/RATE_LIMIT в NACK:** в документации перечислены, в коде сервера при handshake используется закрытие с кодом 4003 без отдельного кода UNAUTHORIZED; RATE_LIMIT не возвращается в outbox_nack.

Подробнее об узких местах и рисках: [BOTTLENECKS_AND_RISKS.md](../../docs/BOTTLENECKS_AND_RISKS.md) (в корне проекта).

## Ссылки

- [AUTHENTICATION.md](AUTHENTICATION.md) — аутентификация и безопасность
- [DatabaseManager документация](DATABASE.md) — детали работы с базой данных
- [WSOutboxFlusher документация](SENDER.md) — детали отправки событий
- [AgentOrchestrator документация](ORCHESTRATOR.md) — обработка команд
- [BOTTLENECKS_AND_RISKS.md](../../docs/BOTTLENECKS_AND_RISKS.md) — узкие места и риски проекта


