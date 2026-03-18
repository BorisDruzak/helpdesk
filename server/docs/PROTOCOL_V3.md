# Protocol V3 (ws_ticket_v3) — серверная документация

Краткое описание поведения сервера в рамках Protocol V3 и ссылка на полную спецификацию.

**Дата обновления:** 2026-03-18

---

## Где полная спецификация

**Полная документация протокола V3** (форматы сообщений, envelope, handshake, outbox_item, command, command_result, ACK/NACK, lifecycle) находится в документации агента:

- **Путь:** `pc_agent/docs/PROTOCOL_V3.md` (от корня репозитория: `../../pc_agent/docs/PROTOCOL_V3.md`).

Ниже — только **важные уточнения и требования со стороны сервера**.

---

## Требования сервера к протоколу

### 1. Версия протокола

- Сервер **требует** `protocol_version === "ws_ticket_v3"` при handshake агента.
- При любой другой версии или отсутствии поля соединение закрывается с кодом **4003** и сообщением «Protocol V3 (ws_ticket_v3) required».
- Агенты с устаревшими протоколами не принимаются (Phase E).

### 2. Обязательные capabilities при handshake

В `meta.capabilities` при handshake должны присутствовать:

- `protocol_v3`
- `envelope_v3`
- `outbox_ack_v3`

При отсутствии любой из них соединение закрывается с кодом **4003** и сообщением о недостающих capabilities.

### 3. Аутентификация при handshake

- В handshake обязательно поле **token** (сырой токен агента).
- Токен проверяется через БД (`AuthService.verify_agent_token`). При отсутствии или невалидном токене соединение закрывается с кодом **4003** («Token required» или «Invalid token»).
- **device_id** для всего последующего обмена берётся **только из записи токена в БД**, не из payload. Если в payload указан другой device_id — используется device_id из токена и пишется предупреждение в лог.

### 4. Device binding

- Каждый тикет привязан к одному `device_id`. События от другого устройства для этого тикета отклоняются с **outbox_nack** и кодом `DEVICE_MISMATCH` (non-retryable).
- Валидация выполняется в `EventValidator` (websocket/validator.py).

### 5. Trace correlation

- В ответах **outbox_ack** и **outbox_nack** поле **trace_id** должно совпадать с `trace_id` из входящего envelope (корреляция запрос/ответ).

### 6. Server-side device outbox

- Команды к агенту доставляются через таблицу **device_outbox** (pending → sent → delivered/failed).
- `request_id` в команде используется как **command_id** (единый идентификатор команды).
- DeviceOutboxSender периодически опрашивает pending команды и отправляет их подключённым агентам; при получении `command_result` команда помечается как delivered (или failed при ошибке).

### 7. Deduplication

- **Ticket events:** UNIQUE по `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`. Повторная вставка игнорируется, но сервер отправляет ACK.
- **Device events:** UNIQUE по `(device_id, device_seq)`. Аналогично — идемпотентность и ACK.

### 8. Коды ошибок outbox_nack

- `UNKNOWN_TICKET` — тикет не найден (non-retryable).
- `DEVICE_MISMATCH` — тикет привязан к другому устройству (non-retryable).
- `VALIDATION_ERROR` — ошибка валидации (non-retryable).

---

## SERVER_CAPABILITIES

Список capabilities, которые сервер объявляет агентам в **handshake_ack** (config.py, полный список):

```python
SERVER_CAPABILITIES = [
    "protocol_v3", "envelope_v3", "outbox_ack_v3", "outbox_nack",
    "trace_correlation", "ticket_context", "job_context",
    "device_outbox", "event_replay", "batch_ack", "device_binding_validation",
    "device_registry", "toolset_snapshots", "config_management"
]
```

---

## Коды ошибок outbox_nack (уточнение)

В полной спецификации (агент) перечислены коды UNAUTHORIZED, RATE_LIMIT и др. **На практике сервер при handshake** при невалидном протоколе/токене **закрывает соединение с кодом 4003**, не отправляя outbox_nack. В **outbox_nack** реально используются:

- `UNKNOWN_TICKET`, `DEVICE_MISMATCH`, `VALIDATION_ERROR` (non-retryable)
- `SERVER_ERROR` (retryable) — при исключениях в валидации

Коды `UNAUTHORIZED`, `RATE_LIMIT` в коде сервера в outbox_nack **не возвращаются**; при необходимости их можно добавить в будущем.

---

## Сильные и слабые стороны (сервер)

**Сильные:** строгая проверка protocol_version и capabilities; device_id только из токена (БД); device binding для тикетов; дедупликация по (device_id, ticket_id, agent_seq) и (device_id, device_seq); tool_call_started до отправки run_tool; нормализация command_result и защита terminal состояний (COMMAND_RESULT_LIFECYCLE); единый run_tool backend-фасад (`ToolExecutionService`) для API/админки/smoke.

**Слабые/ограничения:** монолитный agent_handler; один цикл DeviceOutboxSender; синхронное ожидание в send_ws_command по таймауту. `send_ws_command` теперь транспортный слой (enqueue + wait) без run_tool policy/consent-веток. Подробнее: [BOTTLENECKS_AND_RISKS.md](../../docs/BOTTLENECKS_AND_RISKS.md).

---

## WebSocket endpoints

- **/ws** — агенты (Protocol V3). Handshake с `protocol_version`, capabilities и token обязательны.
- **/ws_ui** — UI клиенты. Первое сообщение — `ui_hello` с токеном; см. [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md).

---

## Связанные документы

- [README.md](README.md) — обзор сервера и API.
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — безопасность и аутентификация (токены, handshake, middleware).
- [pc_agent/docs/PROTOCOL_V3.md](../../pc_agent/docs/PROTOCOL_V3.md) — полная спецификация Protocol V3.
- [BOTTLENECKS_AND_RISKS.md](../../docs/BOTTLENECKS_AND_RISKS.md) — узкие места и риски проекта.
