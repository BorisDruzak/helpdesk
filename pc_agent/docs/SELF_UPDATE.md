# Self-Update (remote update) v2 — pc_agent

PC Agent поддерживает удалённое обновление через команду Protocol V3 `update`.

**Модель v2:** агент запускается через **launcher**. Агент только скачивает артефакт и пишет `pending_update.json`, затем завершается с кодом 42. Launcher применяет обновление (распаковка, verify, переключение версии или rollback).

Для операционного сценария "что менять, как версионировать, что проверять и как катить rollout" используйте канонический playbook: [AGENT_UPDATE_WORKFLOW.md](AGENT_UPDATE_WORKFLOW.md).

Важно: server-side assigned rollout является source of truth и может указывать как на upgrade, так и на controlled rollback. Для агента это один и тот же self-update flow: если рекомендованная release-версия с сервера отличается от текущей, агент после успешного startup handshake один раз автоматически запрашивает recommended build, GUI показывает action/state для ручного контроля, а launcher после restart применяет запрошенный архив и переключает `current.json` на указанную версию.

Startup auto-update не обходит серверную авторизацию: `ws_agent.py` пропускает запуск, если уже есть `pending_update.json`, получает verdict через update recommendation endpoint и вызывает обычный `POST /api/devices/{device_id}/agent/update` с reason `agent_startup_auto_update`. Сервер по-прежнему разрешает agent-role self-update только для собственного `device_id` и только для текущего recommended build. После постановки controlled shutdown агент отдаёт через локальный status `update_request_state=applying`, чтобы GUI успел показать пользователю, что идёт обновление и последует автоматический перезапуск.

Server handshake can also enqueue the same `update` command for older installed agents that do not yet contain agent-side startup auto-update code. That fallback runs only for a newer assigned rollout, skips active update operations, skips the same version after a launcher-reported failure, and uses reason `agent_handshake_auto_update`.

2026-06-10 Stage 3 consent GUI changes are ordinary application code inside the distributed agent artifact. They do not alter the self-update command, launcher staging, rollback or assigned rollout protocol.

## Layout (per-user)

- **install_root** (по умолчанию: Windows `%LOCALAPPDATA%\PCClientAgent\install`, Linux `~/.local/opt/pcclient-agent`):
  - `launcher` / `launcher.exe`
  - `current.json` — `{"version":"3.1.0","previous":"3.0.0"}`
  - `versions/<ver>/` — onedir-сборка версии (бинарь + зависимости)
- **data_root** (по умолчанию: Windows `%LOCALAPPDATA%\PCClientAgent\data`, Linux `~/.local/share/pcclient-agent`):
  - `storage.db`, `identity.json`, `settings.yaml`
  - `modules_store/`, `logs/`
  - `updates/downloads/` — скачанные артефакты
  - `updates/pending_update.json` — запрос на обновление (агент пишет, launcher читает)
  - `updates/update_history.json`, `updates/db_backups/`

## Команда `update`

Параметры (передаются сервером в `params`):
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
  "restart_delay_sec": 2
}
```

Требования:
- `download_url`, `sha256`, `version` обязательны
- `archive_type`: `zip` или `tar.gz`
- выполнять может server-authorized privileged actor: `admin`, `system` или `agent` для собственного self-update, уже разрешённого сервером по recommended build
- для совместимости со старыми release сервер может прислать WS-команду с `actor_role=admin`, а исходного инициатора положить в `requested_by`; агент должен использовать `requested_by` для `pending_update.json` и диагностики

## Что делает агент (при команде update)

1. Скачивает артефакт в `data_root/updates/downloads/build-<version>-<operation_id>.<ext>` с проверкой sha256/size.
2. Если `data_root/updates/pending_update.json` уже существует, не перетирает его новым update: exact same `operation_id` считается idempotent retry, любая другая операция должна завершаться ошибкой. Исключение: pending с версией не новее текущего `AGENT_VERSION` архивируется в `last_stale_pending_update.json` и не блокирует новый recommended build.
3. Пишет `data_root/updates/pending_update.json` (version, target, archive_type, artifact_path, received_at, operation_id, requested_by, requested_reason, sha256, size).
4. Отправляет command_result со статусом "scheduled" только после успешной постановки controlled shutdown-for-update.
5. Через короткую задержку выполняет **clean shutdown** и завершает процесс с **exit code 42** (`EXIT_UPDATE_PENDING`). Агент **не** запускает in-place updater и **не** меняет свои файлы.

## Что делает launcher

- Читает `install_root/current.json`, запускает `versions/<version>/.../<binary>` с env `PC_AGENT_DATA_DIR`, `PC_AGENT_INSTALL_ROOT`.
- При завершении дочернего процесса:
  - если **exit code 42** или существует **pending_update.json** — выполняет установку обновления (см. ниже);
  - иначе — перезапуск с backoff (tray-режим).
- Если только что переключённая версия несколько раз подряд падает сразу после старта, launcher пишет причину в `launcher.log`, сохраняет `last_failed_launch.json`, добавляет failure entry в `update_history.json` и откатывает `current.json` на `previous`.
- **Установка обновления** (модуль `launcher/installer.py`):
  - распаковка архива в `install_root/versions/_staging/<version>/` (защита от path traversal, запрет archive links, восстановление POSIX mode bits для `tar.gz`);
  - backup `storage.db` в `data_root/updates/db_backups/`;
  - **verify**: запуск новой версии с `--verify` (таймаут 60–90 с) c возвратом stdout/stderr в diagnostics при ошибке;
  - при успехе: safe publish staging → `versions/<version>` через backup/restore существующей версии, затем обновление `current.json`, запись в `update_history.json`, удаление `pending_update.json`;
  - при провале extract / verify / publish: восстановление БД при необходимости, запись ошибки в `update_history`, сохранение `last_failed_pending_update.json`, удаление `pending_update.json` и откат (current.json не меняется).

Важно: failed `pending_update.json` больше не ретраится бесконечно на каждом цикле launcher. После terminal failure требуется новый явный запрос на update с сервера.

## Режим агента --verify

Запуск с флагом `--verify`: без WebSocket и GUI; инициализация конфига и БД (миграции), пробная загрузка оркестратора. Exit 0 — версия рабочая, иначе — ненулевой код. Launcher использует это для принятия решения о переключении версии или rollback.

## Диагностика

- `data_root/updates/pending_update.json` — параметры ожидающего обновления.
- `data_root/updates/update_history.json` — история применённых/неудачных обновлений.
- `data_root/updates/last_failed_pending_update.json` — последний провалившийся pending payload и текст ошибки.
- `data_root/updates/last_stale_pending_update.json` — последний устаревший pending payload, который не был новее текущего `AGENT_VERSION`.
- `data_root/updates/last_failed_launch.json` — последний terminal startup crash новой версии после переключения launcher.
- `data_root/logs/action_trace.jsonl` — полный update trail: `agent.update.request` (GUI/runtime), `agent.update.command` (orchestrator), `agent.update.shutdown` (runtime exit), `agent.update.apply` (launcher apply/verify/publish).
- `data_root/updates/db_backups/` — бэкапы БД перед verify.
- Устаревший in-place updater: `pc_agent/utils/agent_updater.py` (в v2 не вызывается).
- Если update "успешен" по логам агента, но GUI показывает `Сервер: подключение...`, проверьте локальный `ui_bridge`: поздний SSE-подписчик должен сразу получать последнее `connection_state`; см. `pc_agent/ui_bridge/event_bus.py`, `pc_agent/ui_bridge/api_server.py`.
- Runtime status GUI должен дополнительно показывать: `comparison`, `recommendation_source`, `assigned_rollout`, `pending_update_*`, `update_request_state`, `update_request_version`, `update_request_operation_id`, `last_applied_update_*`, `last_failed_update_*`, чтобы разбирать rollout/update состояние без ручного чтения файлов. Состояния `pending_restart`, `applying` и `restarting` должны отображаться как видимый progress/restart UX, а не как внезапное закрытие окна.

## Распространение (exe / rpm) и готовность к обновлению

Код обновления готов к использованию при распространении агента в виде **exe** (Windows) и **rpm** или бинарного архива (Linux).

### Требования к layout

- **Launcher** должен запускаться первым; он читает `install_root/current.json` и запускает `versions/<version>/<binary>`.
- **install_root** должен содержать: `current.json`, `versions/<ver>/` с бинарём агента (Windows: `pc_agent.exe`, Linux: `pc_agent`) и зависимостями (onedir PyInstaller).
- **data_root** задаётся через env `PC_AGENT_DATA_DIR` (или `--data-dir` у launcher); в нём создаются `updates/downloads/`, `updates/pending_update.json`, `updates/db_backups/`, `updates/update_history.json`.
- Путь в `pending_update.json` поле `artifact_path` записывается **абсолютным** — launcher может быть запущен из любого каталога.

### Форматы артефактов

- **Windows (exe):** сервер отдаёт сборку в `archive_type: "zip"`. В архиве — onedir или onefile с именем `pc_agent.exe` (см. `launcher/installer._find_agent_binary`: ищет `pc_agent.exe` в Windows).
- **Linux (rpm / tar.gz):** сервер отдаёт сборку в `archive_type: "tar.gz"` или `"tgz"`. В архиве — каталог с бинарём `pc_agent` (без расширения). Installer распаковывает в `versions/_staging/<version>/`, затем verify и переключение версии.

### Проверка перед распространением

1. **Сборка:** PyInstaller spec-файлы: `pyinstaller_agent_linux.spec`, `pyinstaller_launcher_linux.spec` (Linux); для Windows — соответствующие spec для launcher и агента (например `pyinstaller_launcher_win_release.spec`).
2. **Режим --verify:** после распаковки launcher запускает новый бинарник с `--verify`; агент должен поддерживать этот флаг (миграции БД, без WS/GUI). Реализация: `ws_agent.py` аргумент `--verify`, функция `_run_verify_mode`.
3. **Exit code 42:** агент при запланированном обновлении завершается с кодом 42 (`EXIT_UPDATE_PENDING` в `version.py`); launcher по этому коду применяет обновление и перезапускает агент.
4. **Env при запуске:** launcher передаёт дочернему процессу `PC_AGENT_DATA_DIR` и `PC_AGENT_INSTALL_ROOT`; без них данные и текущая версия будут разрешаться по умолчанию (см. `core/runtime_paths.py`).

Итог: цепочка «сервер шлёт update → агент скачивает и выходит 42 → launcher применяет обновление и перезапускает» не зависит от способа доставки (exe, rpm, zip, tar.gz); достаточно соблюдать layout install_root/data_root и передавать переменные окружения.
