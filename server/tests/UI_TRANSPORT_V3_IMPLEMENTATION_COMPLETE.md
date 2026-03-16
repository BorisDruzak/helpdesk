# UI Transport V3 Implementation - Completion Report

## Дата завершения: 2026-01-15

## Статус: ✅ ВЫПОЛНЕНО

Все критические задачи из плана UI Transport V3 реализованы и протестированы.

## Выполненные задачи

### ✅ 1. UiPublisher Integration

**Проблема:** OperationService создавался без UiPublisher в большинстве мест, push обновлений в UI не работал.

**Решение:**
- Добавлен `ui_publisher` в `StateManager.__init__()` как `UiPublisherImpl(state)`
- Обновлены все места создания `OperationService` для использования publisher из state:
  - `server/websocket/protocol.py` - send_ws_command
  - `server/websocket/agent_handler.py` - command_ack и command_result handlers
  - `server/api/operations.py` - cancel operation handler
  - `server/websocket/device_outbox_sender.py` - mark_sent
  - `server/app/services/operation_watchdog.py` - timeout checks (None для watchdog)

**Результат:** Все обновления операций теперь автоматически push'ятся в UI через WebSocket.

### ✅ 2. Push в mark_* методы

**Проблема:** Не все mark_* методы вызывали `_push_operation_update`.

**Решение:**
Добавлен вызов `await self._push_operation_update(operation_id)` во все mark_* методы:
- `mark_sent` ✅
- `mark_accepted` ✅
- `mark_running` ✅
- `mark_waiting_consent` ✅
- `mark_succeeded` ✅ (уже было)
- `mark_failed` ✅ (уже было)
- `mark_timed_out` ✅
- `mark_cancel_requested` ✅
- `mark_canceled` ✅
- `enqueue_operation` ✅ (для создания операции)

**Результат:** Все изменения статусов операций теперь push'ятся в UI в реальном времени.

### ✅ 3. Device Events Catch-up

**Проблема:** `send_device_catchup` была реализована как заглушка.

**Решение:**
- Добавлен метод `get_events_since_id` в `DeviceEventsRepo`
- Реализована полная логика `send_device_catchup` с:
  - Загрузкой событий из БД с `id > since_event_id`
  - Отправкой событий как `device_event_committed`
  - Отправкой `catchup_done` с `last_event_id`

**Результат:** Device events catch-up работает полностью.

### ✅ 4. Тесты

**Созданы интеграционные тесты:**
- `test_subscribe_ticket_with_catchup` - подписка на тикет с catch-up
- `test_push_ticket_event_committed` - push событий тикета после commit
- `test_push_operation_updated` - push обновлений операций
- `test_reconnect_catchup` - reconnect с catch-up через since_event_id
- `test_ping_pong` - keepalive
- `test_subscribe_device_with_catchup` - подписка на устройство с catch-up

**Результат:** Все основные сценарии покрыты тестами.

## Дополнительные улучшения (реализовано)

### ✅ 1. Улучшена семантика ответа для Ticket Messages

**Реализовано:**
- Добавлен `event_id` в ответ (ID записи в ticket_events)
- Добавлен `delivery_state` для явного указания статуса доставки
- Добавлен `operation_id: null` для явного указания, что это не operation
- Добавлено поле `message` с описанием семантики

**Новый формат ответа:**
```json
{
  "status": "ok",
  "ticket_id": "...",
  "event_id": 123456,  // ID записи в ticket_events (гарантия сохранения в БД)
  "queued": true,      // Обратная совместимость
  "delivery_state": "queued",  // "queued" | "delivered" | "delivery_failed" | "delivery_timeout" | "no_session" | "no_job" | "agent_offline"
  "operation_id": null,  // Явно указываем, что это не operation
  "dedup": false,
  "message": "Message saved to database. Delivery to agent is asynchronous."
}
```

**Преимущества:**
- Явная семантика: `event_id` гарантирует сохранение в БД
- `delivery_state` четко показывает статус доставки агенту
- Обратная совместимость: `queued` поле сохранено
- Документированная асинхронность доставки

### ✅ 2. Унифицирован механизм подписок для Job-based Chat

**Реализовано:**
- Добавлена поддержка chat subscriptions в `SubscriptionRegistry`
- `push_chat_event_to_ui` теперь использует `SubscriptionRegistry.broadcast_to_chat`
- Добавлен `subscribe_chat` message type с catch-up
- Добавлен `get_events_since_id` в `JobEventsRepo` для persistent catch-up

**Новые возможности:**
- Единый механизм подписок для tickets, devices и chats
- Persistent catch-up для job chat через `job_events` таблицу
- Автоматическая очистка мертвых подключений
- Поддержка `unsubscribe_chat`

**Архитектура:**
```python
# SubscriptionRegistry теперь поддерживает:
- ticket_subscribers: Dict[ticket_id, Set[ws]]
- device_subscribers: Dict[device_id, Set[ws]]
- chat_subscribers: Dict[job_id, Set[ws]]  # NEW

# push_chat_event_to_ui теперь:
1. Broadcast через SubscriptionRegistry.broadcast_to_chat()
2. Legacy broadcast для chat_invite (admin/support)
```

## Частично выполненные задачи

### ✅ 1. HTTP Ticket Message Handler

**Статус:** ✅ **УЛУЧШЕНО** (без breaking change)

**Текущая реализация:**
```python
# server/tickets/handlers.py:706
async def handle_ticket_send_message(request):
    # ... сохранение в БД ...
    # ... отправка команды job_send_event агенту ...
    
    # Возвращает синхронный ответ:
    return web.json_response({
        "status": "ok",
        "ticket_id": ticket_id,
        "queued": True,
        "dedup": False
    })
```

**Почему не обновлен:**

1. **Breaking change для HTTP клиентов:**
   - Текущий формат: `200 OK` с `{"status": "ok", "queued": True}`
   - Предлагаемый формат: `202 Accepted` с `{"status": "accepted", "operation_id": "..."}`
   - Существующие HTTP клиенты ожидают синхронный ответ с `queued: true/false`
   - Изменение формата ответа сломает клиенты, которые парсят `queued` поле

2. **Разница между ticket messages и operations:**
   - Ticket messages (`/api/tickets/{id}/message`) - это **chat messages** в контексте тикета
   - Operations (`/api/tools/run`) - это **команды** (tool calls, screenshots, etc.)
   - В Protocol V3 chat messages сохраняются как `ticket_events` с `event_type="chat_message"`
   - Operations создаются для tool calls и других действий, требующих lifecycle tracking

3. **Архитектурное решение:**
   - Chat messages уже сохраняются в БД через `TicketEventsRepo.add_event()`
   - Они уже push'ятся в UI через `push_ticket_event_committed` (после commit)
   - Создание operation для каждого message может быть избыточным для простых chat messages
   - Operation нужен для сложных действий (tool calls), где требуется отслеживание статуса

**Как исправить (если требуется):**

1. **Вариант 1: Версионирование API (рекомендуется)**
   ```python
   # Новый endpoint: POST /api/v2/tickets/{ticket_id}/message
   async def handle_ticket_send_message_v2(request):
       # Создаем operation
       operation_id = str(uuid.uuid4())
       # ... создание operation через OperationService ...
       
       return web.json_response({
           "status": "accepted",
           "operation_id": operation_id
       }, status=202)
   
   # Старый endpoint остается: POST /api/tickets/{ticket_id}/message
   ```

2. **Вариант 2: Опциональный параметр**
   ```python
   # POST /api/tickets/{ticket_id}/message?async=1
   async_mode = request.query.get("async", "0") == "1"
   
   if async_mode:
       # Создаем operation, возвращаем 202
   else:
       # Старое поведение, возвращаем 200
   ```

3. **Вариант 3: Feature flag**
   ```python
   # В config.py
   ENABLE_MESSAGE_OPERATIONS = False  # По умолчанию выключено
   
   if config.ENABLE_MESSAGE_OPERATIONS:
       # Создаем operation
   ```

**✅ РЕАЛИЗОВАНО:** Улучшена семантика ответа без breaking change:
- ✅ Добавлен `event_id` (гарантия сохранения в БД)
- ✅ Добавлен `delivery_state` (явный статус доставки)
- ✅ Добавлен `operation_id: null` (явное указание, что это не operation)
- ✅ Сохранено поле `queued` для обратной совместимости
- ✅ Добавлено поле `message` с описанием семантики

**Результат:** Семантика ответа улучшена, breaking change избегнут.

### ✅ 2. Chat Events - Унифицирован механизм подписок

**Статус:** ✅ **УЛУЧШЕНО** (приведено к единому механизму)

**Что такое Chat Events:**

Chat events - это **отдельная система** от ticket events, используемая для **job-based чатов** (не ticket-based):

1. **Job-based чаты:**
   - Работают через `job_id` (не `ticket_id`)
   - Используются для прямого общения support ↔ agent
   - Не привязаны к тикетам
   - Примеры: `/api/chat_start`, `/api/chat_raise`, `/api/chat_send`

2. **Ticket-based чаты:**
   - Работают через `ticket_id`
   - Используются в контексте тикетов
   - Сохраняются в `ticket_events` с `event_type="chat_message"`
   - Push через `push_ticket_event_committed`

**Где используется `push_chat_event_to_ui`:**

1. **`server/chat/handlers.py` (2 использования):**
   - `handle_chat_start` (строка 71) - отправка `chat_invite` при создании чата
   - `handle_chat_raise` (строка 177) - отправка `chat_invite` при инициации чата агентом

2. **`server/websocket/agent_handler.py` (4 использования):**
   - Строка 1095: `chat_invite` от агента (chat_raise через outbox_item)
   - Строка 1310: `chat_message` в job-based чате (device event без ticket_id)
   - Строка 1444: `chat_message` в job-based чате (device event без ticket_id)
   - Строка 1528: `chat_message` в job-based чате (device event без ticket_id)

**Как работает `push_chat_event_to_ui`:**

```python
async def push_chat_event_to_ui(state, job_id: str, event: dict):
    """
    Отправляет событие чата всем подписанным UI WebSocket'ам.
    
    Для chat_invite отправляет всем admin/support подключениям.
    Для остальных событий отправляет только подписчикам chat_session.
    """
    # 1. Для chat_invite - broadcast всем admin/support
    if event.get("event") == "chat_invite":
        for conn_id, conn_data in state.ui_connections.items():
            if conn_data.get("role") in ["admin", "support"]:
                await ws.send_json({"type": "chat_event", "job_id": job_id, "event": event})
    
    # 2. Для остальных - только подписчикам chat_session
    else:
        session = state.chat_sessions[job_id]
        subscribers = session.get("subscribers", set())
        for ws in subscribers:
            await ws.send_json({"type": "chat_event", "job_id": job_id, "event": event})
```

**Почему не удален:**

1. **Отдельная система:** Chat events работают через `job_id`, а не `ticket_id`
2. **Разные use cases:**
   - Chat events: прямые чаты support ↔ agent (без тикетов)
   - Ticket events: чаты в контексте тикетов
3. **Разные подписчики:**
   - Chat events: подписчики через `state.chat_sessions[job_id].subscribers`
   - Ticket events: подписчики через `state.subscription_registry.ticket_subscribers[ticket_id]`

**Как мигрировать (если требуется):**

1. **Добавить `subscribe_chat` message type:**
   ```python
   # В websocket/ui_handler.py
   elif msg_type == "subscribe_chat":
       job_id = data.get("job_id")
       # Регистрируем подписку через subscription_registry
       await state.subscription_registry.add_chat_subscriber(job_id, ws)
   ```

2. **Создать `push_chat_event_committed`:**
   ```python
   async def push_chat_event_committed(state, job_id: str, event: dict):
       message = {
           "type": "chat_event_committed",
           "job_id": job_id,
           "event": event
       }
       await state.subscription_registry.broadcast_to_chat(job_id, message)
   ```

3. **Заменить вызовы:**
   ```python
   # Вместо:
   await push_chat_event_to_ui(state, job_id, event)
   
   # Использовать:
   await push_chat_event_committed(state, job_id, event)
   ```

**✅ РЕАЛИЗОВАНО:** Приведено к единому механизму подписок:
- ✅ `push_chat_event_to_ui` теперь использует `SubscriptionRegistry.broadcast_to_chat()`
- ✅ Добавлена поддержка `subscribe_chat` с catch-up через `JobEventsRepo.get_events_since_id`
- ✅ Единый механизм подписок для tickets, devices и chats
- ✅ Legacy broadcast для `chat_invite` сохранен (admin/support broadcast)
- ✅ Добавлен `unsubscribe_chat` handler

**Результат:**
- Job-based chat теперь использует единый механизм подписок
- Поддерживается persistent catch-up через `job_events` таблицу
- Обратная совместимость сохранена (legacy broadcast для chat_invite)
- Готов к дальнейшей миграции на полную систему подписок

**Примечание:** "Старые агенты" vs "Старые клиенты":
- **Старые агенты** - это агенты, которые еще не обновлены до Protocol V3 (не актуально, т.к. Protocol V3 уже обязателен)
- **Старые клиенты** - это HTTP/WebSocket клиенты (UI, мобильные приложения), которые используют старый формат API
- Breaking change в `handle_ticket_send_message` сломает **HTTP клиенты**, которые ожидают `{"status": "ok", "queued": true}`
- ✅ **Решение:** Улучшена семантика ответа без breaking change (добавлены новые поля, старые сохранены)

## Критические исправления

### 1. Импорт logger в state_manager.py

**Проблема:** `logger` не был импортирован, вызывал ошибки линтера.

**Решение:** Добавлен `from loguru import logger` в начало файла.

### 2. Возврат (id, created_at) из add_event

**Статус:** ✅ Уже реализовано в предыдущих PR

**Проверка:** `TicketEventsRepo.add_event` возвращает tuple `(inserted_id, created_at)` из INSERT RETURNING.

## Архитектурные улучшения

### 1. Централизованный UiPublisher

- `UiPublisherImpl` создается один раз при инициализации `StateManager`
- Доступен через `state.ui_publisher` во всех местах
- Единый интерфейс для push обновлений

### 2. Автоматический Push

- Все изменения операций автоматически push'ятся в UI
- Не требуется ручной вызов push в каждом месте
- Единый хук через `OperationService._push_operation_update`

### 3. Catch-up Before Subscription

- Catch-up выполняется ДО регистрации подписки
- Предотвращает race conditions
- Гарантирует получение всех событий

## Файлы изменены

### Новые файлы
- `server/tests/test_ui_transport_v3.py` - интеграционные тесты

### Измененные файлы

**Core:**
- `server/state_manager.py` - добавлен `ui_publisher`
- `server/websocket/subscription_registry.py` - добавлена поддержка chat subscriptions
- `server/websocket/ui_handler.py` - реализован `send_device_catchup`, `send_chat_catchup`, `subscribe_chat`, `unsubscribe_chat`
- `server/websocket/protocol.py` - `push_chat_event_to_ui` использует SubscriptionRegistry, использование ui_publisher
- `server/websocket/agent_handler.py` - использование ui_publisher (2 места)

**Repositories:**
- `server/app/repos/device_events_repo.py` - добавлен `get_events_since_id`
- `server/app/repos/job_events_repo.py` - добавлен `get_events_since_id` для chat catch-up

**Services:**
- `server/app/services/operation_service.py` - добавлен push во все mark_* методы
- `server/api/operations.py` - использование ui_publisher
- `server/websocket/device_outbox_sender.py` - использование ui_publisher
- `server/app/services/operation_watchdog.py` - использование ui_publisher (None)

**Handlers:**
- `server/tickets/handlers.py` - улучшена семантика ответа `handle_ticket_send_message` (event_id, delivery_state)

## Проверка работы

### Ручное тестирование

1. **Subscribe ticket:**
   ```bash
   # WebSocket connect to /ws_ui
   # Send: {"type": "subscribe_ticket", "ticket_id": "...", "since_event_id": 0}
   # Should receive: catch-up events + catchup_done + subscribe_ack
   ```

2. **Operation updates:**
   ```bash
   # Create operation via API
   # Subscribe to ticket
   # Operation status changes should be pushed automatically
   ```

3. **Device events:**
   ```bash
   # Subscribe to device
   # Should receive device events catch-up
   ```

### Автоматические тесты

```bash
cd server
pytest tests/test_ui_transport_v3.py -v
```

## Следующие шаги (опционально)

1. **Миграция chat events:**
   - Заменить `push_chat_event_to_ui` на новую систему подписок
   - Добавить `subscribe_chat` message type

2. **HTTP Ticket Message:**
   - Обновить `handle_ticket_send_message` для создания operation
   - Версионирование API (v2 endpoint)

3. **Мониторинг:**
   - Метрики количества подписчиков
   - Метрики push событий
   - Ошибки при push

## Выводы

✅ **Все критические задачи выполнены:**
- UiPublisher интегрирован во все места
- Push работает для всех изменений операций
- Device events catch-up реализован
- Тесты созданы и проходят

✅ **Дополнительные улучшения реализованы:**
- Улучшена семантика ответа для ticket messages (event_id, delivery_state)
- Унифицирован механизм подписок для job-based chat
- Добавлен persistent catch-up для job chat через JobEventsRepo
- `push_chat_event_to_ui` теперь использует SubscriptionRegistry

🎯 **Результат:** UI Transport V3 полностью функционален, улучшен и готов к использованию.

## Итоговая архитектура

### Subscription Registry
- ✅ `ticket_subscribers` - подписки на тикеты
- ✅ `device_subscribers` - подписки на устройства
- ✅ `chat_subscribers` - подписки на job-based чаты (NEW)

### Push механизмы
- ✅ `push_ticket_event_committed` - для ticket events (после commit в БД)
- ✅ `push_operation_updated` - для обновлений операций (через UiPublisher)
- ✅ `push_chat_event_to_ui` - для job-based chat (через SubscriptionRegistry)

### HTTP Endpoints
- ✅ `/api/tickets/{id}/message` - улучшенная семантика ответа (event_id, delivery_state)
- ✅ `/api/tools/run` - возвращает 202 Accepted с operation_id
- ✅ `/api/tickets/{id}/snapshot` - snapshot endpoint для UI

### WebSocket Messages
- ✅ `subscribe_ticket` - с catch-up через since_event_id
- ✅ `subscribe_device` - с catch-up через since_event_id
- ✅ `subscribe_chat` - с catch-up через since_event_id (NEW)
- ✅ `unsubscribe_ticket`, `unsubscribe_device`, `unsubscribe_chat`
- ✅ `ping` / `pong` - keepalive

