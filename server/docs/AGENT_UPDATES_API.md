# Remote Agent Update (pc_agent) — API

Механизм удалённого обновления PC Agent через сервер (v2: onedir + launcher, zip/tar.gz).

- Сборка агента (ZIP или tar.gz) загружается на сервер по HTTP (multipart).
- Агент скачивает артефакт по защищённому HTTP download (Bearer token), пишет `pending_update.json` и завершается с кодом 42.
- Launcher на устройстве применяет обновление (verify, переключение версии или rollback).

Бинарные данные **не** передаются по WebSocket.

## Upload build

`POST /api/agent_builds/upload`

**Auth:** обязателен, только `admin`.

**Content-Type:** `multipart/form-data`.

Поля:
- `file` — архив (обязательно): ZIP или tar.gz
- `target` — например `windows_amd64`, `linux_alt_x86_64` (обязательно)
- `channel` — `stable` (по умолчанию), `beta`, `dev`
- `version` — строка версии (обязательно)
- **`archive_type`** — **обязательно**: `zip` или `tar.gz`
- `notes` — текст (опционально)
- `overwrite` — `true|false` (по умолчанию `false`)

Файл сохраняется как `{target}/{channel}/{version}/agent.<ext>`. В БД записываются `artifact_filename`, `archive_type`, `mime_type`.

Успех (200):
```json
{
  "status": "success",
  "target": "windows_amd64",
  "channel": "stable",
  "version": "3.1.0",
  "sha256": "…",
  "size": 123456,
  "download_path": "/api/agent_builds/windows_amd64/stable/3.1.0/download"
}
```

## List builds

`GET /api/agent_builds?target=...&channel=...&limit=...`

**Auth:** обязателен.

Ответ:

```json
{
  "status": "ok",
  "builds": [
    {
      "target": "windows_amd64",
      "channel": "stable",
      "version": "3.1.0",
      "artifact_filename": "pc_agent-windows_amd64-3.1.0.zip",
      "archive_type": "zip",
      "mime_type": "application/zip",
      "sha256": "…",
      "size": 123456,
      "notes": null,
      "created_at": "2026-04-13T08:30:00+00:00",
      "download_path": "/api/agent_builds/windows_amd64/stable/3.1.0/download"
    }
  ],
  "count": 1
}
```

## Download build

`GET /api/agent_builds/{target}/{channel}/{version}/download`

**Auth:** обязателен (agent token или UI token).

Заголовки ответа:
- `Content-Type` — из поля билда `mime_type` (application/zip или application/gzip)
- `Content-Disposition` — `attachment; filename="<artifact_filename>"`
- `ETag: "{sha256}"`
- `Cache-Control: no-store`

Скачивания логируются в `agent_build_download_audit`.

## Trigger update on device

`POST /api/devices/{device_id}/agent/update`

**Auth:** обязателен. Policy: `system_write` (admin/system).

**Ограничение:** агент должен быть **online** (активное WS-соединение).

Body:
```json
{
  "target": "windows_amd64",
  "channel": "stable",
  "version": "3.1.0",
  "restart_delay_sec": 2,
  "reason": "manual canary rollout after smoke"
}
```

- `reason` — опциональная человекочитаемая причина запуска; попадает в audit/timeline и в `pending_update.json`.

Если `version` не задан — берётся **latest** build для `(target, channel)`.

Ответ (202):
```json
{
  "status": "accepted",
  "operation_id": "…",
  "build": { "target": "…", "channel": "…", "version": "…" }
}
```

## WS command: `update`

Сервер ставит в очередь команду `update` с параметрами:
```json
{
  "target": "windows_amd64",
  "channel": "stable",
  "version": "3.1.0",
  "download_url": "http(s)://SERVER/api/agent_builds/.../download",
  "sha256": "…",
  "size": 123456,
  "archive_type": "zip",
  "artifact_name": "pc_agent-windows_amd64-3.1.0.zip",
  "restart_delay_sec": 2,
  "reason": "manual canary rollout after smoke"
}
```

Агент по этим параметрам скачивает артефакт, проверяет sha256, пишет `pending_update.json` и завершается с кодом 42. Дальнейшим управлением занимается launcher.

## Массовое обновление

`POST /api/agents/update_bulk`

**Auth:** обязателен. Policy: `system_write` (admin/system).

**Body:**
```json
{
  "device_ids": ["uuid1", "uuid2"],
  "channel": "stable",
  "version": "3.1.0",
  "restart_delay_sec": 2,
  "reason": "bulk rollout after verified canary"
}
```

- `device_ids`: список `device_id` или `null` — при `null` обновление запускается для **всех онлайн-агентов**.
- `channel`: канал (по умолчанию `stable`).
- `version`: версия билда; если не указана — берётся последняя для каждого target.
- Target для каждого устройства подбирается **автоматически** по `os_type` из метаданных агента (Windows → `windows_amd64`, Linux → `linux_alt_x86_64` и т.д.).

**Ответ (200):**
```json
{
  "status": "ok",
  "operations": [
    { "device_id": "...", "operation_id": "...", "build": { "target": "...", "channel": "...", "version": "..." } }
  ],
  "errors": [
    { "device_id": "...", "error": "Unknown os_type: ..." }
  ]
}
```

## Подтверждение обновления (handshake)

После успешного применения обновления агент при переподключении может передать в **handshake** (в `payload`):

- `applied_update_version` — версия, на которую обновился агент;
- `last_update_operation_id` — ID операции обновления.

Сервер сохраняет эти поля в `device_metadata` устройства и отдаёт в `GET /api/devices/{device_id}`. По ним можно убедиться, что агент реально перешёл на новую версию.

Если launcher не смог применить обновление и перезапустил старую версию, агент передаёт в следующий `handshake`:

- `failed_update_version`
- `failed_update_operation_id`
- `failed_update_reason`
- `failed_update_at`
- `failed_update_message`

Сервер использует эти поля, чтобы перевести `agent_update` в `failed` без ожидания watchdog timeout, и сохраняет их в `device_metadata`.

## Диагностика обновления по устройству

`GET /api/devices/{device_id}/agent/update_diagnostics`

**Auth:** `admin`, `support`, `auditor`.

Возвращает расширенную диагностическую сводку для admin UI:

- `device` — online/offline, last_seen/last_handshake, stale;
- `update_summary` — последняя успешная/неуспешная информация, включая launcher-side failure report;
- `recent_operations` — последние `agent_update` операции с target/channel/version/reason/status;
- `timeline` — runtime-audit события `update_*` и timeout-сигналы;
- `problem_logs` — последние warning/error записи из tech log buffer по `device_id`/hostname.

## Канонический workflow

Для production-сценария "как выпускать новую версию агента, какие проверки обязательны, когда bump-ать version и как делать canary/bulk rollout" используйте:

- [../../pc_agent/docs/AGENT_UPDATE_WORKFLOW.md](../../pc_agent/docs/AGENT_UPDATE_WORKFLOW.md)
- [../../pc_agent/docs/SELF_UPDATE.md](../../pc_agent/docs/SELF_UPDATE.md)
