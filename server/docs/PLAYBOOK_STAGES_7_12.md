# Playbook Engine — этапы 7–12 (семантика шагов, parallel, capability, drift, каталог, наблюдаемость)

**Версия:** 1.0  
**Дата:** 2026-02-21  

Документ описывает реализацию и контракты этапов 7–12 плана внедрения модульной системы и Playbook Engine.

---

## Этап 7. Семантика шагов (if/retry/timeout/params-template)

### Реализовано

- **if_expr** — безопасный evaluator без exec: только `context` и `prev_steps` в namespace. Пустое выражение → шаг выполняется; при ошибке парсинга/оценки → шаг пропускается (step_run со статусом `skipped`).
- **params_template_json** — подстановка плейсхолдеров `{{ context.key }}`, `{{ steps.step_key.output.field }}` из контекста run и выходов предыдущих шагов. Модуль: `app/utils/playbook_step_eval.py` (`resolve_params_template`).
- **retry_policy_json** — структура: `max_attempts`, `backoff_ms` (опционально), `retry_on_codes` (список кодов; пустой = retry при любом коде). При `failed` и разрешённом retry создаётся новый step_run с `attempt+1` и команда ставится в очередь снова.
- **timeout_sec** — передаётся в `operations.timeout_override_sec` при создании операции; управляет таймаутом шага на уровне playbook.

### Критерии готовности

- Шаги условно пропускаются по if_expr.
- Retry работает по policy (max_attempts, retry_on_codes).
- Timeout шага управляется из playbook (timeout_sec → operations.timeout_override_sec).

### Файлы

- `app/utils/playbook_step_eval.py` — оценка if_expr, подстановка params.
- `app/repos/playbook_repo.py` — `get_prev_steps_for_run`, `create_step_run_skipped`.
- `app/services/playbook_engine.py` — использование в start_run, advance_after_terminal, retry.

---

## Этап 8. Parallel шаги

### Реализовано

- **parallel_group** — подряд идущие шаги с одинаковым значением `parallel_group` (в т.ч. `NULL`) образуют одну группу. Шаги группы запускаются параллельно (до лимита на run).
- **Join** — переход к следующей группе только после перехода в терминал всех шагов текущей группы.
- **Лимит** — `PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN` (по умолчанию 10). В одной группе может быть больше шагов; тогда сначала запускаются до 10, по завершении одного запускается следующий в той же группе.
- Групповой статус: успех при успехе всех или при `continue_on_error=true` для упавших.

### Конфиг

- `PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN` (по умолчанию 10).

### Критерии готовности

- Fan-out/fan-in предсказуем и повторяем.
- Trace каждого параллельного шага виден отдельно (operation_id, step_run).

### Файлы

- `app/services/playbook_engine.py` — `_group_steps_by_parallel`, `_start_group_steps`, `_advance_to_next_group_or_finish`, логика в advance_after_terminal.
- `app/repos/playbook_repo.py` — `count_running_step_runs_for_run`, `get_step_runs_for_run_by_step_ids`.

---

## Этап 9. Capability Gate и совместимость агентов

### Реализовано

- До enqueue каждого step выполняется **pre-dispatch check**: наличие tool в актуальном toolset snapshot устройства; при наличии metadata — проверка платформы (device.os vs metadata.platforms).
- При несовместимости: создаётся step_run со статусом `failed`, `error_code` = `UNSUPPORTED_CAPABILITY` или `TOOL_UNAVAILABLE`, команда агенту не отправляется.
- Логика продвижения run после такого шага та же, что при обычном terminal (группа, следующая группа или завершение).

### Коды

- `TOOL_UNAVAILABLE` — устройство не найдено или нет toolset snapshot.
- `UNSUPPORTED_CAPABILITY` — tool отсутствует в toolset или не поддерживается на платформе.

### Критерии готовности

- Ошибки класса UNKNOWN_COMMAND из-за несовместимости минимизированы.
- Несовместимость фиксируется на сервере до отправки команды.

### Файлы

- `app/services/playbook_capability.py` — `check_tool_available(session, device_id, tool_name)`.
- `app/repos/playbook_repo.py` — `create_step_run_failed`, `get_step_run_with_step_and_run`.
- `app/services/playbook_engine.py` — вызов check в `_start_group_steps`, `_process_run_after_step_terminal` для advance без operation_id.

---

## Этап 10. Drift/Inventory: builtin vs managed

### Назначение

- В snapshot/tools добавить **origin**: `builtin` | `managed`.
- Drift-алгоритм: автоматические действия только по **managed**; **builtin** — только информационно.
- UI/API: отдельные секции drift по origin.

### Статус

- Подготовка: контракт и схема (origin в каждом tool в toolset_json) описаны в плане; агент должен отдавать origin в list_tools. Реализация фильтрации drift по origin — в UI/API и в логике drift (следующая итерация).

### Критерии готовности

- Drift-шум от встроенных инструментов не триггерит автоматику.

---

## Этап 11. Масштаб каталога атомарных команд (100–150)

### Назначение

- Домены: system, process, filesystem, network, service, security, diag, ui.
- Волны: 30–40 → 80–100 → 120–150 production-grade команд.
- Для каждой команды: module.tool, metadata-контракт, unit + integration тесты, docs, risk/consent policy. CI: Linux + Windows, smoke + contract tests.

### Статус

- Атомарные команды пока не пишутся; подготовлено:
  - Контракт list_tools (metadata: domain, platforms, risk_level, requires_consent, timeout_sec, idempotent, allow_roles, scopes).
  - Контракт ошибок run_tool (INVALID_TOOL_FORMAT, TOOL_NOT_FOUND, UNSUPPORTED_CAPABILITY, CONSENT_REQUIRED, TIMEOUT, COMMAND_FAILED).
  - Capability Gate на сервере и структура для проверки tool в snapshot.

### Критерии готовности

- Каждая команда имеет измеряемые SLO; нет платформенных «сюрпризов» на релизе.

---

## Этап 12. Наблюдаемость, SLO, rollout

### Метрики (целевые)

- success_rate, p95_duration, timeout_rate по команде и по шагам playbook.

### Алерты

- Рост timeout и retry-storm.

### Feature flags (целевые)

- `PLAYBOOK_SCHEDULER_ENABLED`
- `PLAYBOOK_PARALLEL_ENABLED`
- `CAPABILITY_GATE_STRICT`

### Канареечный rollout

- 10% → 50% → 100% устройств.

### Критерии готовности

- Rollout контролируемый; откат по флагу без смены транспорта.

---

## Тесты и сценарии приёмки

- E2E: immediate run online device.
- E2E: scheduled run offline → reconnect → продолжение.
- E2E: step timeout → run terminal без зависания.
- E2E: retry policy с transient error и success на N-й попытке.
- E2E: parallel group с mixed success/fail + continue_on_error.
- E2E: capability mismatch → fail до enqueue.
- Contract tests: list_tools metadata schema обязательна.
- Regression: install_module same sha → no-op success.
- Load: 500+ одновременных run, SKIP LOCKED и отсутствие дублей запуска.

---

## Связанные документы

- `PLAYBOOK_IMPLEMENTATION.md` — общий план и этапы 1–6.
- `PLAYBOOK_API.md` — POST /api/playbooks/runs и dry_run/idempotency.
- `MODULES_DRIFT_AND_SNAPSHOTS.md` — drift и snapshots.
