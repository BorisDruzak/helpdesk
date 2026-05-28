# API артефактов (скриншоты, запись экрана)

Документ описывает контракты загрузки (upload) и скачивания (download) артефактов, а также формат дескриптора артефакта. Файлы передаются через HTTP; бинарные данные не передаются по WebSocket.

## Дескриптор артефакта (Artifact Descriptor)

Используется в ответах команд (command_result), в ленте событий тикета и при отображении скриншотов/видео.

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `artifact_id` | string (UUID) | да (после upload) | Уникальный идентификатор артефакта на сервере |
| `name` | string | да | Имя файла (оригинальное или сгенерированное) |
| `mime` | string | нет | MIME-тип (например `image/png`, `video/mp4`) |
| `size_bytes` | integer | нет | Размер в байтах |
| `sha256` | string | нет | SHA256 хеш в hex (64 символа) |
| `kind` | string | нет | Семантический тип: `screenshot`, `screen_recording`, `log`, и т.д. |
| `url` | string | нет | URL для скачивания (например `/api/artifacts/{artifact_id}/download`) |
| `expires_at` | string (ISO 8601) | нет | Время истечения TTL (если задано) |

Пример (в payload события или в `command_result.data.artifacts`):

```json
{
  "artifact_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "screenshot_20260204.png",
  "mime": "image/png",
  "size_bytes": 1048576,
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "kind": "screenshot",
  "url": "/api/artifacts/a1b2c3d4-e5f6-7890-abcd-ef1234567890/download",
  "expires_at": "2026-02-05T12:00:00Z"
}
```

---

## Upload: POST /api/upload

**Аутентификация:** обязательна (Bearer token агента или UI).  
**Content-Type:** `multipart/form-data`.

### Поля запроса (multipart)

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `file` | file | да | Файл (бинарные данные) |
| `ticket_id` | string (UUID) | нет | Идентификатор тикета (для привязки артефакта к тикету) |
| `operation_id` | string (UUID) | нет | Идентификатор операции (run_tool) |
| `kind` | string | нет | Семантический тип: `screenshot`, `screen_recording`, и т.д. |

**device_id** не передаётся в теле запроса — берётся из токена (AuthContext) при аутентификации агента.

### Ограничения

- Максимальный размер файла: **200 MB** (209715200 байт).
- При превышении — ответ **413 Payload Too Large**.

### Обработка на сервере

- Потоковая запись на диск (без загрузки всего файла в память).
- Вычисление SHA256 «на лету» во время сохранения.
- Сохранение метаданных в таблицу `artifacts` (artifact_id, storage_path, original_name, mime_type, size_bytes, sha256, kind, device_id, ticket_id, operation_id, expires_at, created_at).

### Успешный ответ (200 OK)

```json
{
  "status": "success",
  "artifact_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "a1b2c3d4-e5f6-7890-abcd-ef1234567890.png",
  "url": "/api/artifacts/a1b2c3d4-e5f6-7890-abcd-ef1234567890/download",
  "size": 1048576,
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "mime_type": "image/png",
  "kind": "screenshot"
}
```

### Ошибки

| Код | Описание |
|-----|----------|
| 400 | Нет поля `file` или пустой запрос |
| 401 | Нет или невалидный токен |
| 413 | Размер файла превышает 200 MB |
| 500 | Внутренняя ошибка сервера |

---

## Download: GET /api/artifacts/{artifact_id}/download

**Реализация:** `server/uploads/handlers.py` — `handle_artifact_download`; проверка прав — `server/app/services/artifact_service.py` (`ArtifactService.get_artifact_for_download`).

**Аутентификация:** обязательна (Bearer token).  
Public-ticket session tokens are accepted on this route and are scoped by `AuthContext.ticket_scope`; they still pass through `ArtifactService` ticket/artifact visibility checks.
Доступ к артефакту проверяется по привязке к тикету: пользователь (UI token) может скачать артефакт, привязанный к тикету (тикет должен существовать); агент (agent token) — только к своим артефактам (по device_id). Артефакты без ticket_id в БД доступны только агенту-владельцу, **кроме случая fallback** (см. ниже).

### Query-параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `ticket_id` | string (UUID) | Опционально. Для UI-токена: если у артефакта в БД нет `ticket_id` (старые загрузки), сервер разрешает доступ, если переданный тикет существует и в событиях тикета есть `tool_call_result` с этим `artifact_id`. Используется для отображения скриншотов/видео в `ticket.html`. |

Без передачи `ticket_id` артефакты с пустым `artifact.ticket_id` при запросе с UI-токеном возвращают **403 Forbidden**.

### Заголовки ответа

- **Content-Type:** соответствует `mime_type` артефакта.
- **Content-Length:** размер файла.
- **Accept-Ranges:** bytes (для видео поддерживается Range запрос).
- **Content-Disposition:** `attachment; filename="<ascii fallback>"; filename*=UTF-8''<encoded original>`. Unicode names must be exposed through `filename*`; the plain `filename` value is only a safe ASCII fallback.

### Range (206 Partial Content)

Для видео поддерживается заголовок `Range: bytes=0-1023`. Сервер возвращает **206 Partial Content** с фрагментом файла. Используется для перемотки в плеере.

### Ошибки

| Код | Описание |
|-----|----------|
| 401 | Нет или невалидный токен |
| 403 | Нет прав на доступ к артефакту |
| 404 / 410 | Артефакт не найден или TTL истёк (expires_at < NOW()) |

---

## MIME-типы

Поддерживаемые типы для скриншотов и записи экрана:

| Расширение | MIME |
|------------|------|
| .png | image/png |
| .jpg, .jpeg | image/jpeg |
| .mp4 | video/mp4 |

Сервер может хранить и отдавать и другие типы (см. ArtifactManager.MIME_MAP на агенте и валидацию на сервере).
