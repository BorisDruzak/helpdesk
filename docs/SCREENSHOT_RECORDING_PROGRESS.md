# Скриншот и запись экрана — выполненные работы и дальнейший план

Исходный план: `docs/PLAN_SCREENSHOT_SCREEN_RECORDING.md`.

---

## Выполнено: этап 0 (подготовка и контракты)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 0.1 | Создан `server/docs/ARTIFACTS_API.md` с контрактами upload/download и форматом дескриптора артефакта | ✅ |
| 0.2 | В `pc_agent/core/tool_response.py` в `ArtifactDescriptor` добавлены поля `kind`, `expires_at` | ✅ |
| 0.3 | В `ArtifactManager.MIME_MAP` и `FileUploader.MIME_MAP` добавлен тип `.mp4` → `video/mp4` | ✅ |

**DoD:** Документация контрактов готова, модели расширены.

---

## Выполнено: этап 1 (сервер — модель и upload, MVP скриншота)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 1.1 | Alembic миграция `20260204_1000_015_add_artifacts.py`: таблица `artifacts` (artifact_id, storage_path, original_name, mime_type, size_bytes, sha256, kind, device_id, ticket_id, operation_id, expires_at, created_at) | ✅ |
| 1.2 | SQLAlchemy модель `Artifact` в `server/app/db/models.py` | ✅ |
| 1.3 | Репозиторий `ArtifactsRepo`: `create()`, `get_by_id()`, `delete_expired()` в `server/app/repos/artifacts_repo.py` | ✅ |
| 1.4 | Переписан `handle_upload` в `server/uploads/handlers.py`: потоковая запись, лимит 200MB, sha256 на лету, сохранение в `artifacts` | ✅ |
| 1.5 | При upload извлекаются `ticket_id`, `operation_id`, `kind` из multipart (опциональные поля) | ✅ |
| 1.6 | Агент: `FileUploader.upload_file()` принимает `meta` и передаёт в multipart `ticket_id`, `operation_id`, `kind`; `ArtifactManager.upload()` передаёт meta и заполняет дескриптор из ответа (artifact_id, kind, expires_at) | ✅ |
| 1.7 | Публичная раздача `add_static('/uploads/')` отключена — артефакты только через защищённый download (этап 2) | ✅ |

**DoD:** Upload сохраняет в БД, streaming работает, sha256 считается, лимит 200MB.  
**Конфиг:** В `server/config.py` добавлена константа `ARTIFACT_MAX_BYTES = 200 * 1024 * 1024`.

---

## Выполнено: этап 2 (Secure Download)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 2.1 | Создан `ArtifactService` в `server/app/services/artifact_service.py`: `get_artifact_for_download(artifact_id, auth_context)` — проверка прав по device_id (агент) и по ticket_id (UI) | ✅ |
| 2.2 | Endpoint `GET /api/artifacts/{artifact_id}/download` в `server/uploads/handlers.py` (`handle_artifact_download`) | ✅ |
| 2.3 | Auth middleware — endpoint под `/api/` защищён | ✅ |
| 2.4 | Обработка заголовка `Range: bytes=...` для видео (ответ 206 Partial Content) | ✅ |
| 2.5 | Маршрут зарегистрирован в `server/routes.py` | ✅ |

**DoD:** Download с Bearer-токеном работает; без токена — 401; без прав — 403; артефакт не найден — 404; TTL истёк — 410. Range для mp4 поддерживается.

---

## Выполнено: этап 3 (GUI агента — кнопки Screenshot и Record)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 3.1 | В `ChatPanel` добавлены кнопки «Screenshot» и «Record Screen» и метка статуса | ✅ |
| 3.2 | При нажатии Screenshot: вызов `TicketApiClient.run_tool()` → `POST /api/tools/run` с `tool_name="screen.collect"`, `preset_id="primary_monitor"` | ✅ |
| 3.3 | При нажатии Record: диалог выбора длительности (30/60/120/300 сек), затем run_tool с `tool_name="screen.record"`, `params={"duration_sec": N}` | ✅ |
| 3.4 | Отображение статуса: «Идёт захват...» / «Идёт запись...», «Скриншот отправлен...» / «Запись отправлена...», «Ошибка: ...»; сброс через 5 сек | ✅ |

**DoD:** Кнопки доступны при открытом тикете, вызывают run_tool, статус отображается.  
**Файлы:** `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py` (метод `run_tool`).

---

## Выполнено: этап 4 (свернуть окно + STOP-кнопка)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 4.1 | События для UI: `prepare_screen_capture`, `screen_capture_done`, `prepare_screen_recording`, `screen_recording_done`, `stop_recording_requested` (через POST /ui/stop_recording) | ✅ |
| 4.2 | В `orchestrator._handle_run_tool` перед вызовом `screen.collect`/`screen.record`: публикация `prepare_screen_capture` / `prepare_screen_recording` через ui_bus с `operation_id` | ✅ |
| 4.3 | После завершения tool (успех или ошибка): публикация `screen_capture_done` / `screen_recording_done`; для record — снятие регистрации в RecordingController | ✅ |
| 4.4 | GUI: при `prepare_screen_capture` — `window.showMinimized()` | ✅ |
| 4.5 | GUI: при `screen_capture_done` — `window.showNormal()` | ✅ |
| 4.6 | GUI: при `prepare_screen_recording` — минимизация окна + красная STOP-кнопка (always-on-top, bottom-left) | ✅ |
| 4.7 | GUI: при нажатии STOP — POST `/ui/stop_recording` с `operation_id` → RecordingController.signal_stop() | ✅ |
| 4.8 | Модуль `screen.record` проверяет флаг/Event «остановить запись» через RecordingController.get(operation_id) | ✅ (этап 5) |
| 4.9 | GUI: при `screen_recording_done` — скрыть STOP-кнопку, `window.showNormal()` | ✅ |

**DoD:** При скриншоте окно сворачивается и восстанавливается. При записи — сворачивается, показывается STOP; по нажатию отправляется сигнал остановки (модуль record будет обрабатывать в этапе 5).

**Файлы:**
- `pc_agent/core/recording_controller.py` — глобальный RecordingController (register/get/signal_stop/unregister).
- `pc_agent/core/orchestrator.py` — публикация prepare_* / done, регистрация record в контроллере.
- `pc_agent/ui_bridge/api_server.py` — endpoint POST `/ui/stop_recording`.
- `pc_agent/ui_gui/main_window.py` — обработка событий, минимизация/восстановление, плавающая STOP-кнопка.

---

## Выполнено: этап 5 (модуль screen.record)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 5.1 | Реализован `screen.record` в `pc_agent/modules/impl/screen.py`: ScreenRecordParams, метод record(), mss + ffmpeg (subprocess), лимит 200MB | ✅ |
| 5.2 | Интеграция с STOP: оркестратор передаёт `operation_id` в params; модуль получает `stop_event` из `get_recording_controller().get(operation_id)` и проверяет в цикле записи | ✅ |
| H.5 | Параметры: duration_sec 1–300, fps 5–30, max_width, quality_crf, monitor; presets short (30 сек) / long (300 сек) | ✅ |
| H.5 | Проверка ffmpeg в PATH при вызове; запись в temp_dir, _artifacts с kind=screen_recording, mime=video/mp4; -movflags +faststart | ✅ |

**DoD:** Запись до 5 мин, mp4, ≤200MB, досрочная остановка по STOP-кнопке работает.

**Зависимость:** для записи экрана нужен **ffmpeg** в PATH (системная установка); в `requirements.txt` добавлен комментарий.

**Файлы:** `pc_agent/modules/impl/screen.py`, `pc_agent/core/orchestrator.py` (передача operation_id для screen.record).

---

## Выполнено: этап 6 (Web UI тикета — артефакты в ленте)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 6.1 | В React-ленте тикета при `tool_call_result` с `artifacts` — рендер карточек артефактов | ✅ |
| 6.2 | Для `kind=screenshot` или `mime=image/*`: загрузка через fetch (Bearer) и отображение в `<img>` | ✅ |
| 6.3 | Для `kind=screen_recording` или `mime=video/mp4`: `<video controls preload="metadata">` с тем же fetch | ✅ |
| 6.4 | Сервер при сохранении `tool_call_result` в ticket_events передаёт в payload поле `artifacts` из command_result.data | ✅ |

**DoD:** Скриншоты и видео отображаются в тикете; воспроизведение и перемотка работают. Авторизация — через перехват fetch (Bearer из localStorage).

**Файлы:** `server/websocket/agent_handler.py` (добавлено `artifacts` в result_payload), `webapp/src/pages/tickets/detail-page.tsx` (normalization, image/video selection and artifact URLs).

---

## Выполнено: этап 7 (Hardening)

| Шаг | Действие | Статус |
|-----|----------|--------|
| 7.1 | Retry upload в `FileUploader`: до 3 попыток, exponential backoff при `ServerConnectionError` и `aiohttp.ClientError` | ✅ |
| 7.2 | Фоновая задача: раз в час `ArtifactsRepo.delete_expired()` + удаление файлов с диска (`UPLOAD_DIR`), запуск при `ENABLE_DB_PERSISTENCE` | ✅ |
| 7.3 | Идемпотентность upload: при совпадении `sha256` и `operation_id` возвращается существующий `artifact_id`, дубликат файла удаляется | ✅ |

**DoD:** Ретраи при сбоях соединения, периодическая очистка истёкших артефактов, повторная отправка того же файла по operation_id не создаёт дубликат.

**Файлы:**
- `pc_agent/network/uploader.py` — ретраи и `_do_upload_once`.
- `server/server.py` — задача `artifacts_expired_cleanup_task`, интервал 1 час.
- `server/app/repos/artifacts_repo.py` — метод `get_by_sha256_and_operation_id`.
- `server/uploads/handlers.py` — проверка перед `create`, возврат существующего артефакта при совпадении sha256+operation_id.

---

## Исправления багов

### 403 ROLE_NOT_ALLOWED при запуске Screenshot / Record

**Симптом:** При нажатии «Screenshot» или «Record Screen» в GUI агента: `HTTP 403: Policy violation, required_role: llm, support или admin`.

**Причины (исправлено):**
1. **Формат list_tools:** Сервер искал инструмент по полям `name`/`tool_id` и метаданные в `metadata`, тогда как агент отдаёт формат `tool` + `spec.metadata`. В результате метаданные не находились, применялся дефолт `safe_read` → доступ только для llm/support/admin.
2. **Роли для screen-инструментов:** Даже при корректном парсинге у `screen.collect` и `screen.record` был `risk_level=sensitive_read` (доступ только support/admin). Для кнопок в тикете нужна возможность запуска от роли **user** (владелец устройства).

**Правки:**
- **Сервер** `server/core/policy_engine.py`: в `get_tool_metadata()` добавлена поддержка формата агента — сопоставление по `tool.get("tool")` и чтение `metadata` из `tool.get("spec", {}).get("metadata", {})`.
- **Агент** `pc_agent/modules/impl/screen.py`: для `collect` и `record` задано `metadata_allow_roles=["user", "llm", "support", "admin"]`.

**Дополнительные правки (повторная 403):**
- **Роль `agent`:** В GUI агента запрос идёт с **токеном устройства** (Bearer), поэтому сервер определяет `actor_role="agent"`, а не "user". В `allow_roles` для screen-инструментов добавлена роль **"agent"** (в агенте и в fallback на сервере).
- **Fallback при пустом списке tools:** Если `get_tools_list(device_id)` вернул `None` (агент офлайн или снапшот ещё не создан), для `screen.collect` и `screen.record` сервер больше не подставляет дефолт `safe_read`, а использует метаданные с `allow_roles=["user", "agent", "llm", "support", "admin"]` (в `server/tools/handlers.py` и `server/websocket/protocol.py`).
- **Старые снапшоты:** В `get_tool_metadata()` для screen-инструментов, если в снапшоте `allow_roles` отсутствует (null), подставляется тот же список ролей.
- **Отладка 403:** В теле ответа 403 добавлено поле `actor_role`, чтобы видеть, с какой ролью сервер воспринял запрос.

**Запуск без шага согласия (исправление 202 waiting_consent):** Для кнопок Screenshot/Record в GUI нажатие считается явным действием пользователя, поэтому consent не запрашивается. Для `screen.collect` и `screen.record` выставлено `metadata_requires_consent=False` (агент); на сервере в fallback и в `get_tool_metadata` для этих инструментов также принудительно `requires_consent=False`. Операция сразу ставится в очередь и выполняется агентом.

### 403 при просмотре скриншота в веб-интерфейсе админа

**Симптом:** Артефакт успешно загружается (логи сервера: «Артефакт загружен»), но в тикете картинка не открывается — при запросе `GET /api/artifacts/{id}/download` приходит 403.

**Причина:** Для доступа по UI-токену сервер проверяет, что у артефакта задан `ticket_id` и тикет существует (`ArtifactService`). Агент при upload не передавал `ticket_id` и `operation_id` в multipart, поэтому артефакт сохранялся без привязки к тикету и доступ для UI блокировался.

**Правка:** В `pc_agent/core/orchestrator.py` при формировании `ArtifactIntent` для загрузки в `meta` каждого артефакта подставляются `ticket_id` (из `command_params`) и `operation_id` (из `meta.request_id`). Uploader отправляет их в multipart, сервер пишет в таблицу `artifacts` — после этого админ/UI получает доступ к скачиванию по тому же тикету.

### 403 при скачивании артефакта: в БД нет ticket_id (fallback по ticket_events)

**Симптом:** В React ticket detail скриншоты не отображаются: `GET /api/artifacts/{artifact_id}/download` возвращает **403 Forbidden**. В таблице `artifacts` у записей поле `ticket_id` = null (артефакт не привязан к тикету при upload).

**Причина:** Для UI-токена доступ разрешён, если у артефакта задан `artifact.ticket_id` и тикет существует, либо если в запросе передан `?ticket_id=...` и тикет содержит этот артефакт в событиях (`tool_call_result` с `payload.artifacts[].artifact_id`). Проверка «тикет содержит артефакт» делалась через `get_events(..., limit=500)` и обход в Python — при большом числе событий или иной структуре payload проверка могла не срабатывать.

**Правки (2026-02-05):**
1. **Сервер** `server/app/repos/ticket_events_repo.py`: метод `ticket_contains_artifact()` переведён на один SQL-запрос по JSONB без лимита — поиск по `ticket_events` с `event_type = 'tool_call_result'` и `EXISTS (jsonb_array_elements(payload->'artifacts') ... elem->>'artifact_id' = :artifact_id)`. Это гарантирует доступ для уже загруженных артефактов без `ticket_id` в БД, если в запросе download передан `?ticket_id=...` и в тикете есть соответствующее событие.
2. **Сервер** `server/app/services/artifact_service.py`: при отказе в доступе (403) добавлено логирование причины (тикет не найден, артефакт не в событиях, нет ticket_id в запросе).
3. **Агент** `pc_agent/core/orchestrator.py`: при загрузке артефактов без `ticket_id` в контексте добавлено предупреждение в лог — для новых загрузок по возможности передавать `ticket_id` (run_tool с тикета должен содержать `ticket_id` в params).

**Рекомендация:** Чтобы новые артефакты сохранялись с `ticket_id` в БД, запуск инструмента (Screenshot/Record) должен идти из тикета (POST /api/tools/run с `ticket_id`), тогда сервер передаёт `ticket_id` агенту в команде run_tool и агент подставляет его в meta при upload.

### TOOL_NOT_FOUND для screen.record (кнопка Record, нет STOP)

**Симптом:** При нажатии «Record Screen» агент возвращает ошибку: `Инструмент "screen.record" не найден в реестре` (TOOL_NOT_FOUND). Кнопка STOP не появляется, т.к. запись не стартует.

**Причина:** В реестре модулей при уникальном коротком имени инструмента в списке tools хранится только короткое имя (например `record`), а запрос приходит в формате `screen.record`. Метод `get_tool("screen.record")` искал только точное совпадение по полю `tool` и не находил запись.

**Правка (2026-02-05):** В `pc_agent/core/registry.py` в методе `get_tool()` добавлен fallback: если точное совпадение не найдено и имя содержит точку, выполняется поиск по паре `module` + короткое имя (например `screen` + `record`). После этого `screen.record` корректно находится, запись запускается и показывается STOP-кнопка.

### Где лежат файлы скриншотов и записей

- **Сервер:** каталог задаётся в `server/config.py`: `UPLOAD_DIR = Path("uploads")` (относительно рабочей директории процесса сервера). Полный путь к файлу: `{UPLOAD_DIR}/{artifact_id}{suffix}`, например `uploads/ce8f57f8-d934-46fb-82af-798789305c28.png`. При старте сервер логирует абсолютный путь: «Папка загрузок: …».
- **Агент:** временные скриншоты до отправки создаются в `pc_agent/data/temp/` (например `screenshot_<timestamp>.png`) и удаляются после загрузки или при ошибке.

---

## Итог

Все этапы плана скриншот/запись экрана (0–7) выполнены. Детали — в `docs/PLAN_SCREENSHOT_SCREEN_RECORDING.md` (разделы G, H, I).

---

## Проверка миграции и БД

После применения миграции 015 таблица `artifacts` должна присутствовать в PostgreSQL. Проверка: выполнить запрос `SELECT * FROM artifacts LIMIT 1;` (пустой результат допустим) или `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'artifacts' ORDER BY ordinal_position;` (через MCP PostgreSQL или psql к рабочей БД).

## Документация

- **Сервер:** [server/docs/ARTIFACTS_API.md](../server/docs/ARTIFACTS_API.md) — контракты upload/download, дескриптор артефакта, query-параметр `ticket_id` для download (fallback).
- **Сервер:** [ENDPOINT_OPERATION_CONTRACT.md](../server/docs/ENDPOINT_OPERATION_CONTRACT.md) — границы интеграции Helpdesk и Endpoint.
- **Агент:** [pc_agent/docs/MODULES.md](../pc_agent/docs/MODULES.md) — модуль screen (screen.collect, screen.record).
- **Агент:** [pc_agent/docs/README.md](../pc_agent/docs/README.md) — раздел «Графический интерфейс», ссылки на скриншот/запись.
