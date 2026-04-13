# UI Bridge Module

Модуль для публикации UI-событий и HTTP API.

## Компоненты

### EventBus

Шина событий для публикации и подписки на UI-события.

**Использование для публикации событий (из core компонентов):**

```python
from ui_bridge import EventBus

# Получить event_bus из WSAgent
event_bus = agent.event_bus

# Публиковать событие
await event_bus.publish({
    "event_type": "job_started",
    "data": {
        "job_id": "123",
        "module": "screen",
        "status": "running"
    },
    "timestamp": "2025-01-01T12:00:00Z"
})
```

**Использование для подписки (из UI компонентов):**

```python
# Подписаться на события
queue = event_bus.subscribe()

# Читать события
while True:
    event = await queue.get()
    print(f"Получено событие: {event}")
```

### UiApiServer

HTTP API сервер для UI Bridge.

**Эндпоинты:**

- `GET /ui/events` - SSE или long-poll для получения событий
  - SSE: установите заголовок `Accept: text/event-stream`
  - Новый SSE-подписчик сразу получает последнее `connection_state`, чтобы GUI не зависал в `подключение...`, если handshake успел завершиться до подписки
  - Long-poll: ждет одно событие до 30 секунд, возвращает JSON

- `POST /ui/consent_decision` - обработка решений о согласии
  ```json
  {
    "job_id": "...",
    "consent_token": "...",
    "approved": true,
    "reason": ""
  }
  ```

- `POST /ui/chat_send` - отправка сообщения в чат тикета (ticket_id, text, from_role, attachment_refs, metadata). Требует on_chat_send в агенте.

- `GET /health` - health check

**Пример использования SSE:**

```bash
curl -N -H "Accept: text/event-stream" http://127.0.0.1:8765/ui/events
```

**Пример использования long-poll:**

```bash
curl http://127.0.0.1:8765/ui/events
```

**Пример отправки решения о согласии:**

```bash
curl -X POST http://127.0.0.1:8765/ui/consent_decision \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "123",
    "consent_token": "token123",
    "approved": true,
    "reason": "User approved"
  }'
```

## Интеграция

UI Bridge автоматически инициализируется при запуске агента через `ws_agent.py`.

- EventBus создается в `WSAgent.initialize()`
- UiApiServer запускается как background task в `WSAgent.run()`
- Сервер останавливается при завершении работы агента в `WSAgent.cleanup()`

## Конфигурация

По умолчанию сервер запускается на `127.0.0.1:8765`. Это можно изменить в `ws_agent.py` при создании `UiApiServer`.







