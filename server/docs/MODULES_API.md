# Modules API Contract

Документация API контрактов для управления модулями через HTTP и WebSocket команды.

## Архитектура

Модули устанавливаются через **HTTP download** механизм:
1. Модуль загружается на сервер через `POST /api/modules/upload`
2. Сервер сохраняет ZIP на диск и в БД (таблица `modules`)
3. При установке команда `install_module_package` содержит `download_url` вместо `package_b64`
4. Агент скачивает ZIP по HTTP, проверяет SHA256 и устанавливает

Серверное файловое хранилище модулей, артефактов и agent builds живёт вне Git-дерева, в `PC_CLIENT_SERVER_DATA_ROOT` (по умолчанию: Linux `~/.local/share/pcclient-server`, Windows `%LOCALAPPDATA%\PCClientServer\data`). При старте сервер один раз мигрирует данные из старых каталогов `server/uploads`, `server/data/modules_storage`, `server/data/agent_builds`, если новые директории ещё пусты.

### Развёртывание: SERVER_PUBLIC_BASE_URL

URL для скачивания модулей строится на сервере из `SERVER_PUBLIC_BASE_URL` (см. `server/config.py`). Текущий дефолт в коде: `http://192.168.100.17:{SERVER_PORT}`. **Если агент работает на другой машине**, этот URL должен быть доступен с хоста агента (IP или hostname сервера). В **production** обязательно задавать `SERVER_PUBLIC_BASE_URL` явно через env; дефолт считается только dev-safe. При установке модуля на удалённый агент без настройки вы получите ошибку вида `MODULE_DOWNLOAD_FAILED: Cannot connect to host ... [Неверный формат сетевого имени]`.

**Рекомендация:** в `server/.env` или при запуске задать:
```bash
SERVER_PUBLIC_BASE_URL=http://IP_ИЛИ_ИМЯ_СЕРВЕРА:8666
```
Например: `SERVER_PUBLIC_BASE_URL=http://192.168.100.17:8666`.

### Автоустановка модуля при run_tool

При вызове инструмента на агенте (run_tool, в т.ч. через `POST /api/admin/run_tool` или `POST /api/tools/run`) сервер:

1. Определяет, является ли инструмент модульным (формат `module_name.tool_name`, например `ping.ping`).
2. Проверяет наличие модуля на агенте по таблице `device_modules` (активные модули).
3. Если модуля на агенте нет — ищет модуль на сервере в реестре `modules` (берётся последняя по дате загрузки версия).
4. Если модуль есть на сервере — проверяет совместимость ОС устройства с `platforms` из manifest модуля; при несовместимости или неизвестной ОС возвращает ошибку.
5. Если всё ок — отправляет агенту команду `install_module_package` (через тот же механизм, что и ручная установка), ждёт успешного завершения (таймаут 90 с), затем выполняет запрошенный run_tool.

Исключение: builtin-модули агента (`system`, `screen`) не требуют server-side установки. Для `screen.collect` и `screen.record` сервер не должен пытаться скачивать ZIP с `/api/modules/.../download`, даже если в server registry есть старые записи о пакетах.

Если модуля нет на сервере, возвращается ошибка с кодом `MODULE_NOT_ON_SERVER`. Ошибки установки (таймаут, отказ агента) возвращаются с кодами `MODULE_INSTALL_TIMEOUT`, `MODULE_INSTALL_FAILED` и т.п.

Список модулей на сервере: реестр в таблице `modules` и API `GET /api/modules`.

## HTTP Endpoints

### POST /api/modules/upload

Загружает модуль на сервер (сохраняет ZIP на диск и в БД). Перед сохранением выполняется preflight (ZIP, manifest, entrypoint) и smoke-check в subprocess (загрузка модуля, register, list_tools). Невалидные пакеты не сохраняются (см. docs/PLAYBOOK_IMPLEMENTATION.md, этапы 2 и 2b).

**Request:** `multipart/form-data`
- `file`: ZIP файл модуля (обязательно, streaming read)
- `module_name`: Имя модуля (обязательно)
- `version`: Версия модуля (обязательно)
- `actor_role`: Роль актора (optional, default "admin")
- `overwrite`: Разрешить перезалив существующего (optional, "true"/"false", default "false")

**Response (200 OK):**
```json
{
  "status": "success",
  "module_name": "custom",
  "version": "1.0.0",
  "sha256": "a1b2c3d4e5f6...",
  "size": 12345,
  "download_path": "/api/modules/custom/1.0.0/download",
  "preflight_status": "passed"
}
```

**Response (400 Bad Request)** — ошибка валидации (preflight):
```json
{
  "status": "error",
  "error": "Module validation failed",
  "preflight_status": "failed",
  "preflight_errors": ["manifest.json: missing required field 'module_version'"],
  "module_name": "custom",
  "version": "1.0.0"
}
```

**Response (409 Conflict):**
```json
{
  "status": "error",
  "error": "Module already exists",
  "module_name": "custom",
  "version": "1.0.0"
}
```

### POST /api/modules/create

Создаёт модуль из «только кода функции»: подставляет код в единый шаблон (см. docs/ATOMIC_MODULES_ANALYSIS.md), собирает manifest.json и module.py, прогоняет preflight и smoke, сохраняет ZIP и запись в БД. Доступно из веб-формы и из API (установка через терминал без веб-панели).

**Request:** `application/json`
- `module_name`: Имя модуля (обязательно)
- `version`: Версия в формате X.Y.Z (обязательно)
- `tool_name`: Имя инструмента (обязательно)
- `description`: Описание инструмента (обязательно)
- `user_function_body`: Тело async-функции, возвращающей Dict (обязательно)
- `risk_level`: safe_readonly | safe_write | dangerous (optional, default "safe_readonly")
- `overwrite`: Перезаписать при совпадении имени и версии (optional, default false)

**Response (200 OK):** как у POST /api/modules/upload (status, module_name, version, sha256, size, download_path, preflight_status).

**Response (400):** ошибка валидации или smoke — в теле могут быть `preflight_errors`.

**Response (409):** модуль с такой парой (module_name, version) уже существует и overwrite не передан.

### POST /api/modules/bulk_install

Массовая установка модуля на несколько устройств. Для каждого device_id команда install_module_package ставится в outbox: онлайн-агенты получают команду сразу (на агенте сначала выполняется smoke-проверка, затем установка), офлайн — при подключении из очереди.

Исключение: builtin-модули агента (`system`, `screen`) через этот endpoint как пакет не ставятся. Сервер возвращает `202 Accepted` с `builtin=true`, пустым `operations` и списком `skipped`, потому что такие модули уже входят в сборку агента.

**Request:** `application/json`
- `module_name`: Имя модуля (обязательно)
- `version`: Версия модуля (обязательно)
- `device_ids`: Массив UUID устройств (обязательно, непустой)
- `replace_if_exists`: При конфликте SHA заменять (optional, default false)

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operations": [
    { "device_id": "uuid-1", "operation_id": "uuid-op-1" },
    { "device_id": "uuid-2", "operation_id": "uuid-op-2" }
  ]
}
```

**Response (404):** модуль не найден в реестре.

### GET /api/modules/{module_name}/{version}/download

Скачивает ZIP модуля (streaming).

**Headers:**
- `ETag`: SHA256 хеш модуля
- `Content-Type`: application/zip
- `Content-Disposition`: attachment; filename="{module_name}-{version}.zip"
- `Cache-Control`: no-store

**Response (200 OK):** Streaming ZIP file

**Response (404):** Module not found

### GET /api/modules/ping

Лёгкий endpoint для preflight-проверки доступности module API префикса
из агента перед установкой/загрузкой модулей.

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

### GET /api/modules

Список загруженных модулей.

**Query params:**
- `module_name`: Фильтр по имени модуля (optional)

**Response (200 OK):**
```json
{
  "modules": [
    {
      "module_name": "custom",
      "version": "1.0.0",
      "sha256": "a1b2c3d4e5f6...",
      "size": 12345,
      "created_at": "2026-01-10T12:00:00Z",
      "uploaded_by": "admin"
    }
  ]
}
```

### DELETE /api/modules/{module_name}/{version}

Удаляет модуль с сервера: запись из БД и файл ZIP с диска. Требует аутентификации и роль `admin`.

**Response (200 OK):**
```json
{
  "status": "ok",
  "module_name": "custom",
  "version": "1.0.0"
}
```

**Response (401):** Authentication required

**Response (403):** Only admin can delete modules from server

**Response (404):** Module not found

### GET /api/devices/{device_id}/modules

Список модулей на устройстве.

**Query params:**
- `active_only`: Только активные модули (optional, default false)

**Response (200 OK):**
```json
{
  "device_id": "device-uuid",
  "modules": [
    {
      "module_name": "custom",
      "version": "1.0.0",
      "installed": true,
      "active": true,
      "installed_at": "2026-01-10T12:00:00Z",
      "activated_at": "2026-01-10T12:01:00Z",
      "state": "active",
      "last_error_code": null,
      "last_error_message": null
    }
  ]
}
```

### POST /api/devices/{device_id}/modules/install

Устанавливает модуль на устройство (enqueue install_module_package через device_outbox).

Исключение: builtin-модули агента (`system`, `screen`) не ставятся как server-managed ZIP. Для них endpoint возвращает `202 Accepted` c `builtin=true`, а агент не получает `install_module_package`.

**Request:**
```json
{
  "module_name": "custom",
  "version": "1.0.0",
  "actor_role": "admin",
  "replace_if_exists": false
}
```

- **replace_if_exists** (опционально): если `true`, при конфликте SHA (та же версия уже установлена с другим хешем) сервер передаёт агенту флаг замены — старый каталог удаляется и пакет устанавливается заново. По умолчанию `false` (поведение как раньше).

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

**Response (404):** Module not found

### POST /api/devices/{device_id}/modules/activate

Активирует модуль на устройстве.

**Request:**
```json
{
  "module_name": "custom",
  "version": "1.0.0",
  "actor_role": "admin"
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### POST /api/devices/{device_id}/modules/deactivate

Деактивирует модуль на устройстве.

**Request:**
```json
{
  "module_name": "custom",
  "actor_role": "admin"
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### POST /api/devices/{device_id}/modules/sync

Синхронизирует состояние модулей на устройстве (enqueue list_installed_modules и list_tools).

**Request:**
```json
{
  "actor_role": "admin"
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_ids": ["uuid-1", "uuid-2"]
}
```

### POST /api/devices/{device_id}/modules/remove_version

Удаляет версию модуля на устройстве.

**Request:**
```json
{
  "module_name": "custom",
  "version": "1.0.0",
  "actor_role": "admin",
  "force": false
}
```

- **force** (опционально): если `true`, проверка наличия модуля в device_modules не выполняется — команда remove_module_version сразу ставится агенту в outbox. Позволяет удалить модуль на агенте, даже если записи в inventory нет (например, после сбоя или без предварительного sync).

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### POST /api/devices/{device_id}/modules/remove

Удаляет модуль (все версии) на устройстве.

**Request:**
```json
{
  "module_name": "custom",
  "actor_role": "admin",
  "force": false
}
```

- **force** (опционально): если `true`, проверка наличия модуля в device_modules не выполняется — команда remove_module сразу ставится агенту в outbox.

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

## WebSocket команды (install_module_package)

Все команды возвращают `operation_id` для отслеживания статуса.

### install_module_package

**Новый формат (HTTP download):**
```json
{
  "command": "install_module_package",
  "params": {
    "module_name": "custom",
    "module_version": "1.0.0",
    "download_url": "http://server:8666/api/modules/custom/1.0.0/download",
    "sha256": "a1b2c3d4e5f6...",
    "size": 12345,
    "package_b64": null
  }
}
```

**Legacy формат (base64 fallback):**
```json
{
  "command": "install_module_package",
  "params": {
    "module_name": "custom",
    "module_version": "1.0.0",
    "package_b64": "base64-encoded-zip...",
    "sha256": "a1b2c3d4e5f6..."
  }
}
```

**Response (command_result):**
```json
{
  "status": "success",
  "data": {
    "observations": {
      "module_name": "custom",
      "module_version": "1.0.0",
      "message": "Module installed successfully"
    }
  }
}
```

### activate_module

**Request:**
```json
{
  "module_name": "custom",
  "version": "1.0.0"
}
```

**Response:**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### deactivate_module

**Request:**
```json
{
  "module_name": "custom"
}
```

**Response:**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### rollback_module

**Request:**
```json
{
  "module_name": "custom"
}
```

**Response:**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### remove_module_version

**Request:**
```json
{
  "module_name": "custom",
  "version": "1.0.0"
}
```

**Response:**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### remove_module

**Request:**
```json
{
  "module_name": "custom"
}
```

**Response:**
```json
{
  "status": "accepted",
  "operation_id": "uuid-here"
}
```

### activate_module

**Request:**
```json
{
  "command": "activate_module",
  "params": {
    "module_name": "custom",
    "version": "1.0.0"
  }
}
```

**Response (command_result):**
```json
{
  "status": "success",
  "data": {
    "observations": {
      "module_name": "custom",
      "version": "1.0.0",
      "message": "Module activated"
    }
  }
}
```

### deactivate_module

**Request:**
```json
{
  "command": "deactivate_module",
  "params": {
    "module_name": "custom"
  }
}
```

**Response (command_result):**
```json
{
  "status": "success",
  "data": {
    "observations": {
      "module_name": "custom",
      "message": "Module deactivated"
    }
  }
}
```

### rollback_module

**Request:**
```json
{
  "command": "rollback_module",
  "params": {
    "module_name": "custom"
  }
}
```

**Response (command_result):**
```json
{
  "status": "success",
  "data": {
    "observations": {
      "module_name": "custom",
      "previous_version": "1.0.0",
      "current_version": "0.9.0",
      "message": "Module rolled back"
    }
  }
}
```

### list_installed_modules

**Request:**
```json
{
  "command": "list_installed_modules",
  "params": {}
}
```

**Response (command_result):**
```json
{
  "status": "success",
  "data": {
    "observations": {
      "modules": [
        {
          "name": "custom",
          "active": "1.0.0",
          "versions": ["1.0.0", "1.0.1"]
        }
      ]
    }
  }
}
```

## Device Registry (Actual State)

Сервер отслеживает установленные модули в таблице `device_modules` (actual state):

- `device_id` — устройство
- `module_name`, `version` — модуль
- `installed` — установлен ли модуль
- `active` — активен ли модуль
- `state` — состояние (`installing|installed|activating|active|failed|missing|removed`)
- `installed_at`, `activated_at` — временные метки
- `last_seen_at` — время последнего подтверждения реального наличия от агента (миграция 037)
- `source` — источник обновления: `handshake|command_result|event` (миграция 037)
- `last_error_code`, `last_error_message` — ошибки установки/активации

Обновляется автоматически при получении `command_result` для `install_module_package`, `activate_module`, `deactivate_module`, а также при `module_state_changed` event от агента.

### Удаление модуля (remove): только при подтверждении от агента

Сервер обновляет `device_modules` (помечает модуль как удалённый, `state=removed`) **только при успешном** `command_result` для `remove_module` / `remove_module_version`:

1. **Успех (status=success)** — агент реально удалил файлы (например, `shutil.rmtree` выполнен). Тогда сервер вызывает `mark_removed` / `mark_module_removed`, делает commit, и ставит в очередь `list_installed_modules` и `list_tools`, чтобы снимок toolset в PostgreSQL обновился без этого модуля.
2. **Ошибка (REMOVE_FAILED, "Module not found")** — модуль на агенте уже отсутствовал. Сервер **не** обновляет `device_modules`: нет подтверждения, что файлы удалены; интерфейс не меняется до следующего успешного remove или синхронизации.

В GUI модуль исчезает только потому, что в PostgreSQL по устройству его больше нет в актуальном списке (запись в `device_modules` с `state=removed` отфильтровывается в API).

## Desired State

Таблица `device_desired_modules` хранит желаемое состояние модулей (server-first источник истины):

- `device_id`, `module_name` — UNIQUE ключ
- `desired_version` — целевая версия (NULL для state=absent)
- `desired_sha256` — целевой SHA256
- `state` — `installed | absent`
- `reason` — причина: `manual | run_tool | policy | reconcile`
- `updated_at`, `updated_by` — аудит

Записывается при install (`state=installed`) и remove (`state=absent`) операциях.

## Reconcile Engine

Сервис `server/modules/reconcile.py` сравнивает desired vs actual и генерирует команды агентам.

Запускается:
1. **Периодически** — каждые 5 минут через `module_reconcile_scheduler`.
2. **Немедленно** — после `module_state_changed` event от агента.
3. **Вручную** — `POST /api/devices/{device_id}/modules/reconcile`.

Алгоритм:
- desired=installed + actual не active → enqueue `install_module_package`
- desired=absent + actual active → enqueue `remove_module`

## API Desired vs Actual Diff

**GET** `/api/devices/{device_id}/modules/desired_diff`

Возвращает diff желаемого и фактического состояния. Поле `diff_status`:
- `ok` — всё совпадает
- `missing` — desired=installed, но actual не active
- `version_mismatch` — версии отличаются
- `not_removed` — desired=absent, но actual ещё active

## Toolset Snapshots

Сервер сохраняет snapshots toolset устройств в таблице `device_toolset_snapshots`:

- `device_id` — устройство
- `toolset_hash` — SHA256 hash toolset (первые 16 символов)
- `toolset_json` — JSON с инструментами
- `tool_count` — количество инструментов
- `captured_at` — время создания snapshot
- UNIQUE constraint: `(device_id, toolset_hash)`

Обновляется автоматически при получении `command_result` для `list_tools`.

См. [MODULES_DRIFT_AND_SNAPSHOTS.md](MODULES_DRIFT_AND_SNAPSHOTS.md) для деталей.



## Update 2026-03-11

### Manifest v2 compat
- New packages must use `manifest_version: 2`.
- Server normalizes legacy manifests without `manifest_version` into a v2-compatible runtime shape.
- Server persistence now stores:
  - `manifest_json`: normalized manifest contract
  - `validation_json`: preflight/smoke/compat result
  - `manifest_summary`: temporary derived compatibility field

### Updated endpoints
- `POST /api/modules/create`
  - Generates manifest v2.
  - Accepts `method`, `platforms`, `params_schema`, `presets`, `capabilities`, `metadata`, `requirements`, `optional_requirements`, `min_agent_version`.
  - Returns `manifest_version`, `validation_status`, `warnings`, `tools_count`, `preflight_status`.
- `POST /api/modules/upload`
  - Validates manifest v2 or normalizes legacy manifest to compat.
  - Returns structured `preflight_errors`, `warnings`, `validation_json`.
- `GET /api/modules`
  - Returns `manifest_version`, `legacy_manifest`, `validation_status`, `platforms`, `tools_count`, `has_full_metadata`.
- `GET /api/modules/{module_name}/{version}`
  - Returns full `manifest_json`, `validation_json`, `tools`, `requirements`, `optional_requirements`.
- `POST /api/devices/{device_id}/modules/install`
  - Uses `manifest_json.platforms` for compatibility checks.
  - Returns structured `error_code` and `hint` on validation failures.
- `GET /api/devices/{device_id}/modules`
  - Adds `source`, `manifest_version`, `legacy_manifest`.
- `GET /api/devices/{device_id}/toolset`
  - Preserves snapshot contract and enriches tools with `origin` when known.
- `GET /api/devices/{device_id}/modules/debug`
  - Returns `device_modules`, `desired_modules`, `toolset_snapshot`, `recent_operations`, `mismatches`.

## Update 2026-03-11: Update and rollback behavior

- `POST /api/rollback_module` now updates server-side desired state on success. The desired version is moved to the rolled-back version with `reason=manual_rollback`.
- Successful rollback responses may include `data.observations.active_version` in addition to `active_path`.
- Modules UI is expected to treat rollback as a first-class action alongside install, activate, deactivate, remove-version and remove-module.
- Device debug views should no longer require a manual `/modules/sync` after rollback to converge actual and desired module state.
## Runtime Convergence Notes

- Device-scoped module operations now enqueue a follow-up `list_installed_modules` + `list_tools` refresh after the mutating command.
- This applies to install, bulk install, activate, deactivate, rollback, remove version, and remove module flows.
- Server intent: `actual state` and `toolset snapshot` should converge automatically without a separate manual sync step.
- Removing the last known version through `POST /api/devices/{device_id}/modules/remove_version` now also updates desired state to `absent` with reason `manual_remove`.
