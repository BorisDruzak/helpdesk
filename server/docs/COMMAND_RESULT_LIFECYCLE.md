# Command Result Lifecycle Guarantees

## Назначение

Этот документ описывает инварианты и гарантии обработки `command_result` в системе операций сервера. Цель: обеспечить надежность и предсказуемость жизненного цикла операций.

## Инварианты

### Инвариант 1: Любой command_result завершает операцию

При получении `command_result` (success, error или consent_required) сервер **обязан**:

1. Перевести `operations` в terminal (succeeded, failed, waiting_consent) или terminal-подобное состояние
2. Завершить соответствующую запись в `device_outbox` в terminal состоянии
3. Разрешить `pending_command_futures[request_id]` (если есть), чтобы HTTP/WS callers не висели

**Гарантия**: Каждый command_result приводит к завершению операции. Операции не могут "зависнуть" при получении result.

### Инвариант 2: Outbox status — это доставка/исполнение, не execution result

Для server→agent `device_outbox` семантика статусов:

- **sent** — команда отправлена по WebSocket
- **delivered** — сервер получил финальный `command_result` (success/error/consent_required)
  - ⚠️ **Execution error ≠ delivery error**
  - Error result → `outbox: delivered`, `operations: failed`
- **failed** — команда не доставлена (SEND_ERROR / max retries) или не может быть обработана (non-retryable reject)
  - Также используется для timeout с `error_code="TIMEOUT"` (особый failure-класс)

**Ключевой принцип**: 
```
error result ≠ outbox failed
```
Ошибка выполнения команды на агенте — это не ошибка доставки, а успешная доставка команды, которая завершилась с ошибкой. Поэтому:
- `outbox = delivered` (команда доставлена и обработана)
- `operations = failed` (выполнение завершилось с ошибкой)

### Инвариант 3: Terminal состояния защищены от перезаписи

Terminal состояния операций (`succeeded`, `failed`, `timed_out`, `canceled`) **не могут** быть перезаписаны.

**Механизм защиты**:
- `OperationsRepo.update_status()` с `expected_statuses=None` (forced update) проверяет текущий статус
- Если текущий статус terminal → update блокируется и возвращается False
- Guards защищают от race conditions между command_result handler и watchdog

**Исключение**: Forced updates разрешены только для определенных error codes:
- `MALFORMED_RESULT` — битый payload от агента
- `SERVER_PROCESSING_ERROR` — внутренняя ошибка сервера
- `EXCEPTION_RECOVERY` — recovery после exception в обработчике

### Инвариант 4: Нормализация payload гарантирует структуру

Функция `normalize_command_result_payload()` гарантирует единообразную структуру:

```python
{
    "status": "success" | "error" | "consent_required",  # Всегда один из трех
    "error": {},      # Всегда dict
    "data": {},       # Всегда dict
    "meta": {},       # Всегда dict
    "is_malformed": False  # bool флаг битого payload
}
```

**Правила нормализации**:
- `None` payload → `error` + `is_malformed=True`
- Не-dict payload → `error` + `is_malformed=True`
- Любой неизвестный `status` → `error` + `MALFORMED_RESULT` + `is_malformed=True`

## Гарантии обработки

### 1. Гарантия завершения (Finally Block)

Каждый `command_result` проходит через обязательный finally блок, который гарантирует:

```python
finally:
    # 1. Outbox delivered (если еще не delivered/failed)
    # 2. Future resolved (если pending)
```

**Эффект**: Даже при exception в обработке, операция достигает terminal состояния и future разрешается.

### 2. Гарантия согласованности outbox-operations

**Success path**:
- `operations: succeeded` ✅
- `outbox: delivered` ✅
- `future: resolved(success)`

**Error path**:
- `operations: failed` ✅
- `outbox: delivered` ✅ (не failed!)
- `future: resolved(error)`

**Consent_required path**:
- `operations: waiting_consent` ✅
- `outbox: delivered` ✅
- `future: resolved(consent_required)`

**Timeout path** (watchdog):
- `operations: timed_out` ✅
- `outbox: failed` (error_code=TIMEOUT) ✅
- `future: resolved` (если еще pending)

### 3. Гарантия защиты от гонок

**Проблема**: Watchdog и command_result handler могут конкурировать за обновление одной операции.

**Решение**:
1. `OperationService` методы используют `expected_statuses` (optimistic locking)
2. Guards в `operations_repo` блокируют перезапись terminal состояний
3. Watchdog не может перезаписать terminal состояния, установленные command_result handler

**Пример race condition**:
```
t0: Watchdog видит операцию в status=sent, deadline expired
t1: Command_result приходит, устанавливает operations=succeeded
t2: Watchdog пытается установить operations=timed_out
→ Guard блокирует update, операция остается succeeded
```

## Особые случаи

### Timeout как особый failure-класс

Timeout операций обрабатывается watchdog'ом:
- `operations: timed_out`
- `outbox: failed` с `error_code="TIMEOUT"` и `should_retry=False`

Это **не** transport failure, а execution timeout failure. Документируется отдельно как особый класс.

### Malformed payload

При получении битого payload (None, не dict, неизвестный status):
- Нормализация возвращает `is_malformed=True`
- `status` устанавливается в `error`
- `error_code=MALFORMED_RESULT`
- Операция завершается как `failed`
- Разрешены forced updates для recovery

### Consent_required

`consent_required` — это отдельный status, не являющийся ошибкой:
- `operations: waiting_consent` (не terminal, ожидает действия пользователя)
- `outbox: delivered` (команда успешно доставлена)
- Future разрешается с payload для информирования caller

**HTTP endpoint** `/api/tools/run` возвращает:
- Status: 200 OK
- Body: `{status: "consent_required", consent_token: "...", ...}`

## Архитектурные принципы

### 1. Single Exit Path

Все ветки обработки `command_result` (success/error/consent_required) используют единый terminal path:

```python
if status == "success":
    # Обработка success
elif status == "error":
    # Обработка error
elif status == "consent_required":
    # Обработка consent_required
# else невозможен благодаря нормализации

# Единый terminal path для всех веток
```

### 2. Separation of Concerns

- **Outbox**: отражает доставку/транспорт (delivered/failed)
- **Operations**: отражает выполнение команды (succeeded/failed/waiting_consent)
- **Future**: уведомляет caller о результате

### 3. Idempotence

Обработка `command_result` идемпотентна:
- Повторная обработка того же result не изменяет terminal состояния
- Guards защищают от некорректных updates

## Контракты

### Future Contract для Consent_Required

HTTP endpoint `/api/tools/run` при `status=consent_required`:

**Рекомендуемый контракт**:
```json
{
  "status": 200,
  "body": {
    "status": "consent_required",
    "consent_token": "...",
    "message": "User consent required for this operation",
    "consent_details": {...}
  }
}
```

Альтернатива: 202 Accepted (если требуется семантика "принято, но не завершено").

## Примеры сценариев

### Сценарий 1: Нормальное выполнение

```
1. Сервер отправляет команду → outbox: sent
2. Агент отправляет command_ack → operations: accepted
3. Агент выполняет команду → operations: running
4. Агент отправляет command_result success → operations: succeeded, outbox: delivered
```

### Сценарий 2: Ошибка выполнения

```
1. Сервер отправляет команду → outbox: sent
2. Агент отправляет command_ack → operations: accepted
3. Агент выполняет команду, получает ошибку
4. Агент отправляет command_result error → operations: failed, outbox: delivered
```

### Сценарий 3: Timeout

```
1. Сервер отправляет команду → outbox: sent
2. Агент не отвечает
3. Watchdog обнаруживает expired deadline → operations: timed_out, outbox: failed (TIMEOUT)
```

### Сценарий 4: Race condition (timeout vs result)

```
1. Сервер отправляет команду → outbox: sent
2. Deadline истекает
3. T0: Watchdog видит expired deadline
4. T1: Command_result приходит → operations: succeeded, outbox: delivered
5. T2: Watchdog пытается mark_timed_out → BLOCKED by guard
   → операция остается succeeded
```

## Конфигурация

Настройки в `config.py`:

```python
OPERATION_WATCHDOG_INTERVAL = 30  # Интервал проверки watchdog (секунды)
DEFAULT_OPERATION_TIMEOUT = 300   # Таймаут операции по умолчанию (секунды)
```

## Мониторинг

Ключевые метрики для мониторинга:

- `operations_timed_out_total` — количество timeout операций
- `operations_guard_blocks_total` — количество блокировок guards
- `malformed_results_total` — количество битых payload
- `consent_required_total` — количество consent_required results

## Связанные документы

- [Operation State Machine](OPERATION_STATE_MACHINE.md)
- [Device Outbox Lifecycle](DEVICE_OUTBOX_LIFECYCLE.md)
- [Watchdog Architecture](WATCHDOG_ARCHITECTURE.md)

## История изменений

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | 2025-01-14 | Первая версия документа |
