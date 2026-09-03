# План: Оптимизированная доставка скриншотов и записи экрана

## Дополнение: STOP-кнопка при записи

**Требование:** Во время записи экрана GUI агента сворачивается, **НО** внизу слева экрана появляется красная кнопка **STOP** для ранней остановки записи.

- Кнопка отображается поверх всех окон (always-on-top), в фиксированной позиции (bottom-left)
- При нажатии STOP: запись останавливается досрочно, сохраняется уже записанный фрагмент, GUI восстанавливается
- Кнопка скрывается сразу после остановки записи

---

## A) Архитектура и поток данных (сводка)

### Инварианты
- Тип события: только по `device_seq` vs `agent_seq` (не по `ticket_id`)
- `tool_call_started` создаётся сервером до отправки `run_tool`
- Файлы — через HTTP артефакты, бинарники не в WS

### Скриншот: GUI → run_tool → collect → upload → command_result → отображение в тикете
### Запись: GUI → run_tool → record (с STOP) → upload → command_result → video в тикете

---

## B–F) Контракты, риски, тест-кейсы

См. исходный план (контракты API, artifact descriptor, upload/download, риски, тест-кейсы).

---

## G) Этапы работ — пошагово (с учётом текущей архитектуры)

### G.1 Этап 0: Подготовка и контракты

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 0.1 | Создать документ `server/docs/ARTIFACTS_API.md` с контрактами upload/download и artifact descriptor | `server/docs/` | — |
| 0.2 | Обновить `ArtifactDescriptor` в `pc_agent/core/tool_response.py`: добавить поля `kind`, `expires_at` (опционально) | `pc_agent/core/tool_response.py` | — |
| 0.3 | Добавить MIME `.mp4` в `ArtifactManager.MIME_MAP` и `FileUploader.MIME_MAP` | `pc_agent/core/artifacts.py`, `pc_agent/network/uploader.py` | — |

**DoD:** Документация контрактов готова, модели расширены.

---

### G.2 Этап 1: Сервер — модель и upload (MVP скриншота)

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 1.1 | Alembic миграция: таблица `artifacts` (artifact_id, storage_path, original_name, mime_type, size_bytes, sha256, kind, device_id, ticket_id, operation_id, expires_at, created_at) | `server/app/db/migrations/` | — |
| 1.2 | SQLAlchemy модель `Artifact` в `server/app/db/models.py` | `server/app/db/models.py` | 1.1 |
| 1.3 | Репозиторий `ArtifactsRepo`: `create()`, `get_by_id()`, `delete_expired()` | `server/app/repos/artifacts_repo.py` | 1.2 |
| 1.4 | Переписать `handle_upload` в `server/uploads/handlers.py`: потоковая запись, лимит 200MB, sha256 на лету, сохранение в `artifacts` | `server/uploads/handlers.py` | 1.3 |
| 1.5 | При upload извлекать `ticket_id`, `operation_id`, `kind` из multipart (опциональные поля) | `server/uploads/handlers.py` | 1.4 |
| 1.6 | Агент: расширить `FileUploader.upload_file()` — передавать в multipart `ticket_id`, `operation_id`, `kind` (если доступны из meta) | `pc_agent/network/uploader.py` | 1.5 |
| 1.7 | Убрать или ограничить публичную раздачу `add_static('/uploads/')` — артефакты только через защищённый download | `server/server.py` | — |

**DoD:** Upload сохраняет в БД, streaming работает, sha256 корректен, лимит 200MB.

**Тестирование:** Upload 1MB PNG, проверка записи в `artifacts`, sha256.

---

### G.3 Этап 2: Сервер — Secure Download

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 2.1 | Создать `ArtifactService`: `can_access(artifact_id, auth_context)` — проверка прав по ticket_id | `server/app/services/artifact_service.py` | 1.3 |
| 2.2 | Endpoint `GET /api/artifacts/{artifact_id}/download` в `server/uploads/handlers.py` | `server/uploads/handlers.py` | 2.1 |
| 2.3 | Auth middleware (уже есть) — endpoint под `/api/` защищён | — | — |
| 2.4 | Обработка `Range: bytes=...` для видео (206 Partial Content) | `server/uploads/handlers.py` | 2.2 |
| 2.5 | Регистрация маршрута в `server/routes.py` | `server/routes.py` | 2.2 |

**DoD:** Download с Bearer token работает; без токена 401; без прав 403; TTL истёк — 404/410.

**Тестирование:** Download с токеном, без токена, Range для mp4.

---

### G.4 Этап 3: GUI агента — кнопки Screenshot и Record

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 3.1 | Добавить в `ChatPanel` или `MainWindow` две кнопки: "Screenshot", "Record Screen" | `pc_agent/ui_gui/chat_panel.py` или `main_window.py` | — |
| 3.2 | При нажатии Screenshot: вызов `POST /api/tools/run` с `tool_name="screen.collect"`, `preset_id="primary_monitor"` (через `TicketApiClient` или `ServerApiClient`) | `pc_agent/ui_gui/` | Наличие тикета/чата |
| 3.3 | При нажатии Record: вызов `POST /api/tools/run` с `tool_name="screen.record"`, `params={"duration_sec": 300}` (или диалог выбора длительности) | `pc_agent/ui_gui/` | 3.2 |
| 3.4 | Отображение статуса: "Идёт захват..." / "Загружается..." / "Готово" / "Ошибка" — через события `tool_started`, `tool_result` (SSE или ui_bus) | `pc_agent/ui_gui/` | 3.1 |

**DoD:** Кнопки вызывают run_tool, статус отображается.

**Примечание:** run_tool идёт через сервер (Tools API → device_outbox → WS → агент). Агент получает команду в `ws_agent.execute_command` → `orchestrator.handle_command` → `_handle_run_tool`.

---

### G.5 Этап 4: Стратегия «свернуть окно» + STOP-кнопка

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 4.1 | Определить события для UI: `prepare_screen_capture`, `screen_capture_done`, `prepare_screen_recording`, `screen_recording_done`, `stop_recording_requested` | `pc_agent/` | — |
| 4.2 | В `orchestrator._handle_run_tool` перед вызовом `screen.collect` или `screen.record`: публиковать `prepare_screen_capture` / `prepare_screen_recording` через `ui_bus` | `pc_agent/core/orchestrator.py` | ui_bus |
| 4.3 | После завершения tool (в finally или после await): публиковать `screen_capture_done` / `screen_recording_done` | `pc_agent/core/orchestrator.py` | 4.2 |
| 4.4 | GUI: подписаться на эти события. При `prepare_screen_capture`: `window.showMinimized()` | `pc_agent/ui_gui/main_window.py` | 4.1 |
| 4.5 | GUI: при `screen_capture_done`: `window.showNormal()` | `pc_agent/ui_gui/main_window.py` | 4.4 |
| 4.6 | GUI: при `prepare_screen_recording`: минимизировать окно + показать красную STOP-кнопку (always-on-top, bottom-left) | `pc_agent/ui_gui/` | 4.4 |
| 4.7 | GUI: при нажатии STOP — отправить `stop_recording_requested` в orchestrator/agent | `pc_agent/ui_gui/` | 4.6 |
| 4.8 | Модуль `screen.record` должен проверять флаг/Event «остановить запись» (см. раздел H) | `pc_agent/modules/impl/screen.py` | H |
| 4.9 | GUI: при `screen_recording_done` — скрыть STOP-кнопку, `window.showNormal()` | `pc_agent/ui_gui/main_window.py` | 4.6 |

**DoD:** При скриншоте окно сворачивается и восстанавливается. При записи — сворачивается, показывается STOP, по нажатию запись останавливается.

---

### G.6 Этап 5: Модуль screen.record (детали — см. раздел H)

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 5.1 | Реализовать `screen.record` (см. раздел H) | `pc_agent/modules/impl/screen.py` | H |
| 5.2 | Интегрировать с механизмом `stop_recording_requested` (Event/флаг) | `pc_agent/modules/impl/screen.py`, `orchestrator` | 4.8 |

**DoD:** Запись до 5 мин, mp4, ≤200MB, ранняя остановка работает.

---

### G.7 Этап 6: Web UI тикета — отображение артефактов

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 6.1 | В React-ленте тикета: при `command_result` с `artifacts` — рендерить карточки артефактов | `webapp/src/pages/tickets/detail-page.tsx` | 2.5 |
| 6.2 | Для `kind=screenshot` или `mime=image/*`: отобразить image download URL через cookie-session | `webapp/src/pages/tickets/detail-page.tsx` | 6.1 |
| 6.3 | Для `kind=screen_recording` или `mime=video/mp4`: отобразить video download URL | `webapp/src/pages/tickets/detail-page.tsx` | 6.1 |
| 6.4 | Проверить, что React ticket detail получает events с artifacts (typed API или WebSocket bridge) | `webapp/src/pages/tickets/detail-page.tsx` | — |

**DoD:** Screenshot и видео отображаются в тикете, воспроизведение и перемотка работают.

---

### G.8 Этап 7: Hardening

| Шаг | Действие | Где | Зависимости |
|-----|----------|-----|-------------|
| 7.1 | Retry upload в `FileUploader`: 3 попытки, exponential backoff при ServerConnectionError | `pc_agent/network/uploader.py` | — |
| 7.2 | Фоновая задача: `DELETE FROM artifacts WHERE expires_at < NOW()` + удаление файлов | `server/` (cron или periodic task) | 1.3 |
| 7.3 | Идемпотентность upload: при совпадении sha256+operation_id возвращать существующий artifact_id | `server/uploads/handlers.py` | 1.4 |

**DoD:** Ретраи, cleanup, идемпотентность работают.

---

## H) Реализация модуля screen.record — пошагово

### H.1 Зависимости и окружение

| Шаг | Действие | Файл / команда |
|-----|----------|----------------|
| H.1.1 | Добавить в `requirements.txt` (pc_agent): `imageio`, `imageio-ffmpeg` ИЛИ использовать subprocess вызов `ffmpeg` | `pc_agent/requirements.txt` |
| H.1.2 | Альтернатива: `python-mss` (уже есть) + запись кадров в временный файл + `ffmpeg` для кодирования | — |
| H.1.3 | Проверка наличия `ffmpeg` в PATH при старте модуля (опционально) | `screen.py` |

### H.2 Pydantic-модель параметров

```python
class ScreenRecordParams(BaseModel):
    duration_sec: int = Field(ge=1, le=300, description="Длительность записи 1-300 сек")
    fps: int = Field(default=15, ge=5, le=30)
    max_width: int = Field(default=1920, ge=640, le=3840)
    quality_crf: int = Field(default=28, ge=18, le=40)
    monitor: int = Field(default=1)
```

### H.3 Логика записи (псевдокод)

```
1. Валидация: duration_sec in [1, 300], size_limit_mb = 200
2. Оценка размера: ~ (width * height * fps * duration * 0.1) — грубая оценка для H.264
   Если оценка > 200MB — снизить fps или max_width
3. temp_path = temp_dir / f"recording_{timestamp}.mp4"
4. Цикл записи:
   - Каждые 1/fps сек: mss.grab() → кадр
   - Записать кадр в буфер/pipe для ffmpeg
   - Проверять stop_event.is_set() — при True выйти из цикла
   - Проверять текущий размер файла — при приближении к 200MB остановиться
5. Завершить ffmpeg (закрыть pipe), дождаться финализации mp4
6. Проверить размер — если > 200MB, логировать warning (уже остановились раньше)
7. Формировать observations с _artifacts, _cleanup_paths
```

### H.4 Интеграция с STOP-кнопкой

- Orchestrator перед вызовом `record()` создаёт `asyncio.Event()` — `stop_recording_event`
- Кладёт в контекст (например, в `meta` или в thread-local / contextvar)
- Модуль `record()` принимает опциональный аргумент `stop_event: asyncio.Event`
- При `stop_event.is_set()` — прерывает цикл захвата, финализирует файл
- GUI по нажатию STOP вызывает метод агента (через ui_bus → orchestrator) для установки `stop_recording_event.set()`

**Вариант:** передавать `stop_event` через `params` или через отдельный механизм (например, `orchestrator.running_tasks[operation_id]` — отмена через `task.cancel()` не подходит, нужен graceful stop). Предпочтительно: `orchestrator` держит `Dict[operation_id, Event]`, модуль получает operation_id из meta и запрашивает event у orchestrator через зависимость или колбэк.

### H.5 Реализация (пошагово в коде)

| Шаг | Действие | Содержимое |
|-----|----------|------------|
| H.5.1 | Добавить `ScreenRecordParams` | В `screen.py`, рядом с `ScreenCollectParams` |
| H.5.2 | Добавить метод `record` с декоратором `@exposed_tool` | name="record", params_model=ScreenRecordParams, presets=[{"id": "short", "params": {"duration_sec": 30}}, {"id": "long", "params": {"duration_sec": 300}}] |
| H.5.3 | Инициализация: создать temp_dir, проверить ffmpeg | В `__init__` или в начале `record` |
| H.5.4 | Захват кадров: цикл `for i in range(fps * duration_sec)` с `await asyncio.sleep(1/fps)` | Внутри record |
| H.5.5 | Вызов ffmpeg: subprocess с stdin для raw frames ИЛИ imageio + mss | См. примеры imageio-ffmpeg |
| H.5.6 | Проверка stop_event в цикле (если передан) | `if stop_event and stop_event.is_set(): break` |
| H.5.7 | Ограничение размера: каждые N кадров проверять `temp_path.stat().st_size` | При > 200*1024*1024 — break |
| H.5.8 | FFmpeg: `-movflags +faststart` для web-воспроизведения | В аргументах ffmpeg |
| H.5.9 | Формирование _artifacts с kind="screen_recording", mime="video/mp4" | Аналогично collect |

### H.6 Альтернативная архитектура (проще)

- Использовать **gif** вместо mp4 — `imageio.mimwrite(path, frames, fps=fps)` без ffmpeg. Но: gif большой и не подходит для 5 мин.
- Использовать **PyAV** или **opencv-python** для записи mp4 — больше зависимостей.
- Рекомендация: **mss + imageio-ffmpeg** или **mss + subprocess ffmpeg**.

### H.7 Передача stop_event в модуль

Текущий вызов в orchestrator:
```python
observations = await method(**params_to_use)
```

Модуль не получает `meta` или `stop_event`. Варианты:

1. **Расширить контракт вызова:** orchestrator передаёт в params скрытое поле `_stop_event` (и затем вычищает его перед передачей в method). Не очень чисто.
2. **Глобальный/contextvar:** `record_stop_events: Dict[str, Event]` в orchestrator, ключ — operation_id. Модуль импортирует функцию `get_stop_event(operation_id) -> Optional[Event]` из orchestrator или из отдельного модуля. При вызове record orchestrator кладёт event в словарь, модуль получает по meta.request_id.
3. **Через ui_bus обратно:** GUI шлёт событие `stop_recording`, в payload — operation_id. Orchestrator получает, устанавливает `stop_recording_events[operation_id].set()`. Модуль должен иметь доступ к этому event — через общий сервис `RecordingController.get_stop_event(operation_id)`.

**Предлагаемая схема:**
- Создать `core/recording_controller.py`: класс с `Dict[str, asyncio.Event]`, методы `register(operation_id)`, `get(operation_id)`, `signal_stop(operation_id)`.
- Orchestrator при вызове `screen.record` вызывает `recording_controller.register(operation_id)` перед вызовом, передаёт в params `_stop_event` (внутренний ключ) или модуль сам получает через `RecordingController.get(operation_id)`.
- GUI при STOP шлёт событие с operation_id; orchestrator обрабатывает и вызывает `recording_controller.signal_stop(operation_id)`.

---

## I) Минимальный набор тест-кейсов (напоминание)

1. Upload 1MB — успех  
2. Upload 50MB — успех, streaming  
3. Upload 200MB — успех  
4. Upload 201MB — 413  
5. Воспроизведение mp4 — перемотка  
6. TTL истёк — 404/410  
7. Download без токена — 401  
8. Download без прав — 403  
9. Обрыв сети — retry, partial  
10. Повторная отправка — идемпотентность  

11. **STOP-кнопка:** запись 60 сек, остановка на 15 сек — файл ~15 сек  
12. **Свернуть окно:** скриншот не содержит окно агента  
