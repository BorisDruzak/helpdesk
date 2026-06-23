# DatabaseManager - Документация

## Обзор

`DatabaseManager` — это менеджер локальной SQLite базы данных агента (Protocol V3). Обеспечивает надежное хранение событий через outbox pattern, упорядочивание событий через sequences, идемпотентность команд и миграции схемы.

**Файл:** `pc_agent/core/database.py`

Current schema note: `DB_SCHEMA_VERSION = 10`. Version 10 adds
`pending_command_results` for durable terminal `command_result` replay after
server/WS outage and for agent-restart recovery reports.

**Версия схемы:** `10` (v10: durable pending command_result replay)

**Протокол:** `ws_ticket_v3`

## Основные возможности

- ✅ **Singleton pattern** — единственный экземпляр базы данных
- ✅ **Outbox pattern** — надежная доставка событий
- ✅ **Sequences** — упорядочивание событий (agent_seq, device_seq)
- ✅ **Идемпотентность команд** — таблица `seen_commands`
- ✅ **Миграции** — автоматические миграции через `PRAGMA user_version`
- ✅ **Jobs** — управление фоновыми задачами
- ✅ **Idempotency cache** — кэш для RPC вызовов

## Структура базы данных

### Таблица: outbox

Хранилище событий для надежной доставки (outbox pattern).

**Схема:**
```sql
CREATE TABLE outbox (
    outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Context (ОБЯЗАТЕЛЬНО)
    ticket_id TEXT NOT NULL,
    job_id TEXT,
    
    -- Event identity
    event_id TEXT UNIQUE,
    kind TEXT NOT NULL,
    
    -- Event data
    payload_json TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    
    -- Timestamps
    created_at REAL NOT NULL,
    
    -- Sequence (per-ticket для ticket events, per-device для device events)
    agent_seq INTEGER,  -- NULL для device events
    device_seq INTEGER, -- NULL для ticket events
    
    -- Batch support
    batch_seq INTEGER NOT NULL DEFAULT 0,
    
    -- Delivery state (NO 'sent' - ACK → DELETE)
    status TEXT NOT NULL DEFAULT 'pending',
    lease_until REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    
    -- Trace correlation
    trace_id TEXT,
    span_id TEXT,
    
    CHECK (status IN ('pending', 'inflight', 'failed'))
)
```

**Статусы:**
- `pending` — событие ожидает отправки
- `inflight` — событие отправлено, ожидает ACK
- `failed` — событие не удалось доставить

**Инвариант схемы:**
- `device_event` ⇔ `device_seq IS NOT NULL AND agent_seq IS NULL`
- `ticket_event` ⇔ `agent_seq IS NOT NULL AND device_seq IS NULL`

**Критично:** Тип события определяется **ТОЛЬКО** через наличие `device_seq` или `agent_seq`, **НЕ** через `ticket_id`.

### Таблица: seq_ticket

Атомарная генерация `agent_seq` для ticket events (per-ticket).

**Схема:**
```sql
CREATE TABLE seq_ticket (
    ticket_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL DEFAULT 0
)
```

**Использование:**
- Генерирует монотонные последовательности для каждого тикета
- Первый вызов возвращает `1` (не `0`)
- Используется через `next_agent_seq(ticket_id)`

### Таблица: seq_device

Атомарная генерация `device_seq` для device events (per-device).

**Схема:**
```sql
CREATE TABLE seq_device (
    device_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL DEFAULT 0
)
```

**Использование:**
- Генерирует монотонные последовательности для каждого устройства
- Первый вызов возвращает `1` (не `0`)
- Используется через `next_device_seq(device_id)`

### Таблица: seen_commands

`seen_commands` includes runtime ownership metadata (`owner_instance_id`) and
controlled retry counters. On agent startup/reconnect, stale `in_progress` rows
owned by a previous runtime session are finalized as terminal `error` results
with `error.code="AGENT_RESTARTED"` for non-resumable commands. The terminal
result is queued in `pending_command_results` for server replay instead of
silently clearing the row. If the server redelivers that command before the
startup replay path runs, the command handler performs the same single-command
recovery and does not write `command_ack` or rerun the tool.

Идемпотентность команд (кэш результатов).

**Схема:**
```sql
CREATE TABLE seen_commands (
    command_id TEXT PRIMARY KEY,  -- request_id из envelope
    status TEXT NOT NULL,  -- 'success' | 'error' | 'in_progress'
    result_json TEXT,      -- JSON payload (status + data)
    completed_at INTEGER NOT NULL,
    started_at INTEGER      -- Для статуса in_progress
)
```

**Политика:**
- "Не затирать success" — успешные результаты не перезаписываются
- Если есть `error` или `in_progress`, можно перезаписать на `success`
- TTL 14 дней (cleanup)

### Таблица: jobs

### Таблица: pending_command_results

Durable replay queue for terminal server-command results. Rows are written
before sending `command_result` and removed only after `command_result_ack`.
This keeps tool results and agent-restart recovery reports durable across WS
disconnects, server restarts and agent reconnects.

**Schema:**
```sql
CREATE TABLE pending_command_results (
    command_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    trace_id TEXT,
    ticket_id TEXT,
    job_id TEXT,
    actor_role TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
)
```

Управление фоновыми задачами.

**Схема:**
```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    request_id TEXT,
    device_id TEXT,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    meta_json TEXT
)
```

### Таблица: rpc_idempotency_cache

Кэш для RPC вызовов (idempotency).

**Схема:**
```sql
CREATE TABLE rpc_idempotency_cache (
    idempotency_key TEXT PRIMARY KEY,
    method TEXT NOT NULL,
    ticket_id TEXT,
    response_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
)
```

### Таблица: auth_tokens (v8)

Хранение токена авторизации агента для Protocol V3.

**Схема:**
```sql
CREATE TABLE auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    device_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_used_at REAL,
    is_active INTEGER NOT NULL DEFAULT 1
)
```

**Поля:**
- `token` — Bearer/JWT токен (уникальный)
- `device_id` — UUID агента
- `is_active` — 1 = активен (используется только один активный токен на device_id)
- `created_at`, `last_used_at` — метки времени

**API:**
- `save_auth_token(token, device_id)` — сохранить или обновить токен
- `get_auth_token(device_id)` — получить активный токен
- `clear_auth_token(device_id)` — деактивировать токен при ошибке аутентификации

**Источники токена:** ENV `AUTH_TOKEN` → `auth_tokens` → identity.json (legacy). Подробнее: [AUTHENTICATION.md](AUTHENTICATION.md).

## Основные методы

### Инициализация

```python
db_manager = DatabaseManager("data/storage.db")
await db_manager.initialize()
```

**Поведение:**
- Singleton — создается один экземпляр
- Автоматические миграции при старте
- Проверка версии схемы через `PRAGMA user_version`

### Enqueue Event

Добавление события в outbox.

```python
outbox_id = await db_manager.enqueue_event(
    device_id="uuid",
    kind="chat_message",
    payload={"text": "Hello"},
    actor_role="user",
    ticket_id="uuid",
    job_id="uuid",
    trace_id="uuid",
    span_id="uuid",
    batch_seq=0
)
```

**Поведение:**
- Автоматически генерирует `agent_seq` или `device_seq` в зависимости от наличия `ticket_id`
- Если `ticket_id` отсутствует, используется `device_seq` (device event)
- Если `ticket_id` присутствует, используется `agent_seq` (ticket event)

### Sequences

#### next_agent_seq

Генерация следующего `agent_seq` для тикета.

```python
seq = await db_manager.next_agent_seq(ticket_id="uuid")
```

**Поведение:**
- Атомарная операция (BEGIN IMMEDIATE)
- Первый вызов возвращает `1`
- Монотонная последовательность per-ticket

#### next_device_seq

Генерация следующего `device_seq` для устройства.

```python
seq = await db_manager.next_device_seq(device_id="uuid")
```

**Поведение:**
- Атомарная операция (BEGIN IMMEDIATE)
- Первый вызов возвращает `1`
- Монотонная последовательность per-device

### Claim Outbox Batch

Атомарное резервирование событий для отправки.

```python
batch = await db_manager.claim_outbox_batch(limit=20, lease_sec=30)
```

**Поведение:**
- Выбирает `pending` события
- Атомарно помечает как `inflight` с `lease_until`
- Возвращает список событий для отправки

### ACK/NACK обработка

#### delete_outbox_acked

Удаление событий после получения ACK.

```python
await db_manager.delete_outbox_acked(outbox_ids=[123, 124])
```

**Критично:** События **удаляются** из outbox, не помечаются как `sent` (Protocol V3).

#### mark_outbox_failed

Пометка событий как failed.

```python
await db_manager.mark_outbox_failed(
    outbox_ids=[125],
    reason="ack_timeout_exhausted"
)
```

### Идемпотентность команд

#### mark_command_started

Пометка команды как начатой.

```python
await db_manager.mark_command_started(command_id="uuid")
```

#### mark_command_seen

Пометка команды как выполненной.

```python
was_updated = await db_manager.mark_command_seen(
    command_id="uuid",
    status="success",
    result_json='{"status": "success", "data": {...}}'
)
```

**Политика:**
- Если есть `success`, не перезаписывается (возвращает `False`)
- Если есть `error` или `in_progress`, можно перезаписать (возвращает `True`)

#### get_command_result

Получение кэшированного результата команды.

```python
result = await db_manager.get_command_result(command_id="uuid")
```

**Возвращает:**
```python
{
    "status": "success",
    "result_json": '{"status": "success", "data": {...}}',
    "completed_at": 1234567890,
    "started_at": 1234567880
}
```

#### cleanup_seen_commands

Очистка старых записей (housekeeping).

```python
deleted_count = await db_manager.cleanup_seen_commands(
    max_age_days=14,
    max_records=50000
)
```

## Миграции

### Версия схемы

Текущая версия: `10`

**История миграций:**
- v1 → v2: Добавлен outbox pattern
- v2 → v3: Добавлен seq_ticket для agent_seq
- v3 → v4: Добавлен seq_device для device_seq
- v4 → v5: Добавлена таблица seen_commands для идемпотентности
- v5 → v8: Дополнительные таблицы (ticket_state, scheduled_tasks, seen_messages, auth_tokens)
- v8 → v9: `seen_commands` gains controlled retry metadata
- v9 → v10: `pending_command_results` durable terminal result replay

### Автоматические миграции

Миграции выполняются автоматически при старте через `init_db()`:

1. Проверка `PRAGMA user_version`
2. Если версия < текущей → выполнение миграций
3. Обновление `PRAGMA user_version`

**Критично:** Миграции идемпотентны (можно запускать повторно).

## Outbox Pattern

### Жизненный цикл события

1. **Enqueue** — событие записывается в outbox со статусом `pending`
2. **Claim** — событие атомарно помечается как `inflight` с lease временем
3. **Send** — событие отправляется через WebSocket
4. **ACK** — при получении `outbox_ack` событие удаляется из outbox
5. **NACK/Timeout** — при `outbox_nack` или истечении lease событие помечается как `failed`

### Lease механизм

- События резервируются с `lease_until = now() + lease_sec`
- Если lease истекает, событие снова становится `pending` для повторной отправки
- Предотвращает зависание событий в статусе `inflight`

## Примеры использования

### Базовый пример

```python
from core.database import DatabaseManager

db_manager = DatabaseManager("data/storage.db")
await db_manager.initialize()

# Enqueue event
outbox_id = await db_manager.enqueue_event(
    device_id="device-uuid",
    kind="chat_message",
    payload={"text": "Hello"},
    actor_role="user",
    ticket_id="ticket-uuid"
)

print(f"Event enqueued: {outbox_id}")
```

### Claim и отправка

```python
# Claim batch
batch = await db_manager.claim_outbox_batch(limit=20, lease_sec=30)

for item in batch:
    # Отправить через WebSocket
    await send_ws_message(item)
    
    # После получения ACK
    await db_manager.delete_outbox_acked([item['id']])
```

### Идемпотентность команд

```python
# Проверка кэша
cached = await db_manager.get_command_result(command_id="uuid")

if cached and cached["status"] == "success":
    # Возвращаем кэшированный результат
    return json.loads(cached["result_json"])

# Выполняем команду
result = await execute_command(...)

# Сохраняем результат
await db_manager.mark_command_seen(
    command_id="uuid",
    status="success",
    result_json=json.dumps(result)
)
```

## Ссылки

- [Protocol V3 документация](PROTOCOL_V3.md) — протокол общения с сервером
- [AUTHENTICATION.md](AUTHENTICATION.md) — аутентификация и таблица auth_tokens
- [WSOutboxFlusher документация](SENDER.md) — отправка событий
- [AgentOrchestrator документация](ORCHESTRATOR.md) — обработка команд
