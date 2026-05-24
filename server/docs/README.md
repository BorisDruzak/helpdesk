# 🚀 PC Agent Server - Документация

![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-Production-brightgreen.svg)
![Protocol](https://img.shields.io/badge/protocol-V3-blue.svg)

> Security note 2026-05-23: `POST /api/login` is admin-only for manual agent-token issue; agent self-provisioning uses `POST /api/connection_request` and protected status polling with `request_id` + `poll_secret`. New web UI login uses `/api/web/session/login` and an httpOnly cookie; legacy `/api/ui_login` is disabled unless explicitly enabled.

> **WebSocket сервер для управления удалёнными PC агентами (relay-архитектура)**

PC Agent Server — это серверная часть системы управления удалёнными агентами. Сервер выступает в роли ретранслятора команд между веб-интерфейсом и агентами, обеспечивая надежную доставку, упорядочивание событий и синхронизацию состояния через Protocol V3 (ws_ticket_v3).

## 📊 Текущее состояние проекта

### Реализованные компоненты

**Протокол V3 (ws_ticket_v3):**
- ✅ Envelope формат для всех сообщений
- ✅ Handshake при подключении с toolset_hash и capabilities
- ✅ Надежная доставка через outbox с подтверждением (outbox_ack/outbox_nack)
- ✅ Поддержка device_seq и agent_seq для корректного упорядочивания событий
- ✅ Device events (без ticket_id) и Ticket events (с ticket_id)
- ✅ Server-side device_outbox для надежной доставки команд
- ✅ Batch ACK для оптимизации доставки
- ✅ Device binding validation
- ✅ Event replay endpoints для синхронизации

**База данных (PostgreSQL):**
- ✅ Ticket, TicketEvent, DeviceEvent модели
- ✅ DeviceOutbox для надежной доставки команд
- ✅ Device registry (devices, device_config, device_toolset_snapshots)
- ✅ Deduplication через UNIQUE constraints
- ✅ Alembic миграции

**WebSocket обработчики:**
- ✅ Agent WebSocket handler (websocket/agent_handler.py)
- ✅ UI WebSocket handler (websocket/ui_handler.py)
- ✅ Event validator для device binding
- ✅ Batch ACK manager
- ✅ Device outbox sender loop

**API endpoints:**
- ✅ Tickets API (создание, список, получение, отправка сообщений)
- ✅ Events API (replay endpoints для ticket_events и device_events)
- ✅ Commands API (отправка команд агентам)
- ✅ Devices API (список устройств, информация об устройстве)
- ✅ Tools API (список инструментов, выполнение команд)
- ✅ Jobs API (управление фоновыми задачами)
- ✅ Chat API (чат с поддержкой)
- ✅ Artifacts API (upload артефактов, secure download с Range для видео)

---

## 📋 Содержание

- [Обзор архитектуры](#обзор-архитектуры)
- [Структура проекта](#структура-проекта)
- [Безопасность и аутентификация](#безопасность-и-аутентификация)
- [Protocol V3 (ws_ticket_v3)](#protocol-v3-ws_ticket_v3)
- [Основные модули](#основные-модули)
- [База данных](#база-данных)
- [API Endpoints](#api-endpoints)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)

---

## 🏗️ Обзор архитектуры

### Relay-архитектура

Сервер выступает в роли **ретранслятора** между веб-интерфейсом и агентами:

```
┌─────────────┐         ┌──────────┐         ┌─────────┐
│  Web UI     │────────▶│  Server  │────────▶│ Agent   │
│  (Browser)  │◀────────│          │◀────────│         │
└─────────────┘         └──────────┘         └─────────┘
                              │
                              ▼
                        ┌──────────┐
                        │PostgreSQL│
                        │ (SoT)    │
                        └──────────┘
```

**Ключевые принципы:**
- Сервер **НЕ выполняет** сбор данных (вся логика на агенте)
- Сервер **только** аутентифицирует, ретранслирует команды и хранит историю
- PostgreSQL — Source of Truth для тикетов, событий и команд
- WebSocket для real-time коммуникации
- Server-side outbox для надежной доставки команд

### Source of Truth (SoT)

**PostgreSQL (SoT для истории):**
- `tickets` — тикеты с device binding
- `ticket_events` — события тикетов (chat messages, command lifecycle)
- `device_events` — события устройств (tools_changed, метрики)
- `device_outbox` — команды к агентам (pending → sent → delivered)
- `devices` — реестр устройств
- `device_config` — конфигурации устройств
- `device_toolset_snapshots` — snapshots инструментов

**StateManager (Runtime данные):**
- `connected_agents` — подключенные агенты (WebSocket)
- `ui_connections` — UI WebSocket подключения
- `chat_sessions` — активные чат-сессии
- `ticket_seen_message_ids` — cache для дедупликации (runtime)

---

## 📁 Структура проекта

```
server/
├── server.py                 # Главная точка входа
├── config.py                 # Конфигурация (DATABASE_URL, SERVER_CAPABILITIES)
├── state_manager.py          # Управление runtime состоянием
├── routes.py                 # Регистрация всех маршрутов
│
├── app/                      # Приложение
│   ├── db/                   # База данных
│   │   ├── models.py         # SQLAlchemy модели (Ticket, TicketEvent, DeviceEvent, DeviceOutbox, Device, DeviceConfig, DeviceToolsetSnapshot)
│   │   ├── engine.py         # Database engine и сессии
│   │   └── migrations/       # Alembic миграции
│   │
│   └── repos/                # Репозитории (data access layer)
│       ├── ticket_events_repo.py
│       ├── device_events_repo.py
│       ├── device_outbox_repo.py
│       ├── devices_repo.py
│       ├── device_config_repo.py
│       ├── toolset_snapshots_repo.py
│       └── job_events_repo.py
│
├── websocket/                # WebSocket обработчики
│   ├── agent_handler.py      # WS агентов: transport-loop; логика в agent_handshake / agent_outbox_ingest / agent_command_result
│   ├── ui_handler.py         # WebSocket handler для UI (chat, subscribe)
│   ├── protocol.py           # Протокол (send_outbox_ack, send_outbox_nack, send_ws_command)
│   ├── validator.py          # EventValidator для device binding
│   ├── batch_ack_manager.py  # Batch ACK накопление и flush
│   └── device_outbox_sender.py  # Sender loop для device_outbox
│
├── api/                      # REST API endpoints
│   ├── events.py             # Event replay endpoints (GET /api/tickets/{id}/events, GET /api/devices/{id}/events)
│   ├── commands.py           # Command endpoints
│   ├── protocol.py           # Protocol documentation endpoint
│   └── admin.py              # Admin endpoints
│
├── tickets/                  # Тикеты (handlers, service)
├── agents/                   # Управление агентами
├── tools/                    # Инструменты
├── chat/                     # Чат с поддержкой
├── jobs/                     # Фоновые задачи
├── modules/                  # Управление модулями
├── auth/                     # Аутентификация
├── uploads/                  # Загрузка файлов
└── static_pages/             # HTML страницы (admin.html, ticket.html, support_console.html)
```

---

## 🔐 Безопасность и аутентификация

- **Агенты:** аутентификация по токену при WebSocket handshake (/ws) и при HTTP API. Agent self-provisioning uses `POST /api/connection_request`; `POST /api/login` is admin-only manual token issue. В БД хранится только SHA256 hash токена.
- **UI:** логин/пароль через `POST /api/ui_login` → выдача UI токена. WebSocket /ws_ui требует первое сообщение `ui_hello` с токеном.
- **HTTP API:** все маршруты `/api/*` (кроме whitelist) защищены middleware: требуется токен в заголовке `Authorization: Bearer <token>`, `Authorization: Token <token>` или `X-Auth-Token`. Whitelist no longer includes `POST /api/login`; legacy `/api/ui_login` is disabled by default.
- **Роли:** `AuthContext` — единственный источник истины для `actor_id` и `actor_role`; данные из JSON/WebSocket payload **никогда** не доверяются для определения роли.

**Подробно:** [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md)

---

## 🔌 Protocol V3 (ws_ticket_v3)

Protocol V3 — современный протокол WebSocket для общения между агентом и сервером. Обеспечивает надежную доставку, упорядочивание событий, идемпотентность команд и синхронизацию состояния.

> **Документация протокола на стороне сервера:** [PROTOCOL_V3.md](PROTOCOL_V3.md). Полная спецификация протокола: `pc_agent/docs/PROTOCOL_V3.md`.

### Ключевые концепции

#### 1. Envelope формат

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
    "actor_role": "server"
  }
}
```

**Обязательные поля:**
- `type` — тип сообщения
- `request_id` — уникальный идентификатор запроса (UUID)
- `device_id` — идентификатор устройства (UUID)
- `protocol_version` — версия протокола (`"ws_ticket_v3"`)
- `payload` — полезная нагрузка сообщения

#### 2. Типы событий

**Device Events (события устройства):**
- Не привязаны к тикету
- Используются для системных событий (tools_changed, метрики)
- Упорядочиваются по `device_seq` (per-device)
- `device_seq IS NOT NULL AND agent_seq IS NULL`

**Ticket Events (события тикета):**
- Привязаны к тикету (`ticket_id`)
- Используются для chat messages, command lifecycle
- Упорядочиваются по `agent_seq` (per-ticket)
- `agent_seq IS NOT NULL AND device_seq IS NULL`

#### 3. Handshake

При подключении агент отправляет `handshake` с capabilities и toolset_hash:

```json
{
  "type": "handshake",
  "protocol_version": "ws_ticket_v3",
  "payload": {
    "token": "auth-token",
    "agent_version": "3.0.0",
    "toolset_hash": "a1b2c3d4e5f6",
    "tools_count": 10,
    "modules": ["system", "screen", "input"]
  },
  "meta": {
    "capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]
  }
}
```

Сервер отвечает `handshake_ack` с server capabilities и desired_revision:

```json
{
  "type": "handshake_ack",
  "payload": {
    "status": "success",
    "server_capabilities": [
      "protocol_v3",
      "envelope_v3",
      "outbox_ack_v3",
      "device_registry",
      "toolset_snapshots"
    ],
    "desired_revision": 1
  }
}
```

**КРИТИЧНО:** Сервер **требует** `protocol_version == "ws_ticket_v3"` (Phase E). Агенты с другой версией протокола отключаются.

#### 4. Outbox Item (outbox_item)

Событие от агента к серверу (из outbox агента):

**Ticket Event:**
```json
{
  "type": "outbox_item",
  "payload": {
    "outbox_id": 123,
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

**Device Event:**
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

#### 5. Outbox ACK/NACK

**Outbox ACK (outbox_ack):**
```json
{
  "type": "outbox_ack",
  "trace_id": "uuid",  // КРИТИЧНО: тот же trace_id, что во входящем envelope
  "payload": {
    "outbox_ids": [123, 124, 125]  // Batch ACK
  }
}
```

**Outbox NACK (outbox_nack):**
```json
{
  "type": "outbox_nack",
  "trace_id": "uuid",
  "payload": {
    "outbox_ids": [123],
    "retryable": false,
    "error": {
      "code": "DEVICE_MISMATCH",
      "message": "Ticket bound to another device"
    }
  }
}
```

**Коды ошибок:**
- `UNKNOWN_TICKET` — тикет не найден (non-retryable)
- `DEVICE_MISMATCH` — тикет привязан к другому устройству (non-retryable)
- `VALIDATION_ERROR` — ошибка валидации (non-retryable)

#### 6. Command (command)

Команда от сервера к агенту:

```json
{
  "type": "command",
  "request_id": "uuid",  // command_id == request_id
  "payload": {
    "command": "list_tools",
    "params": {}
  }
}
```

**КРИТИЧНО:** `request_id` используется как `command_id` (единый идентификатор).

#### 7. Command Result (command_result)

Результат выполнения команды от агента к серверу:

```json
{
  "type": "command_result",
  "request_id": "uuid",  // command_id
  "payload": {
    "status": "success",
    "data": {...},
    "meta": {
      "cached": false
    }
  }
}
```

### Надежная доставка

#### Server-side Device Outbox

Сервер использует **device_outbox** для надежной доставки команд:

1. Команда записывается в `device_outbox` со статусом `pending`
2. `DeviceOutboxSender` loop периодически опрашивает `device_outbox`
3. Команда отправляется агенту и помечается как `sent`
4. При получении `command_result` команда помечается как `delivered`
5. При рестарте сервера pending команды восстанавливаются

**Lifecycle:**
- `pending` → `sent` → `delivered` (успех)
- `pending` → `sent` → `failed` (ошибка)

#### Deduplication

**Ticket Events:**
- UNIQUE constraint на `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`
- Повторная вставка → игнорируется, но отправляется ACK

**Device Events:**
- UNIQUE constraint на `(device_id, device_seq)`
- Повторная вставка → игнорируется, но отправляется ACK

### Device Binding Validation

Каждый тикет строго привязан к `device_id`. События от другого устройства для чужого тикета отклоняются с NACK (`DEVICE_MISMATCH`).

---

## 📦 Основные модули

### 1. WebSocket Handlers

#### Пайплайн WebSocket для агентов (`/ws`)

- **`websocket/agent_handler.py`** — только transport-loop: `websocket_handler`, `AgentMessageRouter`, batch ACK.
- **`websocket/agent_handshake.py`** — handshake, регистрация агента, toolset hash / `list_tools` при необходимости.
- **`websocket/agent_outbox_ingest.py`** — `outbox_item`, валидация, ACK/NACK, сохранение событий.
- **`websocket/agent_command_result.py`** — `command_result`, операции, playbook hooks.

**Ключевые особенности:** Batch ACK (`BatchAckManager`), device binding (`EventValidator`), PostgreSQL через repos. Подробнее — `docs/CODEMAP.md`.

#### `websocket/ui_handler.py`

Обработчик WebSocket для UI клиентов.

**Основные функции:**
- `websocket_ui_handler(request)` — обработчик UI WebSocket соединения

**Обрабатывает:**
- `ui_hello` — аутентификация UI клиента
- `subscribe_chat` — подписка на чат по job_id
- `chat_send` — отправка сообщения в чат
- `run_tool` — вызов инструмента на агенте

#### `websocket/protocol.py`

Протокольные функции для отправки сообщений.

**Основные функции:**
- `send_outbox_ack(ws, outbox_ids, agent_device_id, trace_id)` — отправка outbox_ack
- `send_outbox_nack(ws, outbox_ids, agent_device_id, retryable, error_code, error_message, trace_id)` — отправка outbox_nack
- `send_ws_command(state, device_id, command, params, ...)` — отправка команды через device_outbox
- `push_chat_event_to_ui(state, job_id, event)` — отправка события чата UI клиентам

**КРИТИЧНО:** `trace_id` в ACK/NACK **ДОЛЖЕН** совпадать с `trace_id` из входящего envelope (корреляция).

#### `websocket/validator.py`

Валидатор событий для device binding.

**Основные функции:**
- `EventValidator.validate_event(event, ticket_id, device_id)` — валидация ticket event
- `EventValidator.validate_device_event(event, payload)` — валидация device event

**Проверяет:**
- Существование тикета
- Device binding (ticket.device_id == event.device_id)
- Обязательные поля (event, agent_seq для ticket events)

#### `websocket/batch_ack_manager.py`

Менеджер batch ACK для накопления и отправки ACK батчами.

**Основные функции:**
- `BatchAckManager.add_ack(outbox_id, trace_id)` — добавление ACK
- `BatchAckManager.add_nack(outbox_id, nack_info)` — добавление NACK
- `BatchAckManager.flush(ws, agent_device_id)` — отправка накопленных ACK/NACK

#### `websocket/device_outbox_sender.py`

Sender loop для надежной доставки команд через device_outbox.

**Основные функции:**
- `DeviceOutboxSender.__init__(state_manager, poll_interval)` — инициализация
- `DeviceOutboxSender.start()` — запуск sender loop
- `DeviceOutboxSender.stop()` — остановка sender loop
- `recover_pending_commands()` — восстановление pending команд при старте

**Lifecycle:**
1. Периодически опрашивает `device_outbox` для pending команд
2. Отправляет команды подключенным агентам
3. Обновляет статус команд (`pending` → `sent` → `delivered`)

### 2. Database Models

#### `app/db/models.py`

SQLAlchemy модели для PostgreSQL.

**Основные модели:**
- `Ticket` — тикеты с device binding
- `TicketEvent` — события тикетов (dedupe по `(device_id, ticket_id, agent_seq)`)
- `DeviceEvent` — события устройств (dedupe по `(device_id, device_seq)`)
- `DeviceOutbox` — server-side outbox для команд
- `Device` — реестр устройств
- `DeviceConfig` — конфигурации устройств
- `DeviceToolsetSnapshot` — snapshots инструментов

**Ключевые особенности:**
- UNIQUE constraints для deduplication
- Индексы для эффективных запросов
- JSONB для гибких payload

### 3. Repositories

#### `app/repos/ticket_events_repo.py`

Репозиторий для работы с ticket_events.

**Основные функции:**
- `TicketEventsRepo.add_event(...)` — добавление события с dedupe
- `TicketEventsRepo.get_events(ticket_id, since_agent_seq, limit)` — получение событий тикета
- `TicketEventsRepo.add_command_event(...)` — добавление command lifecycle события

#### `app/repos/device_events_repo.py`

Репозиторий для работы с device_events.

**Основные функции:**
- `DeviceEventsRepo.add_event(...)` — добавление события с dedupe
- `DeviceEventsRepo.get_events(device_id, since_device_seq, limit)` — получение событий устройства

#### `app/repos/device_outbox_repo.py`

Репозиторий для работы с device_outbox.

**Основные функции:**
- `DeviceOutboxRepo.enqueue_command(...)` — добавление команды в outbox
- `DeviceOutboxRepo.get_all_pending_commands(limit)` — получение pending команд
- `DeviceOutboxRepo.mark_sent(command_id, sent_at)` — пометка команды как отправленной
- `DeviceOutboxRepo.mark_delivered(command_id, delivered_at)` — пометка команды как доставленной

#### `app/repos/devices_repo.py`

Репозиторий для работы с devices.

**Основные функции:**
- `DevicesRepo.upsert_on_handshake(...)` — upsert устройства при handshake
- `DevicesRepo.update_last_seen(device_id)` — обновление last_seen_at
- `DevicesRepo.update_toolset_snapshot_ref(device_id, toolset_hash, snapshot_id)` — обновление ссылки на snapshot

#### `app/repos/device_config_repo.py`

Репозиторий для работы с device_config.

**Основные функции:**
- `DeviceConfigRepo.get_or_create_default(device_id)` — получение или создание дефолтной конфигурации
- `DeviceConfigRepo.get_desired(device_id)` — получение desired конфигурации

#### `app/repos/toolset_snapshots_repo.py`

Репозиторий для работы с device_toolset_snapshots.

**Основные функции:**
- `ToolsetSnapshotsRepo.insert_snapshot_if_not_exists(...)` — идемпотентная вставка snapshot
- `ToolsetSnapshotsRepo.get_latest_hash(device_id)` — получение последнего hash

### 4. State Manager

#### `state_manager.py`

Централизованное управление runtime состоянием сервера.

**Основные данные:**
- `connected_agents` — подключенные агенты (device_id → {ws, metadata})
- `ui_connections` — UI WebSocket подключения
- `chat_sessions` — активные чат-сессии
- `ticket_seen_message_ids` — cache для дедупликации (runtime)

**ВАЖНО:** После миграции Protocol V3 StateManager содержит **ТОЛЬКО runtime/эпемерные данные**. Source of Truth для tickets/events/messages — PostgreSQL.

### 5. API Endpoints

#### `api/events.py`

Event replay endpoints для синхронизации.

**Endpoints:**
- `GET /api/tickets/{ticket_id}/events?since_agent_seq=N` — получение событий тикета
- `GET /api/tickets/{ticket_id}/messages` — получение сообщений тикета (shortcut)
- `GET /api/devices/{device_id}/events?since_device_seq=N` — получение событий устройства

**Функции:**
- `handle_get_ticket_events(request)` — обработчик получения событий тикета
- `handle_get_device_events(request)` — обработчик получения событий устройства
- `handle_ticket_messages(request)` — обработчик получения сообщений тикета

#### `api/commands.py`

Command endpoints для отправки команд агентам.

**Endpoints:**
- `POST /api/commands/send` — отправка команды агенту

**Функции:**
- `handle_send_command(request)` — обработчик отправки команды

#### `api/protocol.py`

Protocol documentation endpoint.

**Endpoints:**
- `GET /api/protocol` — документация протокола

---

## 💾 База данных

### PostgreSQL как Source of Truth

После миграции Protocol V3 PostgreSQL является единственным источником истины для:
- Тикетов и их истории
- Событий (ticket_events, device_events)
- Команд (device_outbox)
- Реестра устройств (devices, device_config, device_toolset_snapshots)
- Операций, артефактов, модулей, токенов (см. полный список в [DATABASE.md](DATABASE.md))

**Подробно:** [DATABASE.md](DATABASE.md) — все таблицы, назначение, где используются, репозитории, миграции.

### Схема базы данных (кратко)

#### Таблицы

**tickets:**
- `ticket_id` (PK)
- `device_id` (index) — привязка к устройству
- `title`, `description`, `status`
- `created_at`, `updated_at`

**ticket_events:**
- `id` (PK, BIGSERIAL)
- `ticket_id` (index)
- `device_id`
- `agent_seq` (nullable) — монотонная последовательность per-ticket
- `event_type`, `payload` (JSONB)
- `trace_id`, `event_id`
- UNIQUE constraint: `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`

**device_events:**
- `id` (PK, BIGSERIAL)
- `device_id` (index)
- `device_seq` — монотонная последовательность per-device
- `event_type`, `payload` (JSONB)
- `trace_id`, `event_id`
- UNIQUE constraint: `(device_id, device_seq)`

**device_outbox:**
- `id` (PK, BIGSERIAL)
- `device_id` (index)
- `command_id` — UUID команды (command_id == request_id)
- `trace_id`, `ticket_id`, `job_id`
- `command`, `params` (JSONB)
- `status` — pending → sent → delivered/failed
- `created_at`, `sent_at`, `delivered_at`
- `retry_count`, `last_error`

**devices:**
- `device_id` (PK)
- `first_seen_at`, `last_seen_at`, `last_handshake_at`, `last_toolset_refresh_at`
- `protocol_version`, `agent_version`, `hostname`, `os`
- `capabilities` (JSONB), `tools_version`, `current_toolset_hash`
- `current_toolset_snapshot_id`
- `metadata` (JSONB)

**device_config:**
- `device_id` (PK)
- `desired_revision`, `desired_config` (JSONB)
- `applied_revision`, `applied_at`
- `last_apply_status`, `last_apply_error` (JSONB)

**device_toolset_snapshots:**
- `snapshot_id` (PK, BIGSERIAL)
- `device_id`, `captured_at`
- `agent_version`, `toolset_hash`, `toolset_json` (JSONB)
- `tool_count`
- UNIQUE constraint: `(device_id, toolset_hash)`

**modules:**
- `module_name`, `version` (PK, composite)
- `sha256` (unique index)
- `size`, `storage_path`
- `created_at`, `uploaded_by`
- `manifest_summary` (JSONB)

**device_modules:**
- `id` (PK, BIGSERIAL)
- `device_id`, `module_name`, `version` (UNIQUE constraint)
- `installed`, `active`
- `state` (installing|installed|activating|active|failed)
- `installed_at`, `activated_at`, `last_updated_at`
- `last_error_code`, `last_error_message`

### Миграции (Alembic)

Миграции находятся в `app/db/migrations/versions/`:
- `002_add_v3_tables.py` — создание tickets, ticket_events, device_events
- `003_add_device_outbox.py` — создание device_outbox
- `004_add_device_registry.py` — создание devices, device_config, device_toolset_snapshots
- `005_make_agent_seq_nullable.py` — делаем agent_seq nullable для server-originated событий
- `010_add_modules_registry.py` — создание modules, device_modules (HTTP download migration)

---

## 🌐 API Endpoints

**Аутентификация:** все перечисленные ниже `/api/*` маршруты (кроме `/api/login`, `/api/ui_login`, `/api/health`) требуют валидный токен в заголовке `Authorization: Bearer <token>` или `X-Auth-Token`. См. [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md).

### WebSocket Endpoints

- `GET /ws` — WebSocket для агентов (Protocol V3, handshake с токеном обязателен)
- `GET /ws_ui` — WebSocket для UI клиентов (первое сообщение — ui_hello с токеном)

### Tickets API

- `POST /api/tickets/create` — создание тикета
- `GET /api/tickets/{ticket_id}` — получение тикета
- `GET /api/tickets` — список тикетов
- `POST /api/tickets/{ticket_id}/message` — отправка сообщения в тикет
- `POST /api/tickets/{ticket_id}/close` — закрытие тикета
- `GET /api/tickets/{ticket_id}/events` — получение событий тикета (replay)
- `GET /api/tickets/{ticket_id}/messages` — получение сообщений тикета (shortcut)

### Devices API

- `GET /api/devices` — список устройств
- `GET /api/devices/{device_id}/events` — получение событий устройства (replay)

### Commands API

- `POST /api/commands/send` — отправка команды агенту

### Tools API

- `GET /api/tools?device_id=...` — список инструментов с агента (`tools`) и с сервера (`tools_from_server`). Инструменты из `tools_from_server` помечаются в UI как «с установкой» (модуль установится при run_tool).
- `POST /api/tools/run` — выполнение инструмента (тело: `device_id`, `ticket_id`, `tool_name`, опционально `params`, `preset_id`); при agent-token auth `device_id` обязан совпадать с `AuthContext.actor_id`, иначе 403 `DEVICE_CONTEXT_MISMATCH`.

### Modules API

- `POST /api/modules/upload` — загрузка модуля на сервер (multipart, сохраняет ZIP на диск)
- `GET /api/modules/{module_name}/{version}/download` — скачивание ZIP модуля (streaming)
- `GET /api/modules` — список загруженных модулей
- `GET /api/devices/{device_id}/modules` — список модулей на устройстве
- `GET /api/devices/{device_id}/toolset` — получение toolset snapshot устройства
- `POST /api/devices/{device_id}/modules/install` — установка модуля на устройство
- `POST /api/devices/{device_id}/modules/activate` — активация модуля
- `POST /api/devices/{device_id}/modules/deactivate` — деактивация модуля
- `POST /api/devices/{device_id}/modules/sync` — синхронизация состояния модулей
- `POST /api/devices/{device_id}/modules/remove_version` — удаление версии модуля
- `POST /api/devices/{device_id}/modules/remove` — удаление модуля
- `POST /api/install_module_package` — legacy endpoint (backward compatibility)

**Подробнее:** [MODULES_API.md](MODULES_API.md)

### Jobs API

- `GET /api/job_events?job_id={job_id}` — получение событий job (query-параметр `job_id`)
- `POST /api/start_job` — запуск job

### Chat API

- `POST /api/chat_start` — запуск чата
- `POST /api/chat_raise` — создание чата от агента
- `POST /api/chat_send` — отправка сообщения в чат
- `GET /api/active_chats` — список активных чатов
- `GET /api/chat_events?job_id={job_id}` — получение событий чата (query-параметр `job_id`)

### Artifacts API (скриншоты, запись экрана)

- `POST /api/upload` — загрузка артефакта (multipart: file, опционально ticket_id, operation_id, kind). Только агент. Лимит 200 MB. Идемпотентность по sha256+operation_id.
- `GET /api/artifacts/{artifact_id}/download` — скачивание артефакта с проверкой прав. Поддержка `Range: bytes=...` (206 для видео). Для UI: при артефактах без ticket_id в БД допускается передача `?ticket_id=...` — доступ проверяется по наличию артефакта в событиях тикета.

**Подробнее:** [ARTIFACTS_API.md](ARTIFACTS_API.md)

### Static Pages

- `GET /` — главная страница
- `GET /admin` — админ панель
- `GET /ticket.html` — страница тикета
- `GET /ticket/{ticket_id}` — страница тикета по ID
- `GET /support_console.html` — консоль поддержки

---

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- PostgreSQL 12+
- Зависимости из `requirements.txt`

### Установка

```bash
# Клонировать репозиторий
cd /var/chat_bot/pc_client

# Установить зависимости
pip install -r server/requirements.txt

# Настроить PostgreSQL
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"

# Применить миграции
cd server
alembic upgrade head

# Запустить сервер
python server.py
```

### Конфигурация

Основные параметры в `config.py`:

```python
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8666   # по умолчанию 8666 (переопределяется через config.py)
DATABASE_URL = "postgresql+asyncpg://..."
ENABLE_DB_PERSISTENCE = True
LOG_LEVEL = "DEBUG"
```

### Проверка работы

1. Сервер запущен: `http://localhost:8666/` (порт по умолчанию — 8666)
2. Админ панель: `http://localhost:8666/admin`
3. Protocol docs: `http://localhost:8666/api/protocol`
4. WebSocket для агентов: `ws://localhost:8666/ws`

---

## ⚙️ Конфигурация

### Основные параметры

**`config.py`:**
- `SERVER_HOST`, `SERVER_PORT` — адрес и порт сервера
- `SERVER_PUBLIC_BASE_URL` — публичный URL сервера для скачивания модулей и обновлений агента; **обязательно задать** (IP или hostname), если агенты работают на других машинах (иначе ошибка `MODULE_DOWNLOAD_FAILED`). См. `server/docs/MODULES_API.md`.
- `DATABASE_URL` — строка подключения к PostgreSQL
- `ENABLE_DB_PERSISTENCE` — включить/выключить персистентность
- `LOG_LEVEL` — уровень логирования
- `SERVER_CAPABILITIES` — список capabilities сервера

### SERVER_CAPABILITIES

Список capabilities, которые сервер объявляет агентам:

```python
SERVER_CAPABILITIES = [
    "protocol_v3",
    "envelope_v3",
    "outbox_ack_v3",
    "outbox_nack",
    "trace_correlation",
    "ticket_context",
    "job_context",
    "device_outbox",
    "event_replay",
    "batch_ack",
    "device_binding_validation",
    "device_registry",
    "toolset_snapshots",
    "config_management"
]
```

---

## 📚 Дополнительная документация

- [DATABASE.md](DATABASE.md) — PostgreSQL: таблицы, назначение, где используются, репозитории, миграции
- [TICKET_SYSTEM.md](TICKET_SYSTEM.md) — тикетная система: маршрутизация, SLA, workflow, RBAC, уведомления, очереди, UI, календари, retention (этапы 2–12)
- [KNOWLEDGE_PLATFORM.md](KNOWLEDGE_PLATFORM.md) — universal knowledge platform: spaces/items/versions/chunks, ACL, search/suggestions, helpdesk deflection, support usage and passport drafts
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — безопасность, аутентификация (токены, handshake, middleware)
- [PROTOCOL_V3.md](PROTOCOL_V3.md) — требования сервера к Protocol V3 и ссылка на полную спецификацию
- [Документация агента](../../pc_agent/docs/README.md) — общая документация агента
- [Protocol V3 (агент)](../../pc_agent/docs/PROTOCOL_V3.md) — полная спецификация протокола V3
- [Modules API](MODULES_API.md) — API для управления модулями (HTTP download)
- [Modules Drift and Snapshots](MODULES_DRIFT_AND_SNAPSHOTS.md) — детекция drift и toolset snapshots
- [V3 Migration Complete](../V3_MIGRATION_COMPLETE.md) — статус миграции на Protocol V3

---

## 🔑 Ключевые концепции

### Device Binding

Каждый тикет строго привязан к `device_id`. События от другого устройства для чужого тикета отклоняются с NACK (`DEVICE_MISMATCH`).

### Deduplication

- **Ticket Events:** UNIQUE constraint на `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`
- **Device Events:** UNIQUE constraint на `(device_id, device_seq)`
- Повторная вставка → игнорируется, но отправляется ACK (идемпотентность)

### Надежная доставка

- **Agent → Server:** Outbox pattern на стороне агента + ACK/NACK
- **Server → Agent:** Server-side device_outbox + sender loop + lifecycle tracking

### Trace Correlation

`trace_id` в ACK/NACK **ДОЛЖЕН** совпадать с `trace_id` из входящего envelope для корреляции.

---

## 🛠️ Разработка

### Структура кода

- **Модульная архитектура** — разделение на handlers, services, repos
- **Dependency Injection** — StateManager, database sessions
- **Async/Await** — полностью асинхронный код (aiohttp, asyncpg)
- **Type Hints** — типизация для лучшей читаемости

### Тестирование

- Unit тесты для repositories
- Integration тесты для WebSocket handlers
- E2E тесты для протокола V3

### Миграции

```bash
# Создать миграцию
alembic revision -m "description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

---

## 📝 Лицензия

MIT License

---

## 🙏 Благодарности

- Проект использует Protocol V3 (ws_ticket_v3) для надежной коммуникации
- PostgreSQL как Source of Truth для истории тикетов
- aiohttp для асинхронного WebSocket сервера
- SQLAlchemy для работы с базой данных
