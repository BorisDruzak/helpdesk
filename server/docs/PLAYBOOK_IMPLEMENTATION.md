# Внедрение плейбуков и расширение модульной системы (V3)

Единый документ по внедрению Playbook Engine и расширению модульной системы поверх ws_ticket_v3.

**Версия:** 1.5  
**Дата:** 2026-02-21  
**Статус:** Этапы 1–6 выполнены; этапы 7–9 выполнены; этапы 10–12 в плане/документированы.

---

## 1. Резюме и стратегия

- **Стратегия:** эволюционно поверх текущей реализации, без ломки ws_ticket_v3.
- **Протокол:** оставляем как есть; только backward-compatible расширения.
- **Отложенные playbook:** через offline enqueue в `device_outbox` (реализовано: `require_online=False` в `enqueue_command_async`).
- **Агент:** строгий нейминг `module.tool` включён (Этап 3); целевые метаданные (platforms, timeout_sec, idempotent) — в следующих итерациях.
- **Сервер:** Playbook Engine (Этап 4 MVP) реализован: последовательные шаги, operation_id на шаг, продвижение по command_result.

---

## 2. Текущее состояние (после этапа 1)

| Компонент | Статус |
|-----------|--------|
| `enqueue_command_async(require_online=False)` | Реализовано: запись в device_outbox без проверки online. |
| SLA для `kind=command` (list_tools и др.) | Увеличены: delivery 60s, execution 120s, accepted_timeout 120s (`config.OPERATION_SLA_OVERRIDES["command"]`). |
| device_outbox repair | Реализовано: housekeeping раз в 10 мин помечает `status='sent'` без операции как failed (ORPHAN_SENT). Репозиторий: `get_sent_without_operation`, `repair_sent_without_operation`. |
| Контракт consent | Единый: агент может слать `status=error` + `error.code=CONSENT_REQUIRED`; парсер нормализует в `status=consent_required` (`command_result_parser.normalize_command_result_payload`). |
| Playbook-таблицы | Миграция 033: playbook, playbook_version, playbook_step, playbook_run, playbook_step_run. Модели в `app/db/models.py`. |
| Short-name на агенте | Отключён: только формат `module.tool`; при коротком имени — INVALID_TOOL_FORMAT. |
| Preflight при upload модуля | Реализован: ZIP, manifest, entrypoint; smoke в subprocess (2b); ответ `preflight_status`/`preflight_errors`; невалидные пакеты не сохраняются. |
| Playbook Engine (движок) | MVP: start_run, advance_after_terminal, POST /api/playbooks/runs; шаги через run_tool + device_outbox. |

---

## 3. Этап 1 (стабилизация) — выполнен

### 3.1 SLA для list_tools / kind=command

- **Файл:** `server/config.py`
- **Изменение:** в `OPERATION_SLA_OVERRIDES` добавлен `"command"` с `delivery_timeout=60`, `execution_timeout=120`, `accepted_timeout=120`.
- **Цель:** уменьшить доминирование list_tools в timeout-метрике и убрать ложный timeout в статусе accepted.

### 3.2 Cleanup/repair device_outbox (sent без operation_id)

- **Файлы:** `server/app/repos/device_outbox_repo.py`, `server/server.py`
- **Изменения:**
  - В `DeviceOutboxRepo`: методы `get_sent_without_operation(limit)` и `repair_sent_without_operation(limit)` — поиск записей `status='sent'` без соответствующей операции и пометка их как `failed` с `error_code='ORPHAN_SENT'`.
  - В `housekeeping_cleanup_task`: раз в 10 минут вызывается repair; при необходимости выполняется `commit`.
- **Цель:** устранить «зависшие» sent-записи без операции.

### 3.3 Единый контракт consent

- **Файл:** `server/websocket/command_result_parser.py`
- **Изменение:** если в payload приходит `status="error"` и `error.code="CONSENT_REQUIRED"`, нормализованный результат получает `status="consent_required"`. Обработка на сервере остаётся в одной ветке (mark_waiting_consent и т.д.).
- **Цель:** агент может слать либо `status=consent_required`, либо `status=error` + `code=CONSENT_REQUIRED` — оба варианта обрабатываются одинаково.

---

## 4. Этап 2 (preflight для модулей) — выполнен

### 4.1 Preflight-валидатор

- **Файл:** `server/utils/module_preflight.py`
- **Функция:** `preflight_module_zip(zip_bytes)` → `(ok, errors, manifest_summary)`.
- **Проверки:**
  - целостность ZIP (открытие без BadZipFile);
  - количество записей в архиве не превышает лимит (защита от zip bomb);
  - отсутствие path traversal в именах записей;
  - наличие `manifest.json` (в корне или в подпапке), валидный JSON;
  - обязательные поля manifest: `module_name`, `module_version` (непустые строки);
  - формат entrypoint: либо `module:function`, либо имя файла; если файл — проверка наличия в архиве.
- При успехе возвращается `manifest_summary` (module_name, module_version, entrypoint) для записи в БД.

### 4.2 Интеграция в upload

- **Файл:** `server/modules/handlers.py`, `handle_upload_module`.
- После сбора чанков файла вызывается preflight до сохранения на диск и записи в БД.
- При неудаче preflight: ответ **400** с `status: "error"`, `error: "Module validation failed"`, `preflight_status: "failed"`, `preflight_errors: [...]`. Модуль не сохраняется и не публикуется для install.
- При успехе: сохранение на диск и создание/обновление записи в `modules` с `manifest_summary`; ответ 200 с `preflight_status: "passed"`.

### 4.3 Smoke preflight (фаза 2b) — выполнен

- **Скрипт:** `pc_agent/scripts/smoke_check_module.py` — запускается в subprocess (не в процессе web-handler).
- **Вход:** `--dir <распакованная директория>` (корень модуля с manifest.json).
- **Действия:** загрузка модуля через `DynamicModuleLoader(data_root=...)` (без get_config), `registry.register(instance)`, `registry.get_tools_flat()`; при успехе выход 0 и JSON `{"ok": true, "tools_count": N}`.
- **Сервер:** после успешного preflight (ZIP + manifest) распаковывает zip во временную директорию, вызывает скрипт с `PYTHONPATH=<project_root>`, таймаут 60 с. При ненулевом коде выхода или таймауте — ответ 400 с `preflight_errors` (например «Smoke check failed: ...»). Модуль не сохраняется.
- **Требование:** из каталога сервера должен быть доступен `project_root/pc_agent/scripts/smoke_check_module.py` (типично сервер и агент в одном репозитории).

---

## 5. Этап 3 (контракт атомарных команд) — выполнен

### 5.1 Именование: только module.tool

- **list_tools:** в ответе у каждого инструмента поле `tool` всегда в формате `module.tool` (например `ping_check.ping_host`). Короткое имя без модуля не возвращается.
- **run_tool:** принимается только полное имя `module.tool`. Если передано короткое имя (строка без точки), агент возвращает ошибку:
  - **code:** `INVALID_TOOL_FORMAT`
  - **message:** «Используйте формат "module.tool" (например ping_check.ping_host). Короткое имя не поддерживается.»

### 5.2 Изменения в коде агента

- **pc_agent/core/registry.py:** в `get_tools_flat()` всегда `unique_tool_name = f"{module_name}.{tool_name}"`. В `get_tool(tool_name)` если в `tool_name` нет точки — сразу `return None`.
- **pc_agent/core/orchestrator.py:** в обработчике `run_tool` при отсутствии точки в `tool` — немедленный `fail(code="INVALID_TOOL_FORMAT", ...)`; разрешение только по полному имени через `registry.get_tool(tool)`.

### 5.3 Метаданные и каталог

- Текущие метаданные в spec (risk_level, metadata.requires_consent, scopes, allow_roles) сохранены; значения по умолчанию в реестре — как раньше.
- Целевые поля (platforms, timeout_sec, idempotent) и каталог по domain/OS — в следующих итерациях (расширение этапа 3 или этап 8).

### 5.4 Документация агента

- **pc_agent/docs/TOOLS_CONTRACT.md** — контракт list_tools/run_tool, коды ошибок, целевые метаданные.

---

## 6. Этап 4 (Playbook MVP) — выполнен

### 6.1 Компоненты

- **Репозиторий:** `app/repos/playbook_repo.py` — PlaybookRepo: get_version_with_steps, create_run, create_step_run, get_step_run_by_operation_id, update_step_run_terminal, finish_run.
- **Движок:** `app/services/playbook_engine.py` — start_run (создаёт run, первый шаг, operation, enqueue run_tool с require_online=False), advance_after_terminal (по operation_id обновляет step_run, при успехе или continue_on_error переходит к следующему шагу или завершает run).
- **API:** POST `/api/playbooks/runs` — тело: `playbook_version_id`, `device_id` [, `trigger_type`, `context_json` ]; ответ 202: `{ "playbook_run_id", "status": "running" }`. Обработчик: `playbook_handlers.handle_start_playbook_run`.
- **Хук:** в `websocket/agent_command_result.py` после mark_succeeded и после mark_failed вызывается `advance_after_terminal(session, state, operation_id, "succeeded"|"failed", payload)`; при привязке operation_id к playbook_step_run выполняется продвижение (следующий шаг или завершение run).

### 6.2 Поведение

- Шаги выполняются последовательно по `order_no`. Каждый шаг — одна операция run_tool с отдельным operation_id.
- При terminal статусе операции (succeeded/failed) ищется playbook_step_run по operation_id; step_run обновляется (status, output_json/error_json, finished_at). При `continue_on_error=False` и failed run завершается с ошибкой; иначе берётся следующий шаг: создаётся operation, step_run, команда enqueue с require_online=False.
- Параметры шага: `params_template_json` используется как есть (MVP без подстановки переменных).
- Таймаут/retry на уровне шага (поля в БД) в MVP не обрабатываются — в следующих итерациях.

### 6.3 Требования к данным

- Для запуска нужны: playbook (key, name), playbook_version (status draft или published), playbook_step с полем tool в формате `module.tool` и при необходимости params_template_json. Создание playbook/version/step — через БД или отдельный API (в плане).

---

## 7. Модель данных и миграции (Playbook)

### 7.1 Таблицы (миграция 033)

- **playbook** — id, key, name, domain, owner, archived  
- **playbook_version** — id, playbook_id, version, manifest_json, status, created_at, published_at  
- **playbook_step** — id, playbook_version_id, step_key, order_no, type, tool, params_template_json, if_expr, timeout_sec, retry_policy_json, continue_on_error, parallel_group  
- **playbook_run** — id, playbook_version_id, device_id, status, scheduled_at, started_at, finished_at, trigger_type, context_json, error_code, error_message  
- **playbook_step_run** — id, playbook_run_id, playbook_step_id, attempt, status, operation_id, started_at, finished_at, input_json, output_json, error_json, trace_id  

### 7.2 Применение миграции 033

**Вариант A — Alembic (из каталога server, с DATABASE_URL из .env):**

```bash
cd /var/chat_bot/pc_client/server
./venv/bin/python -c "
from dotenv import load_dotenv
load_dotenv()
import os, subprocess
env = {**os.environ, 'PYTHONPATH': os.getcwd()}
subprocess.run(['./venv/bin/alembic', 'upgrade', 'head'], env=env, cwd=os.getcwd())
"
```

**Вариант B — ручной SQL (пользователь с правами на запись; MCP Postgres read-only):**

Выполнить скрипт: `server/docs/migrations/033_playbook_tables.sql`

---

## 8. Изменения API (реализованные и целевые)

### 8.1 Реализовано

- **enqueue_command_async:** параметр `require_online: bool = True`. При `require_online=False` команда только пишется в device_outbox (для Playbook/deferred execution).
- **Upload модуля (POST /api/modules/upload):** перед сохранением выполняется preflight и smoke; при ошибке — 400 с `preflight_status: "failed"`, `preflight_errors: [...]`; при успехе — `preflight_status: "passed"`, в БД сохраняется `manifest_summary`.
- **Агент list_tools / run_tool:** только формат `module.tool`; при коротком имени в run_tool — ошибка `INVALID_TOOL_FORMAT` (см. pc_agent/docs/TOOLS_CONTRACT.md).
- **Playbook runs:** POST `/api/playbooks/runs` — тело `playbook_version_id`, `device_id` [, `trigger_type`, `context_json` ]; ответ 202 `{ "playbook_run_id", "status": "running" }`. Продвижение шагов по факту command_result (succeeded/failed).

### 8.2 Целевые (дальнейшие этапы)

- **Метаданные:** обязательные поля platforms, timeout_sec, idempotent; каталог по domain/OS.
- **Handshake:** capability-флаги (например cmd.remove_module_version) для pre-dispatch.

---

## 9. План этапов 2–12 (кратко)

| Этап | Содержание | Статус |
|------|------------|--------|
| **2** | Preflight: ZIP, manifest, entrypoint; smoke в sandbox (2b). | Выполнен |
| **3** | Контракт атомарных команд: только module.tool, INVALID_TOOL_FORMAT при коротком имени. | Выполнен |
| **4** | Playbook MVP: последовательные steps, operation_id на step, продвижение по command_result, templates (params как есть). | Выполнен |
| **5** | Hardening MVP: таймаут шага → terminal (advance_after_terminal при timed_out), command_name в operations, install_module идемпотент по SHA, timeout_override_sec. | Выполнен |
| **6** | Deferred Playbook Scheduler: pending + scheduled_at, фоновый планировщик, idempotency_key. | Выполнен |
| **7** | Семантика шагов: if/retry/timeout/params-template. | Выполнен |
| **8** | Parallel шаги (parallel_group, join). | Выполнен |
| **9** | Capability Gate и совместимость агентов. | Выполнен |
| **10** | Drift/Inventory: builtin vs managed. | В плане |
| **11** | Масштаб каталога атомарных команд (100–150). | Подготовка (контракт, без команд) |
| **12** | Наблюдаемость, SLO, rollout (метрики, флаги). | Документировано |

---

## 10. Этап 5 (Hardening MVP) — выполнен

### 10.1 Таймауты playbook-step и terminal-логика

- **operation_watchdog:** после успешного `mark_timed_out` вызывается `advance_after_terminal(session, state, operation_id, "timed_out", payload)` (если передан `app` через `set_app(app)`). Таким образом run плейбука не зависает при таймауте шага: step_run помечается failed, run завершается или переходит к следующему шагу по `continue_on_error`.
- **playbook_engine:** терминальные статусы операции считаются `succeeded | failed | timed_out | canceled`; для step_run статус `success` только при `succeeded`, иначе `failed` (с сохранением error_json, в т.ч. code TIMEOUT).

### 10.2 Поля operations (миграция 034)

- **command_name** (VARCHAR(64), nullable): для операций `kind=command` (list_tools, list_installed_modules и др.) хранится имя команды; метрики по командам не теряются при `tool_name=NULL`.
- **timeout_override_sec** (INTEGER, nullable): переопределение таймаута исполнения для шага playbook; при расчёте deadline для статуса `running` используется это значение, если задано.
- **playbook_run_id** (BIGINT, FK → playbook_run.id, ON DELETE SET NULL): связь операции с запуском плейбука для наблюдаемости.

При создании операции из playbook_engine передаются `timeout_override_sec=step.timeout_sec` и `playbook_run_id=run.id`. При `enqueue_command_async` для команд (не run_tool) передаётся `command_name=command`.

### 10.3 install_module_package идемпотент по SHA (агент)

- **module_manager.install_zip_bytes:** при установке в целевую директорию записывается файл `.sha256` с хешем архива. Если целевой путь уже существует и есть `.sha256`: при совпадении SHA возвращается успех без переустановки (no-op); при другом SHA выбрасывается `ValueError` с текстом `INSTALL_CONFLICT_SHA`.
- **orchestrator._handle_install_module_package:** при перехвате `ValueError` с `INSTALL_CONFLICT_SHA` возвращается `fail(code="INSTALL_CONFLICT_SHA", ...)`. Повторная установка того же пакета (имя+версия+SHA) стабильно даёт success/no-op.

### 10.4 Критерии готовности этапа 5

- Нет зависающих playbook_run после timeout шага (watchdog вызывает advance_after_terminal).
- Метрика list_tools читается по `command_name` (operations.command_name).
- Повторная установка того же SHA стабильно success/no-op; при том же имя+версия и другом SHA — INSTALL_CONFLICT_SHA.

---

## 10.5 Этап 6 (Deferred Playbook Scheduler) — выполнен

### Логика

- **POST /api/playbooks/runs:** добавлены поля `scheduled_at` (UTC ISO), `idempotency_key` (optional), `dry_run` (optional). Если `scheduled_at` не задан — запуск сразу (как раньше). Если `scheduled_at` в будущем — создаётся run со статусом `pending`, первый шаг не ставится; планировщик поднимет run в срок.
- **PlaybookScheduler:** фоновый цикл (интервал из `config.PLAYBOOK_SCHEDULER_INTERVAL`, по умолчанию 3 сек). Выбирает due runs: `status=pending` и `scheduled_at <= now()`, до 100 за раз, `FOR UPDATE SKIP LOCKED`. Для каждого run проверяет лимит активных run на устройство (`PLAYBOOK_MAX_ACTIVE_RUNS_PER_DEVICE`); переводит run в `running`, ставит первый шаг в outbox (`start_first_step_for_run`). На offline-устройстве шаги остаются в outbox и доставляются при reconnect.
- **Idempotency:** при повторном POST с тем же `idempotency_key` возвращается 200 и существующий run (без создания дубликата). В БД добавлено поле `playbook_run.idempotency_key` (unique).

### Конфиг

- `PLAYBOOK_SCHEDULER_INTERVAL` (по умолчанию 3).
- `PLAYBOOK_MAX_ACTIVE_RUNS_PER_DEVICE` (по умолчанию 10).

### Миграция 035

- `playbook_run.idempotency_key` (VARCHAR(128), unique, nullable).
- Индекс `ix_playbook_run_status_scheduled_at` (status, scheduled_at) для выборки due runs.

### Критерии готовности этапа 6

- Run с будущим `scheduled_at` не стартует раньше времени.
- В срок run автоматически переводится в running и первый шаг ставится в outbox.
- На offline-устройстве шаги остаются в outbox и доставляются при reconnect.
- Повторный POST с тем же `idempotency_key` возвращает 200 и тот же run.

---

## 10.6 Этапы 7–9 (семантика шагов, parallel, capability gate) — выполнены

Подробно: **`PLAYBOOK_STAGES_7_12.md`**.

### Этап 7

- **if_expr**: безопасный evaluator (`app/utils/playbook_step_eval.py`), только `context` и `prev_steps`; при false — step_run со статусом `skipped`.
- **params_template_json**: подстановка `{{ context.* }}`, `{{ steps.step_key.output.* }}`.
- **retry_policy_json**: `max_attempts`, `retry_on_codes`; при failed и разрешённом retry — новый step_run с attempt+1 и повторная постановка в очередь.
- **timeout_sec**: передаётся в `operations.timeout_override_sec`.

### Этап 8

- **parallel_group**: шаги с одинаковым значением образуют группу; группа выполняется параллельно; переход к следующей группе после терминала всех шагов группы.
- Конфиг: `PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN` (по умолчанию 10).

### Этап 9

- **Capability Gate**: перед enqueue проверка `check_tool_available(session, device_id, tool_name)` по toolset snapshot; при отсутствии tool или несовместимости платформы — step_run `failed` с `UNSUPPORTED_CAPABILITY`/`TOOL_UNAVAILABLE` без отправки команды агенту.

---

## 11. Тест-кейсы и приёмочные сценарии

- list_tools перестаёт доминировать в timeout-метрике (SLA для command).
- Этап 5: timeout шага playbook → run переходит в terminal (failed или следующий шаг), не зависает; operations.command_name заполняется для list_tools; install_module тот же SHA → no-op, другой SHA → INSTALL_CONFLICT_SHA.
- Записи device_outbox `sent` без операции помечаются ORPHAN_SENT в рамках housekeeping.
- Consent: и `status=consent_required`, и `status=error` + `code=CONSENT_REQUIRED` ведут к mark_waiting_consent.
- install_module того же SHA → success/no-op (агент — позже).
- Upload невалидного ZIP → не публикуется (после preflight).
- run_tool только module.tool: при коротком имени — INVALID_TOOL_FORMAT (этап 3 выполнен).
- Playbook: POST /api/playbooks/runs создаёт run, первый шаг enqueue в outbox; при приходе command_result — продвижение на следующий шаг или завершение run (этап 4). На offline устройстве steps остаются в outbox до появления агента.
- Остальные сценарии (parallel, retry, capability gate, drift UI) — по плану этапов.

---

## 12. Связанные миграции

- **033** — playbook, playbook_version, playbook_step, playbook_run, playbook_step_run.
- **034** — operations: command_name, timeout_override_sec, playbook_run_id (см. `docs/migrations/034_operations_playbook_hardening.sql` и `app/db/migrations/versions/20260221_1000_034_*`).
- **035** — playbook_run: idempotency_key, индекс (status, scheduled_at) (см. `docs/migrations/035_playbook_run_idempotency_scheduler.sql` и `app/db/migrations/versions/20260221_1100_035_*`).

---

## 13. Assumptions и defaults

- Протокол ws_ticket_v3 сохраняем; breaking changes не делаем.
- Playbook Engine — только на сервере; агент — исполнитель атомарных команд.
- По умолчанию для playbook enqueue: **require_online=False**.
- Целевой naming: только **module.tool**.
- Read-only аудит БД: **pc_client_ro** (в среде без psql — psycopg).

---

## 14. Связанные документы

- `PROTOCOL_V3.md` — протокол WebSocket.
- `COMMAND_RESULT_LIFECYCLE.md` — жизненный цикл команд и операций.
- `MODULES_API.md`, `MODULES_DRIFT_AND_SNAPSHOTS.md` — модули и дрифт.
- `TOOL_CALL_STARTED_INVARIANT.md` — инварианты tool_call_started.
- `pc_agent/docs/MODULES.md`, `pc_agent/docs/PROTOCOL_V3.md` — агент.
- `pc_agent/docs/TOOLS_CONTRACT.md` — контракт list_tools/run_tool (module.tool, коды ошибок).
- `PLAYBOOK_API.md` — API POST /api/playbooks/runs (Этап 4).
- **`PLAYBOOK_STAGES_7_12.md`** — этапы 7–12: семантика шагов, parallel, capability gate, drift, каталог, наблюдаемость.

Старый развёрнутый план (до объединения): см. историю `PLAYBOOK_ENGINE_DESIGN.md` или этот файл как единственный актуальный источник по внедрению плейбуков.
