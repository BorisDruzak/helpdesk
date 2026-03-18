# План доработок: тонкий `agent_handler`, тесты dispatch, async API, C2, B2–B5

**Статус (2026-03-18):** выполнены **A2**, **A1** (тесты на уровне HandshakeService/ShardDispatcher), **B1-min** (RFC + `poll_url` + 202), **C2** (`/api/modules/ping` + preflight агента). В бэклоге по этому документу: **B1-c** (UI), **B2–B5**, дробление крупных модулей WS.

Документ задаёт **порядок работ, границы модулей и критерии готовности**. Ниже — архивное описание шагов (раздел «текущее состояние» отражает состояние **до** выноса в отдельные файлы).

---

## Критерии успеха (Definition of Done)

| ID | Критерий | Как проверить |
|----|----------|---------------|
| **A2-DONE** | `server/websocket/agent_handler.py` ≤ **800 строк** (цель **500–800**) | `wc -l` / ревью; в файле только transport-loop + wiring |
| **A1-DONE** | Есть **интеграционные** тесты сценариев dispatch | pytest, см. раздел A1 |
| **B1-DONE** | Отдельный **RFC** в `server/docs/` + минимум один **публичный HTTP** путь «fire-and-forget + poll статуса операции» (или эквивалент в существующем API) | Дока + тесты API |
| **C2-DONE** | Preflight агента делает запрос к URL, **эквивалентному** пути скачивания модуля | См. раздел C2 |
| **B2/B3** | Отдельные эпики; DoD = дизайн-док + PoC или отмена с обоснованием | По желанию релиза |

---

# A2. Тонкий `agent_handler.py` — детальная разбивка

## Текущее состояние

- **`websocket_handler`** (~90 строк): цикл `async for msg`, JSON, `router.route`, flush batch ACK, cleanup.
- **`handle_handshake`** (~370 строк): V3, токен, регистрация агента, дублирующаяся логика с `HandshakeService` (сервис только вызывает legacy).
- **`handle_command_result`** (~1240 строк): основной объём файла.
- **`handle_outbox_item`** (~600 строк): валидация, ingest, NACK.
- **`persist_job_event`** (~50 строк): JobEventsRepo.

**Замечание по багу:** в `websocket_handler` используются `loop_safety_service.handle_unknown_message_type` / `handle_outbox_processing_exception`, но **`AgentLoopSafetyService()` не создаётся** в области видимости handler (экземпляр есть только внутри `handle_handshake`). При срабатывании этих веток возможен **`NameError`**. При рефакторинге **обязательно** инстанцировать `AgentLoopSafetyService()` в начале `websocket_handler` (один раз на соединение).

## Целевая структура каталога `server/websocket/`

```
server/websocket/
  agent_handler.py          # ТОЛЬКО: websocket_handler + импорты сервисов (~400–800 строк макс; цель меньше)
  agent_services.py         # Router, CommandAckService, AgentCommandService, AgentLoopSafetyService (уже есть — дополнять)
  agent_handshake.py        # Полная логика handshake (бывший handle_handshake), класс HandshakeHandler или функции
  agent_command_result.py   # Полная логика command_result (бывший handle_command_result)
  agent_outbox_ingest.py    # Полная логика outbox_item (бывший handle_outbox_item)
  job_event_persistence.py  # persist_job_event (опционально: app/services если хотите убрать из websocket-пакета)
```

## Порядок выноса (выполнять строго по шагам, после каждого шага — pytest + smoke)

### Шаг A2-1: `persist_job_event` + мелочи

1. Перенести **`persist_job_event`** в `server/websocket/job_event_persistence.py` (или `server/app/services/job_events.py`).
2. В `agent_command_result.py` (после шага A2-3) или пока в старом файле — импорт из нового модуля.
3. **Критерий:** тесты `server/tests` зелёные; нет циклических импортов.

### Шаг A2-2: `handle_outbox_item` → `agent_outbox_ingest.py`

1. Создать модуль `agent_outbox_ingest.py`.
2. Перенести тело **`handle_outbox_item`** целиком (включая вспомогательные функции, если они только для outbox — искать по `grep` внутри блока 1711–2306).
3. Публичный API: `async def handle_outbox_item(ws, data, state, agent_id, batch_ack_manager, event_validator) -> bool` (сигнатура как сейчас).
4. В `agent_handler.py` оставить **re-export** на один релиз или сразу в `OutboxIngestService` передавать `agent_outbox_ingest.handle_outbox_item`.
5. **Критерий:** `pytest server/tests/test_agent_message_router.py` + тесты connection/outbox при наличии.

### Шаг A2-3: `handle_command_result` → `agent_command_result.py`

1. Аналогично: один модуль, все импорты наверху модуля.
2. Зависимости: `normalize_command_result_payload`, репозитории, `OperationService`, `send_ws_command`, `push_chat_event_to_ui` — всё явно импортировать в новом файле.
3. **Критерий:** прогон тестов, затрагивающих command_result / operations (поиск по `handle_command_result`, `command_result` в `server/tests`).

### Шаг A2-4: `handle_handshake` → `agent_handshake.py`

1. Вынести **`handle_handshake`** в `agent_handshake.py`.
2. Обновить **`HandshakeService`**: вместо `legacy_handler` вызывать метод нового модуля **или** встроить логику в `HandshakeService.handle` (предпочтительно один класс `HandshakeHandler` с зависимостями для тестов).
3. Исправить **loop_safety**: создать `loop_safety = AgentLoopSafetyService()` в `websocket_handler` до цикла.
4. **Критерий:** интеграционный сценарий handshake (если есть тесты WS — прогнать).

### Шаг A2-5: Упростить `agent_handler.py`

Итоговое содержимое **`agent_handler.py`**:

- docstring (UTF-8, исправить mojibake).
- импорты.
- **`async def websocket_handler(request)`**: prepare, context, `BatchAckManager`, `EventValidator`, **`AgentLoopSafetyService()`**, сборка `AgentMessageRouter` с:
  - `HandshakeService(…)` → реализация из `agent_handshake`;
  - `CommandResultService(agent_command_result.handle_command_result)`;
  - `OutboxIngestService(agent_outbox_ingest.handle_outbox_item, …)`;
- цикл сообщений и `finally` unregister.

**Удалить** из `agent_handler.py` любые оставшиеся куски бизнес-логики.

### Шаг A2-6: Контроль размера и CODEMAP

1. **`wc -l server/websocket/agent_handler.py` ≤ 800** (лучше 400–600).
2. Обновить **`server/docs/CODEMAP.md`**: указать новые файлы и поток «WS агент → handshake / outbox / command_result».
3. Зафиксировать в коммите сообщение вида: `refactor(ws): thin agent_handler; split handshake/outbox/command_result`.

### Риски A2

- **Циклические импорты:** новые модули не должны импортировать `agent_handler`; только handler импортирует их.
- **Регрессии:** после каждого шага A2-2…A2-4 — точечный pytest.

---

# A1. Приёмочные сценарии тестов dispatch (offline → online, несколько устройств, нагрузка)

## Где живёт логика

- `server/websocket/device_outbox_sender.py` — `ShardDispatcher`, `DeviceReadyQueue`, `on_agent_online`.
- `state.register_agent` / disconnect в `agent_handler.websocket_handler`.

## Рекомендуемый файл тестов

`server/tests/test_device_dispatch_integration.py` (новый), маркеры `pytest.mark.asyncio`.

### Сценарий 1: offline → online (drain очереди)

**Идея:** пока агента нет в `connected_agents`, команда в outbox; после регистрации — `on_agent_online` / dispatch доставляет.

**Реализация теста (варианты):**

- **Интеграция с тестовой БД:** фикстура PostgreSQL/sqlite (как в проекте), вставка строки `device_outbox`, вызов API enqueue, затем эмуляция подключения (мок `state` + вызов `on_agent_online(device_id)`) и проверка, что sender пытается отправить (мок WS).
- **Упрощённый:** юнит-тест `ShardDispatcher` + мок `state.get_agent` возвращает ws после «online».

**DoD:** тест падает, если убрать вызов `on_agent_online` из handshake path.

### Сценарий 2: несколько устройств, разные шарды

- Зафиксировать `SHARD_COUNT` (env или константа в тесте).
- Enqueue для `device_A` и `device_B`; проверить, что оба попадают в очередь готовности и обрабатываются (порядок не обязан быть детерминированным, но оба должны получить pop).

### Сценарий 3: «нагрузка» (лёгкая)

- N=50–100 устройств, для каждого один enqueue; измерить, что dispatcher не теряет device_id (все уникальные `device_id` хотя бы раз обработаны в разумное время в тесте с мок-тиками).

**Инфраструктура:** при необходимости вынести общие фикстуры в `server/tests/conftest.py` (state mock, fake ws).

---

# B1. Неблокирующая модель ответа + async API для UI

## Текущее

- `send_ws_command(..., wait_for_result=False)` уже **не ждёт** `command_result` на транспорте.
- Блокировка остаётся у **вызовов с `wait_for_result=True`** (типичный admin run_tool).

## Фаза B1-a: RFC (обязательно первым)

**Файл:** `server/docs/RFC_ASYNC_COMMAND_AND_OPERATION_POLL.md`

**Содержание (чеклист):**

1. Модель: **operation_id** как ключ; состояния операции (queued / sent / accepted / terminal).
2. **HTTP:**  
   - `POST .../run_tool` (или существующий endpoint) с флагом `async=true` → ответ **202** + `{ operation_id, poll_url }`.  
   - `GET .../operations/{id}` или расширение существующего — статус + результат (если terminal).
3. **WebSocket UI** (`/ws_ui`): опционально событие `operation_updated` (если уже есть publisher — переиспользовать).
4. Ограничения: таймауты, идемпотентность, совместимость с consent-path.
5. Явное указание: **семафоры/пул воркеров** как альтернатива для снижения числа висящих корутин без смены контракта UI.

## Фаза B1-b: Минимальная реализация (после RFC)

1. В `ToolExecutionService.run_tool` (или handler API): ветка **async** — вызов `send_ws_command(..., wait_for_result=False)` + возврат `operation_id`.
2. Endpoint статуса операции (если ещё нет — добавить по RFC).
3. Тесты: `server/tests/test_*async*operation*` — запуск async, poll до terminal (мок агента или тестовый WS).

## Фаза B1-c: UI админки

- Подписка на обновление или polling из браузера; не блокировать вкладку на длительный HTTP.

---

# C2. Ping до download URL модулей (агент)

## Проблема

Сейчас: `GET {api_url}/health` и `GET {api_url}/modules/catalog`.  
Путь **скачивания** модуля: `GET {SERVER_PUBLIC_BASE_URL}/api/modules/{name}/{version}/download` — другой маршрут, другие права/прокси.

## Решение

1. **Лёгкий HEAD/GET** на шаблонный URL, не требующий реального модуля:
   - либо завести **`GET /api/modules/ping`** (200, тело `"ok"`) в `server/modules/handlers.py` и документировать в `MODULES_API.md`;
   - либо HEAD на `/api/modules/__ping__/0/download` с ответом **404** без таймаута — хуже для диагностики.
2. **Рекомендуется:** явный **`/api/modules/reachability`** или **`/api/modules/ping`** с тем же middleware, что и download (проверка доступности цепочки).
3. В **`pc_agent/ws_agent.py`** `_check_server_reachability`: добавить третий endpoint — `{base}/api/modules/ping` (или согласованный путь).
4. **DoD:** при недоступности именно «модульного» префикса логируется отдельное предупреждение.

---

# B2. Масштабирование outbox за пределы одного процесса

**Эпик, не патч за день.**

## Этапы

1. **Дизайн-док** `server/docs/DESIGN_OUTBOX_MULTIWORKER.md`:  
   - вариант Redis stream + consumer group;  
   - вариант DB `FOR UPDATE SKIP LOCKED` + отдельный worker-процесс;  
   - шардирование по `device_id` между инстансами aiohttp.
2. **Инварианты:** один командный поток на `device_id`; не дублировать доставку при reconnect.
3. **PoC:** один воркер, читающий из БД очередь «pending dispatch», основной процесс только пишет.

**DoD эпика:** рабочий PoC на стенде + метрики.

---

# B3. DB-backed state_manager

1. Документ: текущее состояние в памяти (`connected_agents`, маршрутизация).
2. Таблицы/кэш: presence, TTL, sticky session.
3. Feature flag `USE_DB_PRESENCE=1`.
4. Миграции + постепенный перевод handshake/register.

**DoD:** отдельный roadmap-эпик; не смешивать с A2 в одном PR.

---

# B4. Рефакторинг `pc_agent/ws_agent.py`

## Целевые модули (подкаталог `pc_agent/ws/` или `pc_agent/runtime/`)

| Модуль | Ответственность |
|--------|-----------------|
| `ws_connection.py` | connect/reconnect, backoff, `_check_server_reachability` |
| `ws_read_loop.py` | чтение WS, dispatch по type |
| `ws_auth_flow.py` | `GuiAuthStateMachine`, connection_request, token load |
| `ws_orchestrator_dispatch.py` | команды run_tool, модули, очередь на оркестратор |
| `ws_scheduler_rpc.py` | `_handle_scheduler_rpc`, `_scheduler_runtime_loop` |
| `ws_gui_hooks.py` | EventBus, consent, UI callbacks |

**Фасад:** класс `WSAgent` (или текущее имя) в `ws_agent.py` **только** собирает зависимости и делегирует; публичный API для `main` и тестов не ломать.

**DoD:** `ws_agent.py` ≤ ~300–500 строк фасада; поведение покрыто существующими/новыми тестами.

---

# B5. Политика in_progress / повторный запуск

1. **Анализ зазора:** между `command_ack accepted` и первым полезным событием / `command_result` — что происходит при краше агента.
2. **Документы:**  
   - дополнить `server/docs/COMMAND_RESULT_LIFECYCLE.md` (состояния, таймауты, повторная отправка);  
   - `pc_agent/docs/SENDER.md` (at-most-once по `command_id` / seen set).
3. **Код:**  
   - `operation_watchdog.py` — явные таймауты для `in_progress`;  
   - опционально на агенте: не выполнять повторно тот же `command_id`, если уже был `seen`.
4. **DoD:** согласованный текст в двух доках + тесты watchdog при наличии.

---

# Рекомендуемый порядок выполнения (вехи)

1. **A2** (по шагам A2-1 … A2-6) — **до достижения ≤800 строк** в `agent_handler.py`.
2. **A1** — параллельно после A2-2 (когда outbox/handshake стабильны) или сразу после A2.
3. **C2** — маленький PR: endpoint ping + агент.
4. **B1-a** RFC → **B1-b** API → **B1-c** UI.
5. **B4** — отдельная ветка, после стабилизации A2.
6. **B5** — дока + watchdog.
7. **B2 / B3** — по приоритету нагрузки.

---

# Чеклист перед merge крупных PR

- [ ] `python scripts/verify_workspace.py`
- [ ] `pytest` по затронутым каталогам
- [ ] Обновлён `server/docs/CODEMAP.md` (и при B4 — `pc_agent/docs/CODEMAP.md`)
- [ ] Нет mojibake в изменённых файлах (UTF-8)
- [ ] Для B1 — синхронизация с `server/docs/PROTOCOL_V3.md` при смене контракта
