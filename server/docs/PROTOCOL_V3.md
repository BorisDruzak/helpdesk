# Protocol V3 (ws_ticket_v3) — серверная документация

Краткое описание поведения сервера в рамках Protocol V3 и ссылка на полную спецификацию.

**Дата обновления:** 2026-04-21

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
- **device_id** для всего последующего обмена берётся **только из записи токена в БД**, не из payload.
- Identity v1: `device_id` на сервере трактуется как канонический `machine_id`. Если агент прислал `payload.machine_id`, он должен совпадать с top-level `device_id`; `payload.install_id` хранится только как secondary metadata.
- Исключение: controlled reprovision. Если токен был выдан на новый placeholder-`device_id`, а агент пришёл с payload `device_id`, который уже известен серверу как реальное устройство, сервер сначала перепривязывает сам токен к существующему устройству и только потом завершает handshake.
- Если payload `device_id` не подходит под controlled reprovision, используется device_id из токена и пишется предупреждение в лог.

### 3.1 Update-report поля в handshake

После self-update launcher/агента сервер дополнительно принимает в handshake launcher-driven report о последней попытке обновления:

- success-report:
  - `applied_update_version`
  - `last_update_operation_id`
- failure-report:
  - `failed_update_version`
  - `failed_update_operation_id`
  - `failed_update_reason`
  - `failed_update_at`
  - `failed_update_message`

Эти поля используются только как post-update confirmation. Для `agent_update` операция считается завершённой именно после такого handshake-report, а не в момент `command_result` со стадией `scheduled`.

### 3.2 Runtime session ownership for one `device_id`

- Каждый успешный `/ws` handshake получает server-side runtime `connection_id`.
- Для одного `device_id` source of truth для live session — последний успешный handshake; предыдущий websocket помечается как superseded и закрывается сервером кодом **4002** (`Superseded by newer connection`).
- Offline/unregister path compare-safe: disconnect старого websocket не должен переводить в offline и не должен снимать более новое runtime-подключение того же `device_id`.

### 4. Device binding

- Каждый тикет привязан к одному `device_id`. События от другого устройства для этого тикета отклоняются с **outbox_nack** и кодом `DEVICE_MISMATCH` (non-retryable).
- Валидация выполняется в `EventValidator` (websocket/validator.py).

### 5. Trace correlation

- В ответах **outbox_ack** и **outbox_nack** поле **trace_id** должно совпадать с `trace_id` из входящего envelope (корреляция запрос/ответ).
- Если входящий `outbox_item` содержит `outbox_id`, но не содержит `trace_id`, сервер возвращает validation NACK с fallback server trace id; такой envelope не должен зависать без ACK/NACK.
- Runtime dedupe for `outbox_id` is terminal-only: retryable NACKs are not inserted into the duplicate cache, so the same `outbox_id` can be retried after transient persistence errors.

### 6. Server-side device outbox

- Команды к агенту доставляются через таблицу **device_outbox** (pending → sent → delivered/failed).
- `request_id` в команде используется как **command_id** (единый идентификатор команды).
- DeviceOutboxSender периодически опрашивает pending команды и отправляет их подключённым агентам; при получении `command_result` команда помечается как delivered (или failed при ошибке).
- Drain order is no longer pure FIFO: `cancel_operation` идёт первым, затем agent update / control-health команды, затем обычный FIFO по `created_at`.
- Для sync transport-path `send_ws_command(..., wait_for_result=True)` waiter теперь хранится в state-level runtime registry по `command_id`, а не в metadata текущего websocket, и регистрируется до wake-up dispatch, поэтому reconnect и быстрый `command_result` не должны терять ожидание.
- `send_ws_command` и `ToolService.run_tool` копируют caller params перед чтением internal `_operation_id`; вызывающий код может безопасно переиспользовать исходный dict для retry/log/audit.
- Если агент и сервер оба объявили capability `outbox_batch_v1`, агент может присылать несколько `outbox_item` в одном WS frame как `outbox_items_batch`; сервер при этом всё равно ACK/NACK-ит каждую запись отдельно.
- Remote Assist consent requests reuse the same device outbox path with command `remote_assist.request`. The command is ticket/device-bound and only tells Maria Agent to show consent UI; the actual WebRTC signaling uses the separate short-lived-token endpoint `/ws/remote-assist/{session_id}`. For `mode=elevated_admin`, the protocol command still does not grant hidden access: Maria Agent must show consent and then use its local Windows UAC helper path before elevated input can work.

### 7. Deduplication

- **Ticket events:** UNIQUE по `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`. Повторная вставка игнорируется, но сервер отправляет ACK.
- **Device events:** UNIQUE по `(device_id, device_seq)`. Аналогично — идемпотентность и ACK.

### 8. Коды ошибок outbox_nack

- `UNKNOWN_TICKET` — тикет не найден (non-retryable).
- `DEVICE_MISMATCH` — тикет привязан к другому устройству (non-retryable).
- `VALIDATION_ERROR` — ошибка валидации (non-retryable).
- `SERVER_ERROR` — внутренняя ошибка валидации/обработки (retryable).

---

## SERVER_CAPABILITIES

Список capabilities, которые сервер объявляет агентам в **handshake_ack** (config.py, полный список):

```python
SERVER_CAPABILITIES = [
    "protocol_v3", "envelope_v3", "outbox_ack_v3", "outbox_nack",
    "trace_correlation", "ticket_context", "job_context",
    "device_outbox", "event_replay", "batch_ack", "outbox_batch_v1", "device_binding_validation",
    "device_registry", "toolset_snapshots", "config_management"
]
```

---

## Коды ошибок outbox_nack (уточнение)

В полной спецификации (агент) перечислены коды UNAUTHORIZED, RATE_LIMITED и др.  
Разделение по фазам:

- **Handshake/auth до установленной сессии**: сервер закрывает соединение кодом **4003** (без `outbox_nack`).
- **Post-handshake ingest/runtime**: сервер использует типизированный `outbox_nack`.

После успешного handshake в `outbox_nack` используются:

- `UNKNOWN_TICKET`, `DEVICE_MISMATCH`, `VALIDATION_ERROR` (non-retryable)
- `UNAUTHORIZED` (non-retryable) — message-level reject в валидной сессии
- `RATE_LIMITED` (retryable) — превышение лимита ingest
- `SERVER_ERROR` (retryable) — при исключениях в обработке/валидации

Wire-contract Protocol V3 при этом не меняется: формат envelope/ACK/NACK остаётся прежним.

### 9. Пути запуска `run_tool` (инвариантная карта)

В текущей реализации есть два легитимных пути, которые сходятся в `device_outbox`:

1. **Прямой запуск из API/UI**: `ToolExecutionService.run_tool` создаёт `tool_call_started` (идемпотентно по `(ticket_id, operation_id, event_type)`), затем вызывает `send_ws_command`.
2. **Через consent approve**: `OperationService.approve_consent()` enqueue команды `run_tool` после одобрения уже созданной операции.

Оба пути должны сохранять общий инвариант: `operation_id` является первичной корреляцией для lifecycle и command_result.

Практическое замечание по нагрузке: transport-функция `send_ws_command` поддерживает `wait_for_result=False` для async API-сценариев (enqueue без удержания корутины до `command_result`).

---

## Сильные и слабые стороны (сервер)

**Сильные:** строгая проверка protocol_version и capabilities; device_id только из токена (БД); device binding для тикетов; дедупликация по (device_id, ticket_id, agent_seq) и (device_id, device_seq); tool_call_started до отправки run_tool; нормализация command_result и защита terminal состояний (COMMAND_RESULT_LIFECYCLE); единый run_tool backend-фасад (`ToolExecutionService`) для API/админки/smoke.

В identity v1 это даёт важный prod-инвариант: удаление локального `identity.json` у агента не должно создавать новый логический device record, если OS-level machine identity не изменилась.

**Слабые/ограничения:** state остается single-process runtime-реестром; `send_ws_command` по-прежнему синхронно ждёт `command_result` по timeout.  
С версии цикла 2026-03-18 `/ws` работает как transport-only loop с `AgentMessageRouter` и сервисами (`HandshakeService`, `CommandAckService`, `CommandResultService`, `OutboxIngestService`, `AgentCommandService`).  
`DeviceOutboxSender` поддерживает режимы `DEVICE_DISPATCH_MODE=poll|sharded` (default: `sharded`), где `sharded` использует per-device queue + shard workers + reconcile sweep без изменения wire-контракта. Для multi-instance используется DB-coordination (`dispatch_ready_devices`, lease claim per `device_id`).

---

## WebSocket endpoints

- **/ws** — агенты (Protocol V3). Handshake с `protocol_version`, capabilities и token обязательны.
- **/ws_ui** — UI клиенты. Первое сообщение — `ui_hello` с токеном; см. [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md).
- **/ws/remote-assist/{session_id}** — Remote Assist signaling relay for `role=operator|agent&token=...`. This endpoint is outside the agent `/ws` Protocol V3 transport, validates short-lived role tokens against `remote_access_sessions`, relays only approved WebRTC/session envelope types, and must not log full SDP or static TURN secrets.

---

## Связанные документы

- [README.md](README.md) — обзор сервера и API.
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — безопасность и аутентификация (токены, handshake, middleware).
- [pc_agent/docs/PROTOCOL_V3.md](../../pc_agent/docs/PROTOCOL_V3.md) — полная спецификация Protocol V3.
- [BOTTLENECKS_AND_RISKS.md](../../docs/archive/BOTTLENECKS_AND_RISKS.md) — исторические узкие места и риски проекта.
