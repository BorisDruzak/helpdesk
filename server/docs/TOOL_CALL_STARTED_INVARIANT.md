# Tool Call Started Event Invariant

## Инвариант

**tool_call_started всегда создаётся сервером до отправки run_tool команды.**

## Корреляция

- **Основной способ**: `operation_id` (UUID, единый для всей операции end-to-end)
- **Legacy**: `call_id` (опциональное поле, не используется для поиска/обновления)

## Идемпотентность

Идемпотентность гарантируется UNIQUE индексом в БД:

```sql
CREATE UNIQUE INDEX uq_ticket_events_ticket_operation_type 
ON ticket_events (ticket_id, operation_id, event_type)
WHERE operation_id IS NOT NULL
```

Это означает, что для каждой операции может быть только одно `tool_call_started` событие. Повторные попытки создания (например, при ретраях) безопасно игнорируются.

## Реализация

### Создание события

Событие создаётся в `server/tools/service.py` в методе `ToolService.run_tool`:

`ToolExecutionService.resume_approved_operation()` also resumes approved
`waiting_consent` operations through this same `run_tool` facade. In that
deferred mode `run_tool` creates the same idempotent `tool_call_started` event
before enqueuing `run_tool` into `device_outbox` without requiring a live
websocket connection.

1. **До отправки команды**: Событие создаётся ПЕРЕД вызовом `send_ws_command`
2. **С operation_id сразу**: Событие создаётся с `operation_id` сразу (не обновляется потом)
3. **Server-originated**: `agent_seq = None` (событие создаётся на сервере)
4. **Trace correlation**: Используется тот же `trace_id`, что и для команды

### Обработка дубликатов

`TicketEventsRepo.add_event` обрабатывает дубликаты:

1. **Предварительная проверка**: Проверка существования события по `(ticket_id, operation_id, event_type)` перед INSERT
2. **IntegrityError handling**: Если предварительная проверка пропустила (race condition), обрабатывается `IntegrityError` от UNIQUE индекса
3. **Безопасный возврат**: При дубликате возвращается `None` (не исключение)

### Упрощение protocol.py

Код в `server/websocket/protocol.py`, который обновлял `tool_call_started` по `call_id`, был удалён:

- **Причина**: Событие теперь создаётся с `operation_id` сразу, не нужно обновлять
- **Legacy**: `call_id` остаётся в payload для обратной совместимости, но не используется для корреляции

## Тесты

Интеграционные тесты в `server/tests/test_tool_started_event.py`:

1. **test_tool_call_started_created_before_command**: Проверяет, что событие создаётся ДО получения ответа от агента
2. **test_tool_call_started_idempotency**: Проверяет идемпотентность (повторная вставка не создаёт дубль)
3. **test_tool_call_started_with_different_operation_ids**: Проверяет, что разные `operation_id` создают разные события

## Миграция

Миграция `20260115_1000_009_add_tool_started_unique_index.py` создаёт UNIQUE индекс для идемпотентности.

## Важные замечания

1. **Не использовать call_id для поиска**: Корреляция только по `operation_id`
2. **Событие создаётся на сервере**: Агент может отправлять своё `tool_call_started`, но оно будет игнорироваться как дубликат (если есть server-originated)
3. **Идемпотентность критична**: При ретраях/реконнектах повторное создание события безопасно

