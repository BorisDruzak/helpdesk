# Chat Message Contract

## Обзор

Данный документ описывает контракт для события `event_type="chat_message"` в системе Protocol V3. Это событие используется для хранения сообщений в истории чата тикета.

**Дата создания**: 2026-01-10  
**Версия контракта**: 1.0

---

## Структура события

### TicketEvent для chat_message

```python
TicketEvent {
    id: int                    # Database primary key
    ticket_id: str             # UUID тикета
    device_id: str             # Device identifier (для привязки)
    agent_seq: int | null      # КРИТИЧНО: int для agent-originated, NULL для server-originated
    event_type: "chat_message" # Фиксированное значение
    payload: dict              # Полезная нагрузка сообщения (см. ниже)
    trace_id: str | null       # Optional trace ID для корреляции
    event_id: str | null       # Optional event ID от агента
    created_at: datetime       # Timestamp создания в БД
}
```

---

## Payload контракт

### Обязательные поля

```yaml
event_type: "chat_message"
agent_seq: int | null
payload:
  message_id: str          # UUID/string - уникальный ID сообщения (REQUIRED)
  sender_role: str         # "user" | "support" | "system" | "agent" (REQUIRED)
  text: str                # Текст сообщения (REQUIRED)
```

### Опциональные поля

```yaml
payload:
  ts: str                  # ISO8601 timestamp (клиентский)
                           # Если None - используется created_at из БД
  attachments: List[dict]  # Список вложений (по умолчанию: [])
  metadata: dict           # Дополнительные метаданные (опционально)
                           # confirmation_request / confirmation_response для UI-подтверждений
  visibility: str          # Stage 4: "public" | "internal"; по умолчанию public.
                           # Unknown authenticated support/admin values fail with 400 INVALID_VISIBILITY.
                           # Requester projection treats every non-public value as hidden.
                           # Requester может писать только public; support/admin — public или internal.
                           # При чтении requester видит только сообщения с visibility=public.
```

### Structured confirmation metadata

```yaml
payload:
  metadata:
    confirmation_request:
      request_id: str
      kind: str
      title: str
      message: str
      state: "pending" | "completed" | "cancelled"
      options:
        - id: str
          label: str
          style: "primary" | "secondary"
          reply_text: str
    confirmation_response:
      request_id: str
      kind: str
      option_id: str
      label: str
```

- `confirmation_request` используется для показа пользователю кнопок подтверждения в GUI агента.
- `confirmation_response` отправляется клиентом вместе с обычным `text`, чтобы сервер мог обработать ответ как структурированное подтверждение, а не только как свободный текст.

---

## Семантика agent_seq

### КРИТИЧНО: agent_seq принадлежит агенту

`agent_seq` генерируется **только агентом** и является монотонным счетчиком событий от агента.

### Agent-originated события (agent_seq = int)
- Генерируются агентом
- Имеют монотонный `agent_seq` (1, 2, 3, ...)
- Дедупликация через UNIQUE constraint `(device_id, ticket_id, agent_seq)`

**Пример:**
```json
{
    "event_type": "chat_message",
    "agent_seq": 5,
    "payload": {
        "message_id": "msg-agent-1",
        "sender_role": "agent",
        "text": "Hello from agent",
        "ts": "2026-01-10T10:00:00Z"
    }
}
```

### Server-originated события (agent_seq = NULL)
- Генерируются сервером (support/user сообщения через UI)
- **НЕ имеют** `agent_seq` (значение = NULL)
- Дедупликация через проверку `message_id` в логике

**Пример:**
```json
{
    "event_type": "chat_message",
    "agent_seq": null,
    "payload": {
        "message_id": "msg-support-1",
        "sender_role": "support",
        "text": "Support team reply",
        "ts": "2026-01-10T10:05:00Z"
    }
}
```

---

## Сортировка событий

### Правило сортировки

События сортируются по следующему правилу:

```sql
ORDER BY 
    created_at ASC,  -- Global ticket timeline across agent and server events
    id ASC           -- Tie-breaker
```

### Пример результата

```
id  | agent_seq | created_at          | sender_role | text
----|-----------|---------------------|-------------|----------------------
1   | 1         | 2026-01-10 10:00:00 | agent       | "First agent message"
4   | NULL      | 2026-01-10 10:00:03 | support     | "Support reply 1"
2   | 2         | 2026-01-10 10:00:05 | agent       | "Second agent message"
5   | NULL      | 2026-01-10 10:00:08 | support     | "Support reply 2"
3   | 3         | 2026-01-10 10:00:10 | agent       | "Third agent message"
```

**Важно:** `agent_seq` не является primary UI timeline sort key. Server-originated events with `agent_seq=NULL` stay in their chronological position.

---

## Sender Role

### Допустимые значения

- `"user"` - Сообщение от пользователя (обычно initial message при создании тикета)
- `"support"` - Сообщение от support team через UI
- `"agent"` - Сообщение от агента (AI/бот)
- `"system"` - Системное сообщение (автоматически сгенерированное)

### Правила использования

- **Agent-originated** события обычно имеют `sender_role="agent"`
- **Server-originated** события могут иметь `sender_role="support"`, `"user"`, или `"system"`

---

## Attachments

Support UI and authenticated requester UI first upload files through `POST /api/upload` with `ticket_id`, then send a message through
`POST /api/web/support/tickets/{ticket_id}/messages` or `POST /api/web/requester/tickets/{ticket_id}/message` with `attachment_refs: ["<artifact_id>"]`.
The message can contain text, attachments, or both. The server resolves artifact descriptors into
`payload.attachments` and keeps the original `payload.attachment_refs` for stable artifact identity.

### Формат вложений

```json
{
    "attachment_refs": ["att-123"],
    "attachments": [
        {
            "artifact_id": "att-123",
            "type": "image",
            "name": "screenshot.png",
            "url": "/api/artifacts/att-123/download",
            "mime_type": "image/png"
        }
    ]
}
```

### Поддерживаемые типы

- `"image"` - Изображения (png, jpg, gif, etc.)
- `"file"` - Произвольные файлы
- `"video"` - Видео
- `"audio"` - Аудио

---

## Дедупликация

### Agent events (agent_seq IS NOT NULL)

Дедупликация через **частичный UNIQUE constraint** в БД:

```sql
UNIQUE (device_id, ticket_id, agent_seq)
WHERE agent_seq IS NOT NULL
```

Если агент отправит событие с дублирующимся `agent_seq`, БД вернет conflict и событие будет проигнорировано.

### Server events (agent_seq IS NULL)

Server-originated events use a fast repository pre-check plus database unique indexes:

```sql
CREATE UNIQUE INDEX uq_ticket_events_server_event_id
    ON ticket_events (ticket_id, event_id)
    WHERE agent_seq IS NULL AND event_id IS NOT NULL AND btrim(event_id) <> '';

CREATE UNIQUE INDEX uq_ticket_events_server_message_id
    ON ticket_events (ticket_id, event_type, (payload ->> 'message_id'))
    WHERE agent_seq IS NULL AND btrim(COALESCE(payload ->> 'message_id', '')) <> '';
```

`TicketEventsRepo.add_event()` treats these unique-index conflicts as idempotent duplicates and returns `None`. This keeps parallel retries from creating duplicate `ticket_events` rows even when both requests pass the application-level pre-check before either insert commits.

**ВАЖНО:** `message_id` должен быть уникальным в пределах тикета и `event_type` для server events.

Authenticated web chat endpoints accept a client-provided `message_id` as the retry/idempotency key. `POST /api/web/requester/tickets/{ticket_ref}/message` and `POST /api/web/support/tickets/{ticket_id}/messages` must return the already persisted `chat_message` event id when the same `message_id` and the same stable chat payload are submitted again for the same ticket. Non-empty client `message_id` values longer than 120 characters fail with `400 INVALID_MESSAGE_ID`; they must not be silently truncated. A retry with the same `message_id` but different text, visibility, actor/requester context, metadata or attachment refs fails with `409 MESSAGE_RETRY_PAYLOAD_CONFLICT`. A valid retry must not create another `ticket_events` row and must not repeat side effects such as requester workflow transitions, support first-response SLA closure, Observer web-cabinet writes, or realtime ticket pushes.

---

## API Endpoints

### Получение chat messages

#### Endpoint 1: Shortcut для chat messages

```http
GET /api/tickets/{ticket_id}/messages
```

**Query параметры:**
- `since_agent_seq` (optional): Получить сообщения после указанного agent_seq
- `limit` (optional): Максимальное количество сообщений (default: 500)

**Ответ:**
```json
{
    "ticket_id": "...",
    "messages": [
        {
            "message_id": "...",
            "sender_role": "agent",
            "text": "...",
            "ts": "...",
            "agent_seq": 5,
            "attachments": [],
            "created_at": "..."
        }
    ],
    "count": 10
}
```

#### Endpoint 2: Фильтрация событий по типу

```http
GET /api/tickets/{ticket_id}/events?types=chat_message
```

**Query параметры:**
- `since_agent_seq` (optional): Получить события после указанного agent_seq
- `limit` (optional): Максимальное количество событий (default: 1000)
- `types` (optional): Comma-separated список event types

**Ответ:**
```json
{
    "ticket_id": "...",
    "events": [
        {
            "id": 123,
            "ticket_id": "...",
            "device_id": "...",
            "agent_seq": 5,
            "event_type": "chat_message",
            "payload": {
                "message_id": "...",
                "sender_role": "agent",
                "text": "...",
                "ts": "...",
                "attachments": []
            },
            "created_at": "..."
        }
    ],
    "count": 10
}
```

---

## Примеры использования

### Пример 1: Agent отправляет сообщение

```python
# Agent через WebSocket
{
    "msg_type": "outbox_item",
    "command_id": "cmd-123",
    "ticket_id": "ticket-1",
    "agent_seq": 5,  # Монотонный счетчик от агента
    "event_type": "chat_message",
    "payload": {
        "message_id": "msg-agent-5",
        "sender_role": "agent",
        "text": "Analyzing the issue...",
        "ts": "2026-01-10T10:00:00Z",
        "attachments": []
    }
}

# Сохраняется в БД через TicketEventsRepo.add_event()
```

### Пример 2: Support отправляет ответ через UI

```python
# UI через REST API
POST /api/tickets/ticket-1/message
{
    "from_role": "support",
    "text": "Thank you for contacting us!",
    "attachments": []
}

# Сохраняется в БД как:
TicketEvent {
    ticket_id: "ticket-1",
    device_id: "device-1",
    agent_seq: null,  # Server-originated
    event_type: "chat_message",
    payload: {
        "message_id": "msg-support-1",  # Генерируется сервером
        "sender_role": "support",
        "text": "Thank you for contacting us!",
        "ts": "2026-01-10T10:05:00Z",
        "attachments": []
    }
}
```

### Пример 3: UI запрашивает историю чата

```python
# UI запрос
GET /api/tickets/ticket-1/messages?limit=100

# Ответ (отсортировано по правилу)
{
    "ticket_id": "ticket-1",
    "messages": [
        {
            "message_id": "msg-agent-1",
            "sender_role": "agent",
            "text": "Agent message 1",
            "agent_seq": 1,
            "created_at": "2026-01-10T10:00:00Z"
        },
        {
            "message_id": "msg-agent-2",
            "sender_role": "agent",
            "text": "Agent message 2",
            "agent_seq": 2,
            "created_at": "2026-01-10T10:00:05Z"
        },
        {
            "message_id": "msg-support-1",
            "sender_role": "support",
            "text": "Support reply",
            "agent_seq": null,  # Server-originated
            "created_at": "2026-01-10T10:00:03Z"  # Раньше чем agent-2, но идет после
        }
    ],
    "count": 3
}
```

---

## Миграция с legacy state

### До миграции (legacy)

Сообщения хранились в памяти:
```python
state.ticket_messages[ticket_id] = [
    {
        "message_id": "...",
        "from_role": "...",
        "text": "...",
        "timestamp": "...",
        "attachments": []
    }
]
```

### После миграции (Protocol V3)

Сообщения хранятся как ticket_events в БД:
```python
TicketEvent {
    event_type: "chat_message",
    agent_seq: int | null,  # NEW: различие agent/server events
    payload: {
        "message_id": "...",
        "sender_role": "...",  # Было: from_role
        "text": "...",
        "ts": "...",          # Было: timestamp
        "attachments": []
    }
}
```

### Mapping полей

| Legacy                | Protocol V3               |
|-----------------------|---------------------------|
| `from_role`           | `payload.sender_role`     |
| `timestamp`           | `payload.ts`              |
| N/A                   | `agent_seq` (NEW)         |
| In-memory только      | Postgres SoT              |

---

## Валидация

### Обязательные проверки при создании

```python
def validate_chat_message(event: dict) -> bool:
    """Валидация chat_message события."""
    
    # 1. event_type должен быть chat_message
    if event.get("event_type") != "chat_message":
        return False
    
    # 2. payload должен существовать
    payload = event.get("payload")
    if not payload or not isinstance(payload, dict):
        return False
    
    # 3. message_id обязателен
    if not payload.get("message_id"):
        return False
    
    # 4. sender_role обязателен и валиден
    valid_roles = {"user", "support", "agent", "system"}
    if payload.get("sender_role") not in valid_roles:
        return False
    
    # 5. text обязателен
    if not payload.get("text"):
        return False
    
    # 6. agent_seq: если есть - должен быть int, иначе None
    agent_seq = event.get("agent_seq")
    if agent_seq is not None and not isinstance(agent_seq, int):
        return False
    
    return True
```

---

## Ограничения и best practices

### Ограничения

1. **message_id**: Обязателен для дедупликации server events; authenticated web chat accepts up to 120 characters and rejects longer non-empty client IDs with `INVALID_MESSAGE_ID`.
2. **text**: Максимальная длина - ограничена БД (обычно TEXT без лимита)
3. **agent_seq**: Монотонный счетчик (не может уменьшаться)
4. **attachments**: Хранятся как ссылки, не inline данные

### Best practices

1. **Генерация message_id**: Использовать UUID v4 для уникальности. Retries must reuse the same `message_id` only with the same chat payload; changed payloads are conflicts, not idempotent retries.
2. **sender_role**: Всегда указывать явно, не полагаться на defaults
3. **Timestamps**: Использовать ISO8601 формат (`2026-01-10T10:00:00Z`)
4. **Attachments**: Валидировать размер и тип перед сохранением

---

## Совместимость

### Protocol V3 Compatibility

✅ **Fully compatible** с Protocol V3:
- Использует `agent_seq` для agent events
- Поддерживает `agent_seq = NULL` для server events
- Дедупликация через UNIQUE constraint и logic
- Сортировка с NULLS LAST

### Backward Compatibility

⚠️ **Breaking changes** от legacy:
- `from_role` → `sender_role`
- `timestamp` → `ts`
- Новое поле `agent_seq`
- Хранение в БД вместо памяти

**Миграция требуется** при переходе с legacy на Protocol V3.

---

## Changelog

### Version 1.0 (2026-01-10)
- Первая версия контракта
- Поддержка `agent_seq = NULL` для server-originated событий
- Определены обязательные и опциональные поля payload
- Описана семантика сортировки и дедупликации

---

## Ссылки

- **Protocol V3 Migration Plan**: `MIGRATION_POSTGRES_SOT.md`
- **Phase B Report**: `PHASE_B_COMPLETE_REPORT.md`
- **Phase D Report**: `PHASE_D_COMPLETE_REPORT.md`
- **Database Models**: `app/db/models.py`
- **Repository**: `app/repos/ticket_events_repo.py`

---

## Update: 2026-02-13 (Attachment Refs)

### POST /api/tickets/{ticket_id}/message

Request now supports:

```json
{
  "message_id": "msg-uuid",
  "from_role": "user",
  "text": "",
  "attachment_refs": ["artifact-id-1", "artifact-id-2"]
}
```

Rules:
- `attachment_refs` is optional and accepts multiple artifact ids.
- `text` is required only when `attachment_refs` is empty.
- Backward compatibility is kept for legacy input `attachments` (artifact refs are extracted when possible).

Server validation for every ref:
- Artifact must exist.
- Artifact must be bound to the same `ticket_id` or be unbound and claimable for that ticket.
- Artifact `device_id` must match `ticket.device_id`.

Saved `chat_message` payload contains normalized fields:
- `attachment_refs`: string[]
- `attachments`: array of descriptors
- `sender_display_name`: optional display name for requester-originated messages
- `requester_display_name`: optional requester profile name mirrored for UI rendering

Normalized attachment descriptor format:

```json
{
  "artifact_id": "artifact-id-1",
  "type": "image|video|file",
  "filename": "report.txt",
  "url": "/api/artifacts/artifact-id-1/download",
  "size": 12345,
  "mime_type": "text/plain",
  "kind": "file"
}
```

### GET endpoints

Both endpoints now return chat attachments consistently:
- `GET /api/tickets/{ticket_id}` -> `messages[*].attachments` (empty array by default)
- `GET /api/tickets/{ticket_id}/messages` -> `messages[*].attachments` (empty array by default)

---

## Update: 2026-03-27 (Reply, read cursors, chat counters)

### `reply_to` in requester/support messages

`POST /api/tickets/{ticket_id}/message` now also accepts structured reply metadata alongside legacy `metadata`:

```json
{
  "message_id": "msg-uuid",
  "from_role": "user",
  "text": "Уточняю ответ",
  "reply_to": {
    "parent_message_id": "msg-parent",
    "preview": "Предыдущее сообщение",
    "sender_role": "support",
    "sender_display_name": "Поддержка",
    "target_ts": "2026-03-27T10:15:00Z"
  },
  "metadata": {
    "agent_stub_reply_to_message": {
      "source": "agent_gui_stub",
      "target_preview": "Предыдущее сообщение",
      "target_ts": "2026-03-27T10:15:00Z"
    }
  }
}
```

Rules:
- `reply_to.parent_message_id` is optional but preferred; when present it points to `payload.message_id` of the parent `chat_message`.
- `reply_to.preview` is a short UI preview cached in payload for stable rendering even if the original message is not loaded.
- Server normalizes reply data and returns it in message payloads for ticket UI, requester UI and agent GUI.
- Serialized messages also expose `event_id` so clients can scroll to the parent message and advance read cursors.

### Read cursor endpoint

Requester/support clients can mark the visible chat window as read:

```http
POST /api/tickets/{ticket_id}/read
```

Request:

```json
{
  "last_read_event_id": 1842
}
```

Response shape:
- `status: "ok"`
- `ticket_id`
- `last_read_event_id`
- `last_read_message_id`
- `read_scope`: `requester` or `staff`
- `messages_read_count`
- `tool_calls_read_count`
- `no_op` when the cursor was already up to date

Server persists this as `event_type="message_read"` and treats repeated calls with the same or older cursor as idempotent.

Notes:
- `read_scope="requester"` is used both for classic requester sessions and for the desktop agent GUI authenticated with `actor_role="agent"`.
- `read_scope="staff"` is used for `support` / `admin` ticket workspaces.

### Chat counters in ticket payloads

`GET /api/tickets`, `GET /api/tickets/{ticket_id}` and `GET /api/tickets/{ticket_id}/snapshot` now include `ticket.chat_counters` with precomputed queue/UI metrics:

```json
{
  "chat_counters": {
    "requester_unread_messages": 2,
    "requester_unread_tool_calls": 1,
    "support_pending_user_messages": 1,
    "last_user_message_text": "Можно уточнить?"
  }
}
```

Intended usage:
- `requester_unread_messages` / `requester_unread_tool_calls` — badge counters in requester/agent GUI.
- `support_pending_user_messages` — operator queue indicator for unanswered requester messages.
- `last_user_message_text` — compact preview in queue rows/cards.
## Requester timeline projection for chat messages

`chat_message` участвует в общей серверной проекции requester timeline через `server/tickets/requester_timeline.py`. В ответах ticket/detail/timeline рядом с событием могут приходить `requester_timeline_text`, `requester_timeline_kind` и `requester_timeline_payload`; requester UI должен использовать эти поля вместо локального вывода raw `sender_role`, `event_type` или технического payload.

Timeline API reads use `TicketEventsRepo.get_events()` in global `(created_at, id)` order. `agent_seq` is only a replay/idempotency coordinate for agent-originated events and must not group server-originated chat messages after all agent events.

Правила видимости:

- `visibility="internal"` скрывается из requester timeline;
- non-public/unknown `visibility` values are hidden from requester timeline;
- публичный `sender_role=support|admin|operator|staff` становится `support_message`;
- `sender_role=user|requester|agent|device|client` становится `user_message`;
- сообщение с вложениями может получить kind `attachment`, payload содержит только безопасные descriptors вложений;
- сообщение с кодом публичного доступа к заявке отображается как `system_event` с текстом `Код доступа к заявке сформирован.` и не раскрывает сам код в projection payload.

First-response SLA закрывается только публичным сообщением реального support/admin. Internal notes, requester/client-agent messages и системное сообщение с кодом доступа не считаются первым ответом.
