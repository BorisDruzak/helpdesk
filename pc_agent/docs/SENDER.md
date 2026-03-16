# WSOutboxFlusher - Документация

## Обзор

`WSOutboxFlusher` — это компонент для надежной доставки событий через WebSocket (Protocol V3). Использует outbox pattern для гарантированной доставки с подтверждением (ACK/NACK).

**Файл:** `pc_agent/core/sender.py`

## Основные возможности

- ✅ **Outbox pattern** — надежная доставка через outbox
- ✅ **ACK/NACK обработка** — подтверждение доставки или отклонение
- ✅ **Exponential backoff** — автоматические повторы с задержкой
- ✅ **Lease механизм** — предотвращение зависания событий
- ✅ **Batch отправка** — оптимизация сетевого трафика
- ✅ **Inflight tracking** — отслеживание отправленных событий

## Инициализация

```python
from core.sender import WSOutboxFlusher
from core.database import DatabaseManager

db_manager = DatabaseManager("data/storage.db")
await db_manager.initialize()

flusher = WSOutboxFlusher(
    db_manager=db_manager,
    device_id="device-uuid",
    logger_instance=logger,
    max_inflight=50,
    ack_timeout_sec=30.0,
    resend_limit=5
)
```

**Параметры:**
- `db_manager` — менеджер базы данных
- `device_id` — идентификатор устройства
- `logger_instance` (опционально) — экземпляр логгера
- `max_inflight` — максимальное количество одновременно отправленных событий (default: 50)
- `ack_timeout_sec` — таймаут ожидания ACK в секундах (default: 30.0)
- `resend_limit` — максимальное количество попыток (default: 5)

## Основной метод: run

Запуск фонового loop для отправки событий.

```python
async def send_func(msg_type, request_id, payload, ticket_id, job_id):
    """Функция отправки через WebSocket."""
    envelope = {
        "type": msg_type,
        "request_id": request_id,
        "payload": payload,
        ...
    }
    await ws.send_json(envelope)

# Запуск flusher
await flusher.run(send_func)
```

**Поведение:**
- Периодически проверяет pending события в outbox
- Отправляет события через `send_func`
- Отслеживает inflight события
- Обрабатывает таймауты и повторы

## Формирование envelope

### Ticket Event

```python
envelope_payload = {
    "outbox_id": 123,
    "item_type": "job_event",
    "agent_seq": 42,
    "event": {
        "event": "chat_message",
        "from": "user",
        "text": "Hello!"
    }
}
```

### Device Event

```python
envelope_payload = {
    "outbox_id": 124,
    "item_type": "job_event",
    "device_seq": 5,
    "event": {
        "event": "tools_changed",
        "toolset_hash": "a1b2c3d4e5f6"
    }
}
```

**Критично:** Тип события определяется **ТОЛЬКО** через наличие `device_seq` или `agent_seq`, **НЕ** через `ticket_id`.

## ACK/NACK обработка

### handle_ack

Обработка `outbox_ack` от сервера.

```python
await flusher.handle_ack(outbox_ids=[123, 124, 125])
```

**Поведение:**
- Удаляет события из outbox (через `delete_outbox_acked`)
- Удаляет из inflight tracking
- Обновляет статистику

**Критично:** События **удаляются** из outbox, не помечаются как `sent` (Protocol V3).

### handle_nack

Обработка `outbox_nack` от сервера.

```python
await flusher.handle_nack(
    outbox_ids=[126],
    retryable=False,
    error_code="DEVICE_MISMATCH",
    error_message="Ticket bound to another device"
)
```

**Поведение:**
- Если `retryable=true`, событие будет отправлено повторно
- Если `retryable=false`, событие помечается как `failed`
- Обновляет статистику

## Exponential Backoff

При получении NACK с `retryable=true` используется exponential backoff:

```python
def calculate_backoff(attempts: int) -> float:
    """Exponential backoff: 1, 2, 4, 8, 16, ... секунд."""
    base_delay = 1.0
    max_delay = 60.0
    
    delay = base_delay * (2 ** (attempts - 1))
    return min(delay, max_delay)
```

**Задержки:**
- 1-я попытка: 1 секунда
- 2-я попытка: 2 секунды
- 3-я попытка: 4 секунды
- 4-я попытка: 8 секунд
- 5-я попытка: 16 секунд
- Максимум: 60 секунд

## Inflight Tracking

Flusher отслеживает отправленные события через `inflight_deadlines`:

```python
self.inflight_deadlines: Dict[int, float] = {}  # outbox_id -> deadline_ts
```

**Поведение:**
- При отправке события добавляется в `inflight_deadlines` с deadline
- При получении ACK удаляется из tracking
- При таймауте событие снова становится доступным для отправки

## Lease механизм

События резервируются с lease временем:

```python
lease_until = now() + lease_sec  # например, now() + 30
```

**Поведение:**
- При `claim_outbox_batch` событие помечается как `inflight` с `lease_until`
- Если lease истекает, событие снова становится `pending` для повторной отправки
- Предотвращает зависание событий в статусе `inflight`

## Статистика

Flusher ведет статистику отправки:

```python
flusher.stats = {
    'sent': 100,           # Отправлено событий
    'acked': 95,           # Получено ACK
    'failed': 2,           # Помечено как failed
    'resends': 10,         # Повторные отправки
    'nack_retryable': 3,   # NACK с retryable=true
    'nack_non_retryable': 2  # NACK с retryable=false
}
```

## Жизненный цикл события

1. **Enqueue** — событие записывается в outbox (`pending`)
2. **Claim** — событие резервируется для отправки (`inflight` с lease)
3. **Send** — событие отправляется через WebSocket
4. **Track** — событие добавляется в inflight tracking
5. **ACK** — при получении `outbox_ack` событие удаляется из outbox
6. **NACK/Timeout** — при `outbox_nack` или истечении lease событие обрабатывается согласно политике

## Примеры использования

### Базовый пример

```python
from core.sender import WSOutboxFlusher

flusher = WSOutboxFlusher(
    db_manager=db_manager,
    device_id="device-uuid"
)

async def send_func(msg_type, request_id, payload, ticket_id, job_id):
    envelope = {
        "type": msg_type,
        "request_id": request_id,
        "payload": payload,
        ...
    }
    await ws.send_json(envelope)

# Запуск flusher (блокирующий)
await flusher.run(send_func)
```

### Интеграция с WSAgent

```python
class WSAgent:
    def __init__(self):
        self.flusher = WSOutboxFlusher(
            db_manager=self.db_manager,
            device_id=self.device_id
        )
    
    async def run(self):
        # Запуск flusher в фоне
        asyncio.create_task(self.flusher.run(self._send_ws_message))
        
        # Обработка сообщений
        async for msg in ws:
            if msg.type == "outbox_ack":
                await self.flusher.handle_ack(msg.payload["outbox_ids"])
            elif msg.type == "outbox_nack":
                await self.flusher.handle_nack(...)
```

### Обработка ACK/NACK

```python
# В обработчике сообщений
if msg_type == "outbox_ack":
    await flusher.handle_ack(payload["outbox_ids"])
    
elif msg_type == "outbox_nack":
    await flusher.handle_nack(
        outbox_ids=payload["outbox_ids"],
        retryable=payload["retryable"],
        error_code=payload["error"]["code"],
        error_message=payload["error"]["message"]
    )
```

## Ссылки

- [Protocol V3 документация](PROTOCOL_V3.md) — протокол общения с сервером
- [DatabaseManager документация](DATABASE.md) — работа с базой данных
- [AgentOrchestrator документация](ORCHESTRATOR.md) — обработка команд


