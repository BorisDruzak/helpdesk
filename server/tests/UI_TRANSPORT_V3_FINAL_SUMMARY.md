# UI Transport V3 - Финальный Summary

## Дата: 2026-01-15

## Статус: ✅ ПОЛНОСТЬЮ РЕАЛИЗОВАНО + УЛУЧШЕНО

Все критические задачи выполнены, дополнительные улучшения реализованы согласно рекомендациям.

---

## 1. HTTP /api/tickets/{id}/message - Улучшена семантика ответа

### ✅ Реализовано

**Проблема:** Ответ `{"queued": true}` вводил в заблуждение - это не "доставлено", а "записано/поставлено в очередь".

**Решение:** Улучшена семантика ответа без breaking change:

```json
{
  "status": "ok",
  "ticket_id": "...",
  "event_id": 123456,              // NEW: ID записи в ticket_events (гарантия сохранения в БД)
  "queued": true,                  // Сохранено для обратной совместимости
  "delivery_state": "queued",      // NEW: Явный статус доставки
  "operation_id": null,            // NEW: Явно указываем, что это не operation
  "dedup": false,
  "message": "Message saved to database. Delivery to agent is asynchronous."
}
```

**Возможные значения `delivery_state`:**
- `"queued"` - сообщение в очереди на доставку агенту
- `"delivered"` - успешно доставлено агенту
- `"delivery_failed"` - ошибка доставки
- `"delivery_timeout"` - таймаут доставки
- `"no_session"` - нет активной сессии
- `"no_job"` - нет активного job
- `"agent_offline"` - агент не подключен

**Преимущества:**
- ✅ Явная семантика: `event_id` гарантирует сохранение в БД
- ✅ `delivery_state` четко показывает статус доставки
- ✅ Обратная совместимость: `queued` поле сохранено
- ✅ Документированная асинхронность доставки
- ✅ Нет breaking change для существующих клиентов

**Архитектурное решение:**
- Chat messages остаются как **events** (не operations)
- Сохранение в БД через `TicketEventsRepo.add_event()`
- Push в UI через `push_ticket_event_committed` (после commit)
- Создание operation для каждого message не требуется (избыточно)

---

## 2. Job-based Chat - Унифицирован механизм подписок

### ✅ Реализовано

**Проблема:** `push_chat_event_to_ui` использовал отдельный механизм подписок через `state.chat_sessions`, не имел persistent catch-up.

**Решение:** Приведено к единому механизму через `SubscriptionRegistry`:

#### 2.1. Расширен SubscriptionRegistry

```python
class SubscriptionRegistry:
    def __init__(self):
        self.ticket_subscribers: Dict[str, Set] = {}  # ticket_id -> Set[ws]
        self.device_subscribers: Dict[str, Set] = {}  # device_id -> Set[ws]
        self.chat_subscribers: Dict[str, Set] = {}    # job_id -> Set[ws]  # NEW
    
    async def add_chat_subscriber(self, job_id: str, ws: web.WebSocketResponse)
    async def remove_chat_subscriber(self, job_id: str, ws: web.WebSocketResponse)
    async def broadcast_to_chat(self, job_id: str, message: dict)
```

#### 2.2. Обновлен push_chat_event_to_ui

```python
async def push_chat_event_to_ui(state, job_id: str, event: dict):
    """
    Thin-wrapper: использует SubscriptionRegistry для подписчиков.
    Legacy broadcast для chat_invite сохранен (admin/support).
    """
    message = {
        "type": "chat_event_committed",  # Единый формат
        "job_id": job_id,
        "event": event,
        "ts": time.time()
    }
    
    # 1. Legacy broadcast для chat_invite (admin/support)
    if event.get("event") == "chat_invite":
        # Broadcast всем admin/support подключениям
        ...
    
    # 2. Broadcast подписчикам через SubscriptionRegistry
    if state.subscription_registry:
        await state.subscription_registry.broadcast_to_chat(job_id, message)
```

#### 2.3. Добавлен persistent catch-up

```python
# JobEventsRepo.get_events_since_id
async def get_events_since_id(
    self,
    job_id: str,
    since_event_id: int,
    limit: int = 500
) -> List[JobEvent]:
    """Get job events with id > since_event_id for catch-up."""
    ...

# send_chat_catchup
async def send_chat_catchup(ws, job_id, since_event_id):
    """Send catch-up events for chat subscription."""
    events = await repo.get_events_since_id(job_id, since_event_id)
    for event in events:
        await ws.send_json({
            "type": "chat_event_committed",
            "job_id": job_id,
            "event_id": event.id,
            "event": event.payload
        })
```

#### 2.4. Добавлен subscribe_chat

```python
# В websocket/ui_handler.py
elif msg_type == "subscribe_chat":
    job_id = data.get("job_id")
    since_event_id = data.get("since_event_id", 0)
    
    # 1. Catch-up FIRST
    await send_chat_catchup(ws, job_id, since_event_id)
    
    # 2. THEN register subscription
    await state.subscription_registry.add_chat_subscriber(job_id, ws)
    
    # 3. Send ack
    await ws.send_json({
        "type": "subscribe_ack",
        "job_id": job_id,
        "since_event_id": since_event_id
    })
```

**Преимущества:**
- ✅ Единый механизм подписок для tickets, devices и chats
- ✅ Persistent catch-up через `job_events` таблицу
- ✅ Автоматическая очистка мертвых подключений
- ✅ Обратная совместимость: legacy broadcast для chat_invite сохранен
- ✅ Готов к дальнейшей миграции на полную систему подписок

---

## Что такое Job-based Chat?

**Job-based чаты** - это отдельная система от ticket-based чатов:

| Аспект | Job-based Chat | Ticket-based Chat |
|--------|----------------|-------------------|
| **Идентификатор** | `job_id` | `ticket_id` |
| **Use case** | Прямое общение support ↔ agent (без тикета) | Чат в контексте тикета |
| **Хранение** | `job_events` таблица | `ticket_events` таблица |
| **Push** | `push_chat_event_to_ui` → `SubscriptionRegistry.broadcast_to_chat` | `push_ticket_event_committed` → `SubscriptionRegistry.broadcast_to_ticket` |
| **Endpoints** | `/api/chat_start`, `/api/chat_raise`, `/api/chat_send` | `/api/tickets/{id}/message` |

**Примеры использования:**
- Support инициирует чат с агентом: `POST /api/chat_start`
- Агент инициирует чат: `POST /api/chat_raise`
- Отправка сообщения: `POST /api/chat_send`

**События:**
- `chat_invite` - приглашение в чат (broadcast всем admin/support)
- `chat_message` - сообщение в чате
- `chat_ended` - завершение чата

---

## Итоговая архитектура

### Subscription Registry (единый механизм)

```python
SubscriptionRegistry:
  - ticket_subscribers: Dict[ticket_id, Set[ws]]  # Ticket events
  - device_subscribers: Dict[device_id, Set[ws]]  # Device events
  - chat_subscribers: Dict[job_id, Set[ws]]       # Job-based chat events
```

### Push механизмы

1. **Ticket Events:**
   - `push_ticket_event_committed(state, ticket_id, event_id, ...)`
   - Использует `SubscriptionRegistry.broadcast_to_ticket()`
   - Вызывается после commit в БД

2. **Operations:**
   - `OperationService._push_operation_update(operation_id)`
   - Использует `UiPublisher.push_operation_updated()`
   - Автоматически вызывается во всех `mark_*` методах

3. **Job-based Chat:**
   - `push_chat_event_to_ui(state, job_id, event)`
   - Использует `SubscriptionRegistry.broadcast_to_chat()`
   - Legacy broadcast для `chat_invite` сохранен

### HTTP Endpoints

1. **POST /api/tickets/{id}/message:**
   - ✅ Улучшенная семантика ответа (event_id, delivery_state)
   - ✅ Сохранение в БД через `TicketEventsRepo.add_event()`
   - ✅ Push в UI через `push_ticket_event_committed`
   - ✅ Обратная совместимость сохранена

2. **POST /api/tools/run:**
   - ✅ Возвращает `202 Accepted` с `operation_id`
   - ✅ Опциональный `?wait=1` для dev mode

3. **GET /api/tickets/{id}/snapshot:**
   - ✅ Snapshot endpoint для UI (отдельный от `/api/tickets/{id}`)

### WebSocket Messages

1. **Subscribe:**
   - `subscribe_ticket(ticket_id, since_event_id)` - с catch-up
   - `subscribe_device(device_id, since_event_id)` - с catch-up
   - `subscribe_chat(job_id, since_event_id)` - с catch-up (NEW)

2. **Unsubscribe:**
   - `unsubscribe_ticket(ticket_id)`
   - `unsubscribe_device(device_id)`
   - `unsubscribe_chat(job_id)` (NEW)

3. **Keepalive:**
   - `ping` / `pong`

---

## Файлы изменены

### Новые файлы
- `server/tests/test_ui_transport_v3.py` - интеграционные тесты
- `server/tests/UI_TRANSPORT_V3_FINAL_SUMMARY.md` - этот файл

### Измененные файлы

**Core:**
- `server/state_manager.py` - добавлен `ui_publisher`
- `server/websocket/subscription_registry.py` - добавлена поддержка chat subscriptions
- `server/websocket/ui_handler.py` - добавлен `send_chat_catchup`, `subscribe_chat`, `unsubscribe_chat`
- `server/websocket/protocol.py` - `push_chat_event_to_ui` использует SubscriptionRegistry
- `server/websocket/agent_handler.py` - использование `ui_publisher` (2 места)

**Repositories:**
- `server/app/repos/device_events_repo.py` - добавлен `get_events_since_id`
- `server/app/repos/job_events_repo.py` - добавлен `get_events_since_id`

**Services:**
- `server/app/services/operation_service.py` - добавлен push во все `mark_*` методы
- `server/api/operations.py` - использование `ui_publisher`
- `server/websocket/device_outbox_sender.py` - использование `ui_publisher`
- `server/app/services/operation_watchdog.py` - использование `ui_publisher` (None)

**Handlers:**
- `server/tickets/handlers.py` - улучшена семантика ответа `handle_ticket_send_message`

---

## Проверка работы

### Тесты

```bash
cd server
pytest tests/test_ui_transport_v3.py -v
```

### Ручное тестирование

1. **Ticket Message с улучшенной семантикой:**
   ```bash
   POST /api/tickets/{id}/message
   # Ответ должен содержать: event_id, delivery_state, operation_id: null
   ```

2. **Subscribe Chat:**
   ```bash
   # WebSocket: /ws_ui
   {"type": "subscribe_chat", "job_id": "...", "since_event_id": 0}
   # Должен получить: catch-up events + catchup_done + subscribe_ack
   ```

3. **Push Chat Event:**
   ```bash
   # После отправки chat_message через /api/chat_send
   # Подписчики должны получить chat_event_committed
   ```

---

## Выводы

✅ **Все задачи выполнены:**
- Критические задачи из плана реализованы
- Дополнительные улучшения реализованы согласно рекомендациям
- Обратная совместимость сохранена
- Единый механизм подписок для всех типов событий

🎯 **Результат:**
- UI Transport V3 полностью функционален
- Семантика ответов улучшена без breaking change
- Job-based chat приведен к единому механизму подписок
- Persistent catch-up работает для всех типов событий

🚀 **Готово к production использованию.**


