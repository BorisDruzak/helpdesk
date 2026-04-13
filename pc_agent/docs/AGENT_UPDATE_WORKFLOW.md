# Agent Update Workflow (pc_agent)

Канонический workflow для изменений, которые попадают в распространяемый агент: launcher, `ws_agent`, `ui_bridge`, GUI, self-update, release-артефакты и rollout через сервер.

**Дата обновления:** 2026-04-13

---

## 1. Когда использовать этот playbook

Используйте этот сценарий, если задача затрагивает хотя бы одно из:

- `pc_agent/launcher/*`
- `pc_agent/ws_agent.py`
- `pc_agent/ui_bridge/*`
- `pc_agent/ui_gui/*`
- release/build scripts (`build_windows_release*.py`)
- server-side agent update flow (`server/agents/agent_builds_handlers.py`, `server/websocket/agent_handshake.py`, admin UI Agent Updates)

Если правка влияет на бинарь, который будет раздаваться агентам, она должна проходить именно по этому сценарию.

---

## 2. Инварианты production-схемы

- Агент распространяется и запускается через `launcher`, а не прямым запуском versioned `pc_agent.exe`.
- Обновление идёт через `pending_update.json` + exit code `42` + launcher apply/verify/rollback.
- Успешным обновление считается только после следующего handshake новой версии.
- Нельзя silently подменять содержимое релизного ZIP под тем же номером версии.
- Для rollout сначала делать canary на одном устройстве, затем bulk.
- Для ручного update/restart действия указывать `reason`, чтобы он попал в audit и diagnostics.

---

## 3. Канонический порядок работы

### 3.1 Анализ и код

1. Начать с:
   - `pc_agent/docs/SELF_UPDATE.md`
   - `server/docs/AGENT_UPDATES_API.md`
   - `pc_agent/docs/CODEMAP.md`
   - при UI-симптомах также `pc_agent/ui_bridge/*` и `pc_agent/ui_gui/*`
2. Внести правки в локальной копии `C:\Users\admin-2\CodexProjects\pc_client`.
3. Если изменился release/update flow, синхронно обновить docs, skill и CODEMAP.

### 3.2 Версионирование

Если меняется распространяемый бинарь агента или launcher:

1. Обновить `pc_agent/version.py`.
2. Не публиковать новый ZIP под старой версией, кроме аварийного overwrite по явному решению пользователя.
3. В notes/reason фиксировать, зачем вышла новая версия.

### 3.3 Локальные проверки

Минимум:

1. `python scripts/verify_workspace.py`
2. `python -m pytest pc_agent/tests/ -v --tb=short`

Если менялся server-side update flow или admin UI:

1. `python -m pytest server/tests/test_p0_workbench_update_contracts.py -v --tb=short`
2. `python -m pytest server/tests/test_admin_tech_api.py -v --tb=short`
3. browser check на `http://192.168.100.17:8666/admin`

Если полный `verify_workspace.py` падает из-за уже существующего чужого WIP вне этой задачи, это надо явно зафиксировать в отчёте. Для проверки своей области допустимо дополнительно прогнать `python scripts/verify_workspace.py --skip-docs-drift`.

### 3.4 Сборка release-артефакта

Windows quiet release:

```powershell
python pc_agent/build_windows_release_v2.py
```

Результат:

- launcher: `pc_agent/dist/launcher.exe`
- agent onedir: `pc_agent/dist/pc_agent/pc_agent.exe`
- release layout: `pc_agent/dist/release/windows_amd64/stable/<version>/install`
- update artifact: `pc_agent/dist/release/windows_amd64/stable/<version>/pc_agent-windows_amd64-<version>.zip`

### 3.5 Публикация на сервер

1. Убедиться, что Linux server поднят.
2. Загрузить новый build через admin UI или `POST /api/agent_builds/upload`.
3. Проверить `GET /api/agent_builds` / список билдов в admin UI.
4. Не использовать overwrite старой версии как обычный путь релиза.

### 3.6 Rollout и верификация

1. Выполнить single-device canary update через admin UI или `POST /api/devices/{device_id}/agent/update`.
   Для локальных Windows canary использовать именованный instance через `python scripts/manage_local_agent.py start <name> --launcher`; если у instance уже есть полный versioned install layout, скрипт должен сохранить текущую установленную версию и не досеивать новую сборку из репозитория.
2. Проверить diagnostics:
   - `recent_operations`
   - `timeline`
   - `problem_logs`
   - handshake-confirmed success/failure
3. Только после canary запускать bulk rollout.

---

## 4. Обязательные проверки перед rollout

- Build upload проходит без overwrite существующей версии.
- Launcher стартует новую версию и сохраняет layout `install_root/versions/<version>/`.
- Агент после update реально делает следующий handshake с новой версией.
- В diagnostics видны `operation_id`, timeline и итоговый статус.
- Если менялся GUI/`ui_bridge`, поздний SSE-подписчик не теряет последнее `connection_state`.

---

## 5. Где смотреть при проблемах

Локально на Windows:

- launcher log: `pc_agent/dist/launcher.log`
- agent log: `pc_agent/dist/data/logs/agent.log`
- identity: `pc_agent/dist/data/identity.json`
- update state:
  - `pc_agent/dist/data/updates/pending_update.json`
  - `pc_agent/dist/data/updates/update_history.json`
  - `pc_agent/dist/data/updates/last_failed_pending_update.json`

На сервере:

- `python scripts/manage_remote_stack.py logs server`
- admin UI Agent Updates diagnostics
- `GET /api/devices/{device_id}/agent/update_diagnostics`

---

## 6. Что считается анти-pattern

- Перезаписывать работающий `pc_agent.exe` in-place.
- Выпускать другой бинарь под тем же version string без явной аварийной причины.
- Считать `scheduled` подтверждением успешного обновления.
- Катить bulk rollout без canary.
- Проверять только серверные логи и игнорировать launcher/update history на устройстве.

---

## 7. Связанные документы

- [SELF_UPDATE.md](SELF_UPDATE.md)
- [CODEMAP.md](CODEMAP.md)
- [../../server/docs/AGENT_UPDATES_API.md](../../server/docs/AGENT_UPDATES_API.md)
- [../../server/docs/AGENT_UPDATES_ANALYSIS.md](../../server/docs/AGENT_UPDATES_ANALYSIS.md)
