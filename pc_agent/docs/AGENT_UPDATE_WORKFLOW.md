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

### 2.2 2026-05-04 release note

- `3.1.29` is the Windows stable agent release for follow-up requester GUI fixes after `3.1.28`: required diagnostic-consent hint, clearer confirmation card, diagnostics/deadline/assignment summaries, and Russian system event text. Publish it as a new build/upload/rollout target; do not overwrite existing artifacts.
- `3.1.30` is the next Windows agent release for the GUI taskbar-window fix: the recording STOP overlay uses a `Qt.Tool` window and no longer creates extra `pc_agent` Taskbar/Alt-Tab entries. Publish it as a new build/upload/rollout target; do not overwrite `3.1.29` artifacts.
- `3.1.31` is the Windows stable agent release for requester timeline projection support: the GUI uses server-provided `requester_timeline_*` fields and keeps the local fallback requester-safe. Publish it as a new build/upload/rollout target; do not overwrite `3.1.30` artifacts.
- `3.1.32` is the Windows stable agent release for the requester diagnostics timeline wording fix: diagnostic result cards show only `Выполнена диагностика` without resource-specific filler text. Publish it as a new build/upload/rollout target; do not overwrite `3.1.31` artifacts.
- `3.1.33` is the Windows stable agent release for Remote Assist runtime fixes: `remote_assist.request` no longer fails on the local datetime binding, and the Qt consent dialog is retained/topmost while waiting for user approval. Publish it as a new build/upload/rollout target; do not overwrite `3.1.32` artifacts.
- `3.1.34` is the Windows stable agent release for the Remote Assist WebRTC hotfix: PyInstaller now packages `aiortc`/ICE/media dependencies, and the GUI reports WebRTC startup failures back to the backend instead of leaving the operator viewer waiting forever. Publish it as a new build/upload/rollout target; do not overwrite `3.1.33` artifacts.
- `3.1.35` is the Windows stable agent release for Remote Assist interactive-control testing: Windows mouse/keyboard injection uses `SendInput` instead of legacy `mouse_event`/`keybd_event`, and Linux control uses the platform `pynput` backend when policy enables `interactive_control`. Publish it as a new build/upload/rollout target; do not overwrite `3.1.34` artifacts.
- `3.1.36` is the Windows stable agent release for Remote Assist connection hardening: viewer and agent fail stalled WebRTC negotiations cleanly, Maria Agent no longer says the specialist sees the screen before ICE connects, and failed negotiation stops capture work instead of leaving CPU usage high. Publish it as a new build/upload/rollout target; do not overwrite `3.1.35` artifacts.
- `3.1.37` is the Windows stable agent release for idle CPU/WMI reduction: Windows fingerprint collection avoids default PowerShell/WMI calls, WMI baseboard lookup is opt-in through `PC_AGENT_ENABLE_WMI_FINGERPRINT=1`, and GUI idle update status checks reuse cache longer. Publish it as a new build/upload/rollout target; do not overwrite `3.1.36` artifacts.
- `3.1.38` is the Windows stable agent release for launcher disk retention and focused-window CPU reduction: after a successful update the launcher keeps only the current and previous version directories, retains fewer downloaded ZIP artifacts, and GUI soft shadows are opt-in through `PC_AGENT_ENABLE_GUI_SHADOWS=1`. Publish it as a new build/upload/rollout target; do not overwrite `3.1.37` artifacts.
- `3.1.39` is the Windows stable agent release for deeper focused-window CPU reduction on Windows/RDP/Proxmox graphics stacks: frameless resize cursor updates are deduplicated and unchanged ticket detail polls skip UI rebuilds before repaint. Publish it as a new build/upload/rollout target; do not overwrite `3.1.38` artifacts.
- `3.1.40` is the Windows stable agent release for field GUI CPU diagnostics: the agent logs `[gui-profiler]` samples with process CPU, Qt event counters, hot receivers, focus/active widgets and top thread CPU deltas. Disable after diagnosis with `PC_AGENT_GUI_PROFILER=0`. Publish it as a new build/upload/rollout target; do not overwrite `3.1.39` artifacts.
- `3.1.41` is the Windows stable agent release for remote GUI CPU log retrieval: `diag.logs.collect` app preset includes the agent runtime logs directory so `[gui-profiler]` samples can be collected as an artifact. Publish it as a new build/upload/rollout target; do not overwrite `3.1.40` artifacts.
- `3.1.42` is the Windows stable agent release for enabling `diag_logs` as a core built-in module so `diag.logs.collect` is present in the runtime registry on upgraded agents. Publish it as a new build/upload/rollout target; do not overwrite `3.1.41` artifacts.
- `3.1.43` is the Windows stable agent release for fixing focused-window GUI CPU spikes caused by synchronous `action_trace.jsonl` recounts on every GUI API trace record. Publish it as a new build/upload/rollout target; do not overwrite `3.1.42` artifacts.

### 2.1 2026-04-22 hardening notes

- `pending_update.json` is a single-flight latch. If one update is already pending, a new update command must not overwrite it. The only allowed duplicate is the exact same `operation_id`, which should be treated as idempotent.
- Downloaded artifacts are stored under unique names derived from version and `operation_id`, not a shared `build.zip` / `build.tar.gz` slot.
- Agent may report `"scheduled"` only after shutdown-for-update is actually armed. A shutdown scheduling failure must return a failed command result and clean up the just-written pending marker/artifact.
- Launcher publish must keep the current version recoverable until staging is fully promoted. Safe publish means backup/restore around the final move, not delete-then-move.
- Installer hardening also includes path-traversal-safe extraction, rejecting archive links, restoring POSIX execute bits for `tar.gz`, and surfacing verify stdout/stderr in failure diagnostics.
- Crash-loop rollback is required for both launcher entrypoints: `launcher_main.py` and `launcher_portable_main.py` must revert `current.json` to `previous` after repeated immediate startup failures of the newly switched version.
- GUI update UX should expose the request lifecycle explicitly: `requesting`, `requested`, `pending_restart`, then handshake-confirmed terminal success/failure.

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
2. Загрузить новый build через React admin UI `/app/admin/agent-updates` или legacy `POST /api/agent_builds/upload` (React использует web-session alias `/api/web/admin/agent-builds/upload`).
3. Проверить `GET /api/web/admin/agent-builds` / список билдов в `/app/admin/agent-updates`.
4. Назначить target rollout policy через `/app/admin/agent-updates` или `PATCH /api/web/admin/agent-updates/rollout-policy` (legacy token route: `PATCH /api/agent_updates/rollout_policy`).
4. Не использовать overwrite старой версии как обычный путь релиза.

### 3.6 Rollout и верификация

1. Выполнить single-device canary update через admin UI или `POST /api/devices/{device_id}/agent/update`.
   Для локальных Windows canary использовать именованный instance через `python scripts/manage_local_agent.py start <name> --launcher`; если у instance уже есть полный versioned install layout, скрипт должен сохранить текущую установленную версию и не досеивать новую сборку из репозитория.
2. Проверить diagnostics:
   - `recent_operations`
   - `timeline`
   - `problem_logs`
   - `data/logs/action_trace.jsonl` или tech drilldown `include_agent_actions=1` для stages `agent.update.request`, `agent.update.command`, `agent.update.shutdown`, `agent.update.apply`
   - handshake-confirmed success/failure
3. Только после canary запускать bulk rollout.

---

## 4. Обязательные проверки перед rollout

- Build upload проходит без overwrite существующей версии.
- Launcher стартует новую версию и сохраняет layout `install_root/versions/<version>/`.
- При немедленном crash-loop новой версии launcher явно логирует ошибку и откатывает `current.json` на `previous`, а не уходит в бесконечный silent restart.
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
  - `pc_agent/dist/data/updates/last_failed_launch.json`

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
