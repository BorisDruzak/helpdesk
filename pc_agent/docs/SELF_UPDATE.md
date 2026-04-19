# Self-Update (remote update) v2 — pc_agent

PC Agent поддерживает удалённое обновление через команду Protocol V3 `update`.

**Модель v2:** агент запускается через **launcher**. Агент только скачивает артефакт и пишет `pending_update.json`, затем завершается с кодом 42. Launcher применяет обновление (распаковка, verify, переключение версии или rollback).

Для операционного сценария "что менять, как версионировать, что проверять и как катить rollout" используйте канонический playbook: [AGENT_UPDATE_WORKFLOW.md](AGENT_UPDATE_WORKFLOW.md).

Важно: server-side assigned rollout является source of truth и может указывать как на upgrade, так и на controlled rollback. Для агента это один и тот же self-update flow: если рекомендованная release-версия с сервера отличается от текущей, GUI должен показывать action-кнопку, а launcher после restart применяет запрошенный архив и переключает `current.json` на указанную версию.

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

1. Скачивает артефакт в `data_root/updates/downloads/build.<ext>` с проверкой sha256/size.
2. Пишет `data_root/updates/pending_update.json` (version, target, archive_type, artifact_path, received_at, operation_id, requested_by, requested_reason, sha256, size).
3. Отправляет command_result со статусом "scheduled".
4. Через короткую задержку выполняет **clean shutdown** и завершает процесс с **exit code 42** (`EXIT_UPDATE_PENDING`). Агент **не** запускает in-place updater и **не** меняет свои файлы.

## Что делает launcher

- Читает `install_root/current.json`, запускает `versions/<version>/.../<binary>` с env `PC_AGENT_DATA_DIR`, `PC_AGENT_INSTALL_ROOT`.
- При завершении дочернего процесса:
  - если **exit code 42** или существует **pending_update.json** — выполняет установку обновления (см. ниже);
  - иначе — перезапуск с backoff (tray-режим).
- Если только что переключённая версия несколько раз подряд падает сразу после старта, launcher пишет причину в `launcher.log`, сохраняет `last_failed_launch.json`, добавляет failure entry в `update_history.json` и откатывает `current.json` на `previous`.
- **Установка обновления** (модуль `launcher/installer.py`):
  - распаковка архива в `install_root/versions/_staging/<version>/` (защита от path traversal);
  - backup `storage.db` в `data_root/updates/db_backups/`;
  - **verify**: запуск новой версии с `--verify` (таймаут 60–90 с);
  - при успехе: атомарное переименование staging → `versions/<version>`, обновление `current.json`, запись в `update_history.json`, удаление `pending_update.json`;
  - при провале extract / verify / publish: восстановление БД при необходимости, запись ошибки в `update_history`, сохранение `last_failed_pending_update.json`, удаление `pending_update.json` и откат (current.json не меняется).

Важно: failed `pending_update.json` больше не ретраится бесконечно на каждом цикле launcher. После terminal failure требуется новый явный запрос на update с сервера.

## Режим агента --verify

Запуск с флагом `--verify`: без WebSocket и GUI; инициализация конфига и БД (миграции), пробная загрузка оркестратора. Exit 0 — версия рабочая, иначе — ненулевой код. Launcher использует это для принятия решения о переключении версии или rollback.

## Диагностика

- `data_root/updates/pending_update.json` — параметры ожидающего обновления.
- `data_root/updates/update_history.json` — история применённых/неудачных обновлений.
- `data_root/updates/last_failed_pending_update.json` — последний провалившийся pending payload и текст ошибки.
- `data_root/updates/last_failed_launch.json` — последний terminal startup crash новой версии после переключения launcher.
- `data_root/updates/db_backups/` — бэкапы БД перед verify.
- Устаревший in-place updater: `pc_agent/utils/agent_updater.py` (в v2 не вызывается).
- Если update "успешен" по логам агента, но GUI показывает `Сервер: подключение...`, проверьте локальный `ui_bridge`: поздний SSE-подписчик должен сразу получать последнее `connection_state`; см. `pc_agent/ui_bridge/event_bus.py`, `pc_agent/ui_bridge/api_server.py`.
- Runtime status GUI должен дополнительно показывать: `comparison`, `recommendation_source`, `assigned_rollout`, `pending_update_*`, `last_applied_update_*`, `last_failed_update_*`, чтобы разбирать rollout/update состояние без ручного чтения файлов.

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
