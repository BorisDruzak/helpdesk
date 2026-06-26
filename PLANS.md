# PLANS.md — программа качества, live-проверок, Observer и БД

## Статус и область

- **Статус:** implementation largely complete; release/live validation blocked. P0 Observer scan completeness is **`[~]`**: code-side fix, focused DB proof and plain full CI are green for current verified checkpoint `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`, but the item is not `[x]` until exact live release summary, release preflight and full release gate pass for the same commit/environment. Current preflight accepts the green CI and webapp bundle, then rejects exact-context `artifacts/live/release-summary.json` for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`/`stand`/release run `critical-behavior-ffa831a4-20260626`/schema head `130` because `status='fail'`: the first live scenario has browser/API partial evidence but still fails manifest validation on missing Observer/canary/cleanup evidence, and the remaining 16 critical behavior scenarios still lack passing live evidence manifests.
- **Дата анализа:** 2026-06-26.
- **Анализируемая ветка:** `codex/helpdesk-process-model`.
- **Latest verified P0/CI checkpoint revision:** `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`.
- **Latest Observer scan completeness evidence:** focused isolated PostgreSQL suite `server/tests/test_observer_integrity_scan_completeness.py` passed with 201/301/501 boundary checks plus resolve-only-current-finding/per-check report coverage; no-DB scope suite `server/tests/test_observer_integrity_scan_scope.py` passed. In the latest full CI for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`, `server_pytest_db_observer_diagnostics` passed with the scan completeness tests included (`126 passed, 42 deselected`), and `migration_schema` passed for schema head `130`; the full P0 item is still open until exact live evidence, release preflight and full release gate pass for the same commit/environment.
- **Latest integrity checker isolation evidence:** service/API now expose timeout-bounded per-check reports, resolve only `status=passed && complete=true`, and persist reports in `observer_integrity_check_runs`; focused no-DB scope suite passed (`10 passed in 0.34s`) and isolated PostgreSQL completeness/report suite passed (`5 passed in 481.79s`).
- **Latest CI evidence:** plain full `python scripts/run_ci_suite.py --workspace . --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` is green: `artifacts/ci/ffa831a4ee84bf0e2897a8a96e9423acb2a0605a/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, `flaky_summary.status=pass`, `clean_green=true`, and 21/21 passed steps. Key layers include `migration_schema` (`4 passed`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`), `server_pytest_db_tickets` (`401 passed, 75 deselected`), `server_pytest_db_web_api` (`392 passed, 6 skipped, 301 deselected`), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`).
- **Release readiness:** blocked by live evidence, not by CI. Exact preflight `python scripts/release_candidate_preflight.py --workspace . --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a --environment stand --release-run-id critical-behavior-ffa831a4-20260626 --expected-schema-head 130 --allow-local-dirty` accepts the green CI artifact and webapp bundle, then rejects `artifacts/live/release-summary.json` because it is `status='fail'`, with `failed_scenario_keys=['requester_support_admin_session_switch']` and 16 remaining `missing_scenario_keys`. P0 Observer scan completeness is `[~]`, not `[x]`, until a passing exact-context live summary, preflight and full gate exist for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`/`stand`/schema head `130`.
- **Latest live evidence slice:** `requester_support_admin_session_switch` now has exact browser/API partial evidence for current checkpoint `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` in `artifacts/live/critical-behavior-ffa831a4-20260626__requester_support_admin_session_switch/manifest.json`: test requester/support passwords were reset through the cookie-auth admin API with CSRF Origin, both role-scoped logins returned HTTP 200, and `run_live_behavior_suite.py` browser probes passed for `/app/requester` and `/app/support` with `loginSubmitted=true`, expected Russian markers and no console/page errors. The manifest intentionally remains `status=blocked`; validation still fails on missing finished timestamp, Observer delta/canary, contamination and cleanup evidence, so exact `artifacts/live/release-summary.json` is `status=fail`.
- **Latest Observer canary auth evidence:** local `scripts/run_observer_canary_suite.py` now logs in through `/api/web/session/login`, reads the `pc_client_web_session` cookie from the diagnostic HTTP client and uses that UI token for the existing canary bearer calls without re-enabling `/api/ui_login`. Targeted proof: `python -m pytest scripts/test_run_observer_canary_suite.py -q --tb=short` passed (`18 passed`), `python -m pytest server/tests/test_auth_security.py::test_legacy_ui_login_disabled_by_default server/tests/test_web_session_api.py::test_web_session_login_sets_http_only_cookie -q --tb=short` passed (`2 passed`), and live `python scripts/run_observer_canary_suite.py --source-coverage-only` passed on stand with report `artifacts/observer_canaries/observer_canary_20260626_074728.json` (`coverage.ok=true`, 9/9 source root kinds observed).
- **Основная цель:** сделать исправление багов воспроизводимым, тесты — достоверными, live-проверки — доказательными, а технический долг — управляемым.
- **Критические зоны:** ticket/requester/support behavior, Protocol V3, agent runtime, PostgreSQL, Observer overlay, webapp, CI/release scripts.
- **Не является целью:** превращать Observer в источник бизнес-истины, подменять live-проверку fixture/mocked E2E-тестом или запускать разрушающие проверки на production-данных.

Этот документ заменяет узкий task-local план по форме создания обращения. Завершенная работа по той задаче сохранена в приложении в конце файла.

## План полного закрытия замечаний 2026-06-24

Статусы: `[ ]` не начато или нет достаточной реализации, `[~]` частично реализовано и требуется доказательство/доработка, `[x]` закрыто кодом и проверками.

> Current P0 Observer scan completeness status (2026-06-26): **`[~]`** for verified P0/CI checkpoint `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`. Code-side/focused DB proof exists, exact full CI is green with the Observer diagnostics layer and scan completeness tests included, and `server_pytest_agent_ws` passes in the full gate. The item is still not `[x]` because exact live release summary/release preflight/full release gate have not passed for the same commit/environment.

Review refresh 2026-06-25 for the attached "Что обязательно доделать" list:

- `P0 Observer scan completeness`: **`[~]`**. The code-side completeness defects from the review are fixed, covered by real DB boundary tests, and covered by green exact full CI for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`; the Observer canary auth drift is fixed locally and source coverage is green on stand. The release-level P0 remains open until exact-context live release summary plus release preflight/full gate are green on the same commit/environment.
- `P0/P1 integrity checker isolation`: `[x]` for focused implementation/evidence; keep covered by `observer_integrity_check_runs`, bounded per-check reports and resolve only for `status=passed && complete=true`.
- `P0 full live behavior pack`: `[~]`; 17 scenario manifests exist only as blocked scaffolds, not as passing `pc_client.live_evidence.v2` proof.
- `P0 strict live release summary aggregator`: `[x]`; exact `commit/environment/release-run/schema` filtering and fail-wins semantics are implemented.
- `P0 release preflight live summary gate`: `[x]`; preflight and full release gate require a passing exact-context live summary.
- `P0 full green CI for latest verified P0/CI checkpoint`: `[x]`; latest plain full CI for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` is green (`status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, 21/21 steps).
- `P1 web Observer execution identity`: `[x]`; server-side request identity and durable execution keys are implemented and covered.
- `Active risks are not eliminated`: `[~]`; risk governance is complete, underlying active/accepted risks remain tracked.
- `P1/P2 suite catalog source of truth`: `[x]`; runner and inventory audit use `quality/test_suites.toml`.
- `P2 branch coverage wording`: `[~]`; current gate validates a critical branch registry, not measured coverage execution.
- `P1/P2 DB/migration checks`: `[~]`; current suite covers fresh/idempotent/schema smoke, but old-baseline/partial-failure/dynamic sentinel checks remain open.
- `P1 integrity occurrence_count semantics`: `[x]`; recurrence and scan observation counters are split and migrated.

- [~] **P0 Observer scan completeness**: **статус 2026-06-26: code-side fix, focused DB-proof и latest exact full CI закрыты для verified P0/CI checkpoint `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`; Observer canary auth drift fixed locally and source coverage passed on stand; пункт остается `[~]`, не `[x]`, потому что release preflight/live evidence/full release gate еще не прошли на том же commit/environment.** Fail-closed path реализован: все top-level checkers возвращают `ObserverIntegrityCheckResult`, bounded scans используют `LIMIT + 1` windows, `runtime_presence` возвращает incomplete при отсутствии state, неизвестная `source_complete` больше не считается complete по умолчанию. DB-улика: focused suites `server/tests/test_observer_integrity_scan_completeness.py` и `server/tests/test_observer_integrity_scan_scope.py` покрывают 201 operation, 301 web cabinet, 501 runtime, per-check report и сценарий "incomplete scan не resolve, complete scan resolve только исчезнувшую visible finding". Latest exact full CI: `python scripts/run_ci_suite.py --workspace . --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` passed with `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, 21/21 steps, including `migration_schema` (`4 passed`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`, including scan completeness tests), `server_pytest_db_web_api` (`392 passed, 6 skipped, 301 deselected`), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`). Current preflight rejects exact-context failing live summary for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`/`stand`/release run `critical-behavior-ffa831a4-20260626`/schema head `130`: `status='fail'`, `requester_support_admin_session_switch` is failed because its manifest still lacks Observer/canary/cleanup evidence, and 16 scenarios remain missing. Latest source coverage canary after auth fix passed: `python scripts/run_observer_canary_suite.py --source-coverage-only` wrote `artifacts/observer_canaries/observer_canary_20260626_074728.json`, `coverage.ok=true`, missing root kinds empty, 9/9 source root kinds observed. Недостающее для перевода в `[x]`: `pc_client.live_release_summary.v1 status=pass`, `release_candidate_preflight.py` pass with `--expected-schema-head 130`, and full release gate pass for `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`/`stand`.
- [x] **P0/P1 integrity checker isolation**: закрыто focused implementation/evidence. Runner использует savepoint isolation where available, rollback fallback without savepoint, bounded checker timeout, per-check status/duration/window/scanned/generated/active/suppressed/resolved/error report, persisted `observer_integrity_check_runs`, API `checks` payload and resolve gate only for `status=passed && complete=true`. Доказательства: RED/GREEN `server/tests/test_observer_integrity_scan_scope.py` (`10 passed in 0.34s`), isolated PostgreSQL `server/tests/test_observer_integrity_scan_completeness.py` (`5 passed in 481.79s`), schema cleanup audit from models, docs drift and navigation catalog tests.
- [~] **P0 full live behavior pack**: automation prerequisite improved; browser dry-run covers all 14 browser scenarios across `requester,support,admin,reports`, agent-operation dry-run covers 2 scenarios, and the live-browser runner now waits for the React login inputs after redirect/hydration. First real scenario slice was rerun for current exact context `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a`/`stand`/`critical-behavior-ffa831a4-20260626`/schema head `130`: requester/support API logins pass and browser probes pass. Exact-context release summary is still `status=fail`: `requester_support_admin_session_switch` has a blocked/validation-fail manifest without Observer delta/canary/cleanup evidence, source-coverage Observer canary auth is fixed and green on stand, and the other 16 scenarios are missing. Still open until the full `critical_behavior_v1.json` run on one frozen commit/environment produces 17 passing `pc_client.live_evidence.v2` manifests.
- [x] **P0 strict live release summary aggregator**: `build_live_release_summary.py` теперь выбирает manifests только по `--commit`, `--environment`, `--release-run-id`, `--expected-schema-head`; fail/blocked текущего release context доминирует над pass из старого commit/run/schema. Доказательства: RED/GREEN `scripts/test_build_live_release_summary.py::test_build_live_release_summary_filters_to_exact_release_context_and_fail_wins`; latest full CI на `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` включает `scripts/test_build_live_release_summary.py`, а release preflight для этого commit блокируется без passing exact-context `artifacts/live/release-summary.json`.
- [x] **P0 release preflight live summary gate**: добавлен обязательный `require_live_release_summary(commit, environment)` для `release_candidate_preflight.py` и `release_server_to_remote.py --gate full`; helper проверяет schema `pc_client.live_release_summary.v1`, `status=pass`, exact commit/environment, optional release-run/schema и отсутствие failed/missing scenarios. Доказательства: RED/GREEN `scripts/test_ci_artifacts.py`, `scripts/test_release_candidate_preflight.py`, `scripts/test_release_server_to_remote.py`.
- [x] **P0 full green CI for latest verified P0/CI checkpoint**: latest plain full `python scripts/run_ci_suite.py --workspace . --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` is green (`status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, 21/21 steps). Release preflight/live evidence remain separate release-readiness gates for moving P0 Observer scan completeness to `[x]`.
- [x] **P1 web Observer execution identity**: code-side server-generated request identity реализован (`request_id_middleware`, actor contexts, writer attrs, requester/support chat `message_id` как `idempotency_key`) и no-DB RED/GREEN proof проходит. DB/API regression без клиентского `X-Request-ID` прошел (`server/tests/test_requester_workspace_api.py::test_requester_distinct_messages_without_client_request_id_get_distinct_observer_traces`), а full CI на `66be2997b551027a0776d9587ac433117ab451b6` покрывает broader web API.
- [~] **Active risks are not eliminated**: Phase 5 означает governance/registry/gating, а не устранение всех underlying risks; `TD-012`, `TD-013`, `TD-014`, `TD-015`, `TD-017`, `TD-019` остаются active/accepted до отдельных implementation/live proofs.
- [x] **P1/P2 suite catalog source of truth**: закрыто. `quality/test_suites.toml` теперь является единым каталогом для canonical CI layer order, affected-suite base layers, server DB/API filename ownership, source-prefix routing and DB/WS parallel grouping; `scripts/run_ci_suite.py` и `scripts/audit_test_inventory.py` читают его через `scripts/suite_catalog.py`, а runner падает на Python-only/catalog order drift. RED/GREEN evidence: `scripts/test_run_ci_suite.py::test_server_db_api_layer_paths_uses_workspace_suite_catalog`, `scripts/test_audit_test_inventory.py::test_inventory_audit_uses_workspace_suite_catalog_for_server_db_ownership`; focused suite `python -m pytest scripts/test_run_ci_suite.py scripts/test_audit_test_inventory.py -q --tb=short` passed (`30 passed in 4.49s`).
- [~] **P2 branch coverage wording**: `COV-405` сейчас является реестром заявленных targeted branches, не measured coverage engine; для `[x]` нужен реальный targeted coverage gate.
- [~] **P1/P2 DB/migration checks**: `DB-104` покрывает fresh/idempotent/schema smoke, но еще не доказывает old baseline snapshot upgrade, partial migration recovery, dynamic sentinel cleanup/concurrency и reference-fixture preservation.
- [x] **P1 integrity `occurrence_count` semantics**: закрыто. `observer_integrity_events` теперь разделяет `scan_observation_count`, `recurrence_count`, `first_seen_at`/`last_seen_at` и `last_reopened_at`; legacy `occurrence_count` оставлен как alias реального `recurrence_count`, а повторные scan observations больше не выглядят как новые инциденты. Migration `130` сохраняет старый legacy count как `scan_observation_count` и нормализует recurrence-счетчик. RED/GREEN evidence: `server/tests/test_observer_integrity_scan_scope.py::test_upsert_event_preserves_acknowledged_status_when_condition_persists`, `::test_upsert_event_counts_recurrence_only_when_resolved_condition_returns`; focused DB evidence `server/tests/test_observer_integrity.py::test_observer_integrity_recurrence_count_increments_only_after_resolution`; migration/schema evidence `server/tests/test_migration_schema_contract.py` passed.

---

## 1. Целевое состояние

Проект считается контролируемым, когда для каждого критического поведения можно ответить на пять вопросов:

1. Как воспроизвести ошибку детерминированно?
2. Какой тест падает до исправления и проходит после него?
3. Какие строки PostgreSQL и/или SQLite подтверждают фактическое состояние?
4. Какая Observer trace/span/signature подтверждает прохождение или деградацию?
5. Что увидел реальный пользователь в браузере или native GUI?

Обязательные архитектурные инварианты:

- PostgreSQL остается source of truth для серверного доменного состояния.
- Agent SQLite остается source of truth только для локального durable-состояния агента.
- Observer является техническим overlay и не изменяет ticket, operation, outbox, registry или policy state.
- `pass` нельзя объявлять по одному сигналу: HTTP `200`, строка в БД, отсутствие exception или screenshot по отдельности недостаточны.
- Видимое web-поведение проверяется в реальном браузере; fixture Playwright остается быстрым UI-contract слоем.
- ACK означает persisted, доказанный duplicate или доказанный no-op; «ответ отправлен» не равен «результат сохранен».
- Любой live-run использует уникальный `run_id` и отделяет pre-fix contamination от новых данных.
- Любое исправление бага включает regression test на минимальном корректном слое и cross-layer проверку, если меняется boundary.

---

## 2. Что в проекте уже сделано хорошо

Текущая база качества сильнее типового проекта и должна быть расширена, а не заменена:

- pytest уже разделен на `no_db`, DB-domain и `agent_ws` слои;
- PostgreSQL-тесты умеют создавать изолированную БД и клонировать мигрированный template;
- есть watchdog, fixture timing, JUnit и раздельные CI-артефакты;
- определены domain cleanup profiles и AST-аудит их применения;
- webapp имеет Vitest, production bundle build и fixture Playwright;
- live-debug правила требуют browser/API/DB/agent/log evidence;
- Observer уже имеет trace/span/link/signature/integrity модель, typed API, canary suite и redaction;
- существуют тестовые data packs и Phase E browser-evidence gate;
- `reset_test_data.py` уже умеет анализировать фактическую PostgreSQL-схему и FK-граф;
- документация фиксирует source-of-truth и ownership boundaries.

Основная проблема не в отсутствии тестов, а в нескольких источниках **ложно-зеленого результата**, schema/test drift и неполной сквозной доказательности.

---

## 3. Результаты статического анализа

### 3.1 Подтвержденные дефекты и разрывы

| ID | Приоритет | Наблюдение | Риск | Первое действие |
|---|---|---|---|---|
| `OBS-001` | P0 | Integrity-checkers читают ограниченные выборки (`LIMIT 200/300`), после чего `resolve_missing()` закрывает все active/acknowledged события source, которых нет в текущем наборе ключей. | При количестве нарушений выше лимита старые реальные нарушения могут быть ложно помечены `resolved`. | Regression test с `limit + 1` нарушениями; затем scope-aware resolve или полная пагинация. |
| `DB-001` | P0 | `FULL_CLEANUP_TABLES` и профили поддерживаются вручную и уже не покрывают всю схему; в частности, отдельные `change_*` таблицы отсутствуют, хотя созданы миграцией `092`. | Межтестовая контаминация, order-dependent failures, ложные green/red результаты. | Автоматический schema-to-cleanup audit по `pg_catalog` и FK-графу; закрыть текущий drift. |
| `CI-001` | P0 | Корневой pytest обнаруживает `scripts/test_*.py`, но `scripts/run_ci_suite.py` не запускает отдельный scripts-test слой. | Тесты CI/release/live tooling могут не исполняться в каноническом gate. | Добавить `scripts_pytest_no_db` и тест, фиксирующий состав шагов. |
| `OBS-002` | P1 | Existing integrity event при каждом повторном scan получает `status=active`, даже если оператор перевел его в `acknowledged`. | Acknowledgement неустойчив, операторская triage-информация теряется. | Characterization test и явная state transition policy. |
| `OBS-003` | P1 | `_has_create_observer_trace()` использует широкое `OR`: совпадения только по source или только по event type достаточно. | Integrity-check может принять blocked/чужой trace за доказательство успешного ticket create. | Сделать допустимые пары `(source, event_type)` явными и протестировать negative cases. |
| `LIVE-001` | P1 | `webapp/tests/requester-workspace.spec.ts` подменяет API через `page.route()` и запускается на fixture server. | Тест хорошо проверяет UI contract, но не доказывает server/DB/Observer behavior. | Явно маркировать artifact как `fixture_e2e`; добавить отдельный live-browser gate. |
| `LIVE-002` | P1 | `live_evidence_pack.py` создает markdown-шаблоны, но не проверяет их заполненность и непротиворечивость. Phase E gate строго валидирует главным образом browser evidence. | Папка evidence может существовать без DB/Observer/API доказательств, но восприниматься как завершенная проверка. | Ввести manifest v2 и машинный validator для всех обязательных сигналов. |
| `CI-002` | P1 | DB-test routing основан преимущественно на именах файлов; неизвестные DB-тесты попадают в широкий `web_api` catch-all. | Новый тест может выполняться не в том домене, скрывать ownership и увеличивать нестабильность. | Machine-readable suite catalog и fail-on-unowned-test audit. |
| `DB-002` | P1 | На Windows возможен автоматический fallback на shared test DB при недоступности admin DB. | Параллельные локальные прогоны могут влиять друг на друга; warning можно пропустить. | Сделать shared fallback явным opt-in и запрещенным для любого release/full gate. |
| `DOC-001` | P2 | Корневой `PLANS.md` был task-local отчетом по одной UI-задаче. | Нет единого приоритизированного quality/bug/tech-debt backlog. | Использовать этот документ как master-plan; task plans хранить отдельно. |

### 3.2 Риски, требующие characterization-тестов

| ID | Приоритет | Статическое наблюдение | Что необходимо доказать |
|---|---|---|---|
| `OBS-004` | P1 | Web Observer `trace_id` детерминируется по `source + event_type + route + ticket/person/device`, span также переиспользуется. Повторный вызов обновляет существующие trace/span. | Не теряется ли хронология повторяемых действий; не возникает ли trace `succeeded` при сохраненных error occurrences после последовательности fail → success. |
| `OBS-005` | P1 | Integrity scan вызывает checkers последовательно в одной orchestration path без per-check result/timeout/isolation. | Падение одного checker не должно скрывать результаты остальных и не должно приводить к ложному resolve. |
| `OBS-006` | P1 | `occurrence_count` integrity event увеличивается на каждом scan, а не только при новом фактическом эпизоде. | Семантика поля должна быть определена: scan observations или реальные occurrences. |
| `OBS-007` | P2 | Known contamination частично seed-ится из hardcoded списка в runtime-коде. | Исключения не должны становиться бессрочными и бесхозными; нужны owner, expiry и review. |
| `DB-003` | P1 | Часть новых таблиц может очищаться только каскадом, часть — не очищаться вовсе. | Автоматический audit должен доказать классификацию каждой public table и корректность FK-порядка. |
| `WEB-001` | P2 | Fixture payloads дублируют typed API вручную; недавняя история содержит исправления fixture drift. | DTO/fixture contract должен генерироваться или валидироваться против server schema. |
| `CI-003` | P2 | Playwright в CI имеет один retry. | First-attempt failure должен оставаться видимым как flaky, а не превращаться в обычный green. |

### 3.3 Ограничение текущего анализа

Этот baseline построен по коду, документации, миграциям и тестам указанной GitHub-ревизии. В рамках составления плана не выполнялись:

- remote deploy;
- подключение к live PostgreSQL;
- запуск Windows/Linux agent VM;
- реальный browser-run на стенде;
- полный локальный `run_ci_suite.py`.

Поэтому runtime-гипотезы выше сначала закрываются воспроизводящими тестами, а не исправляются «по чтению кода».

---

## 4. Приоритеты

### P0 — убрать ложные green и риск повреждения доказательств

1. Исправить bounded-scan/false-resolve в Observer.
2. Закрыть schema-to-cleanup drift.
3. Включить `scripts/test_*.py` в канонический CI.
4. Запретить неявный shared DB для полного gate.
5. Зафиксировать baseline durations, flaky/retry и test inventory.

### P1 — сквозные behavioral contracts

1. Стабилизировать trace identity и integrity lifecycle.
2. Построить critical-journey matrix API → DB → Observer → browser/GUI.
3. Ввести machine-verifiable live evidence manifest.
4. Добавить migration/constraint/concurrency tests.
5. Сделать test suite ownership явным.

### P2 — ускорение и профилактика регрессий

1. Contract-generated fixtures.
2. Property/state-machine tests для redaction, lifecycle и idempotency.
3. Targeted branch coverage и mutation testing для чистой критической логики.
4. Flake quarantine policy без бесконечных retry.
5. CI performance budgets и автоматический поиск тяжелых fixtures.

### P3 — долгосрочная эксплуатационная зрелость

1. Multi-instance/concurrency/chaos scenarios.
2. Retention, volume и query-plan tests для Observer.
3. Dependency/security/static-analysis gates.
4. Автоматическая связь bugs/tech debt с evidence и regression tests.

---

## 5. Workstream A — инвентаризация и архитектура тестов

### A1. Единый каталог suites

Создать machine-readable каталог, например `quality/test_suites.toml`, где для каждого слоя заданы:

- `name`;
- `paths` или explicit selectors;
- marker expression;
- DB domain и cleanup profile;
- owner zone;
- timeout и idle timeout;
- допустимая параллельность;
- требуемые сервисы;
- тип evidence;
- blocking/non-blocking policy.

Минимальные suites:

- `workspace_static`;
- `scripts_pytest_no_db`;
- `webapp_unit`;
- `webapp_fixture_e2e`;
- `server_no_db`;
- `server_db_knowledge`;
- `server_db_tickets`;
- `server_db_observer_diagnostics`;
- `server_db_agent_runtime`;
- `server_db_registry_access`;
- `server_db_policies_config`;
- `server_db_registration`;
- `server_db_web_support`;
- `server_agent_ws`;
- `pc_agent_unit`;
- `pc_agent_integration`;
- `migration_schema`;
- `live_browser`;
- `live_observer_canary`.

Acceptance criteria:

- каждый `test_*.py`, `*.test.ts[x]` и `*.spec.ts` принадлежит ровно одному primary suite;
- unowned или multiply-owned тест делает audit красным;
- новый домен нельзя незаметно отправить в catch-all;
- suite catalog используется и runner, и документацией.

### A2. Закрыть scripts-test gap

Изменить:

- `scripts/run_ci_suite.py`;
- `scripts/test_run_ci_suite.py`;
- при необходимости `docs/TESTING_RULES.md`.

Новый шаг:

```text
scripts_pytest_no_db:
  python -m pytest scripts/test_*.py -m "not manual" -vv --durations=40 --junitxml=...
```

Не включать в него live/deploy tests, требующие стенда. Такие тесты должны проверять pure parsing, validation, command building и report generation через fixtures/mocks.

Acceptance criteria:

- тест состава CI-шагов ожидает `scripts_pytest_no_db`;
- intentional exclusion live-скрипта описано в suite catalog;
- failure любого scripts unit test делает full gate red.

### A3. Strict marker/profile audit

Сделать обязательными в full gate:

```powershell
python scripts/audit_db_cleanup_profiles.py --strict
python scripts/audit_test_inventory.py --strict
```

Дополнительно audit должен проверять:

- DB-backed тест без `db_cleanup` или явного domain ownership;
- `no_db` тест, который запрашивает DB fixture;
- `agent_ws` тест, случайно попавший в обычный DB layer;
- unknown marker;
- test module с network/live access в PR suite;
- прямой `time.sleep()` в async/integration тесте без обоснованного allowlist.

### A4. Test-result taxonomy

Каждый отчет должен различать:

- `passed_first_attempt`;
- `passed_after_retry`;
- `failed`;
- `timed_out`;
- `idle_timed_out`;
- `skipped_expected`;
- `skipped_environment`;
- `not_run_due_to_dependency`;
- `infrastructure_error`.

`passed_after_retry` не равен clean green. Он создает flaky record с test node id, seed, worker, trace/video/log и предыдущей ошибкой.

---

## 6. Workstream B — PostgreSQL, миграции и изоляция

### B1. Schema-to-cleanup drift gate

Создать `scripts/audit_db_cleanup_schema.py`.

Источник истины — фактическая мигрированная test DB:

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public';
```

Для каждой таблицы должна существовать классификация:

- `ephemeral_test_data`;
- `persistent_reference_fixture`;
- `migration_metadata`;
- `explicitly_excluded` с причиной.

Audit строит FK-граф, проверяет:

- присутствует ли ephemeral table хотя бы в одном cleanup path;
- очищается ли parent без зависимого child;
- не полагается ли профиль на отсутствующий/не-CASCADE FK;
- не содержит ли cleanup устаревшее имя таблицы;
- нет ли новой таблицы без owner/profile;
- совпадает ли `FULL_CLEANUP_TABLES` с фактической политикой.

Первый baseline обязан проверить и классифицировать как минимум:

- все `change_*`;
- новые `knowledge_segmentation_*`;
- `knowledge_ai_proposals`;
- `knowledge_taxonomy_*`, `knowledge_*properties`, applicability и quality models;
- runner rollout tables;
- auth/session/consent tables;
- diagnostic link/capability join tables.

Рекомендуемое решение — переиспользовать FK/introspection primitives из `scripts/reset_test_data.py`, не создавать второй несовместимый алгоритм.

### B2. Cleanup profile correctness tests

Добавить тесты:

- `test_full_cleanup_covers_all_ephemeral_tables`;
- `test_each_cleanup_profile_has_valid_fk_closure`;
- `test_cleanup_profiles_do_not_delete_reference_fixtures`;
- `test_cleanup_is_idempotent`;
- `test_cleanup_removes_rows_created_by_previous_test`;
- `test_new_migration_table_requires_cleanup_classification`.

Проверить каждый профиль двумя способами:

1. статически — schema/FK audit;
2. динамически — seed sentinel rows, выполнить cleanup, проверить ожидаемое сохранение/удаление.

### B3. Изолированная БД fail-closed

Политика:

- full/release/nightly gate работает только с `pc_support_test_<runid>...`;
- shared `pc_support_test` разрешен только явным локальным флагом;
- summary содержит `database_name`, `isolation_mode`, `template_fingerprint`, Alembic heads;
- shared mode никогда не может дать release-pass;
- параллельные domains получают разные DB names;
- teardown failure не скрывается warning-only: создается artifact и cleanup debt record.

### B4. Migration gate

Добавить отдельный migration suite:

1. пустая PostgreSQL DB → `alembic upgrade head`;
2. проверка exact head set;
3. повторный `upgrade head` без изменения схемы;
4. upgrade с поддерживаемого baseline snapshot;
5. проверка обязательных constraints/indexes/defaults;
6. smoke insert/select/delete для новых таблиц;
7. schema diff между SQLAlchemy metadata и фактической DB с allowlist для осознанных расхождений;
8. downgrade — только для миграций, где проект официально обещает downgrade; иначе проверять fail-safe documentation.

Для миграций с `_has_table/_has_column` отдельно тестировать частично примененную схему: conditional migration не должна молча принимать несовместимую структуру.

### B5. DB behavioral invariants

Обязательные tests:

- canonical ticket status constraint;
- non-empty requester identity;
- deterministic timeline order `(created_at, id)`;
- idempotency `(device_id, ticket_id, agent_seq)`;
- operation/outbox/result consistency;
- latest feedback uniqueness;
- one active primary binding where это требуется policy;
- one-time token/nonce consumption;
- no requester PII in aggregate analytics;
- Observer FK/reference behavior не изменяет доменные строки.

### B6. Concurrency tests

Для критических гонок использовать реальные параллельные транзакции:

- duplicate ticket event ingest;
- duplicate ACK;
- competing assignment/claim;
- close vs reopen;
- consent timeout vs approval;
- operation cancel vs result;
- one-time publish token double-submit;
- primary-device rebinding;
- Observer same-trace materialization;
- cleanup vs open connection.

Каждый тест должен иметь barrier, bounded timeout и проверять конечное состояние, а не только отсутствие exception.

---

## 7. Workstream C — Observer correctness и анализ слоя

### C1. Исправить false resolve при bounded scan

Regression test должен создать больше нарушений, чем query limit:

```text
limit = 200
seed = 201 active violations
scan #1 -> 201 events remain active
fix one violation
scan #2 -> only fixed violation resolves
```

Допустимые реализации:

- checker полностью пагинирует набор нарушений;
- checker возвращает `ScanCoverage(scope, complete, entity_ids, cursor)`;
- `resolve_missing()` получает явный scope/window и разрешает только сущности, которые реально были проверены;
- при incomplete/error scan resolve запрещен.

Нельзя исправлять увеличением `LIMIT`: это откладывает дефект, но не меняет неверную семантику.

### C2. Checker runner с изоляцией и отчетом

Ввести registry:

```python
CheckerSpec(
    source="observer.operation_lifecycle",
    callable=check_operation_lifecycle,
    timeout_seconds=...,
    resolution_policy="complete_scope_only",
)
```

Для каждого checker записывать:

- started/finished/duration;
- status: `passed`, `degraded`, `failed`, `timed_out`;
- scanned rows/entities;
- generated/active/suppressed/resolved counts;
- complete/incomplete coverage;
- error type и redacted message;
- cursor/window.

Падение одного checker:

- не отменяет результаты независимых checkers;
- не вызывает resolve для failed/incomplete source;
- делает общий scan `degraded` или `failed`;
- создает Observer self-health signature/event;
- возвращается в API и live artifact.

Рассмотреть отдельные таблицы `observer_integrity_runs` и `observer_integrity_check_runs`, если существующего audit недостаточно.

### C3. Integrity event lifecycle

Определить state machine:

```text
new condition -> active
active + operator ack -> acknowledged
condition persists -> acknowledged
condition disappears after complete scan -> resolved
resolved condition returns -> active, recurrence +1
known contamination match -> suppressed
suppression expires and condition persists -> active
```

Разделить счетчики:

- `scan_observation_count`;
- `recurrence_count`;
- при необходимости `affected_entity_count`.

Добавить tests на:

- acknowledgement persistence;
- recurrence after resolution;
- suppression expiry;
- changed severity/evidence;
- two concurrent scans;
- failed scan without resolve;
- run_id association.

### C4. Web trace identity: одна execution — одна trace

Сначала characterization tests:

1. два сообщения в одном ticket;
2. два одинаковых API retry с одним idempotency/correlation id;
3. два независимых запроса с разными request ids;
4. blocked → success;
5. error → success;
6. concurrent same-ticket actions.

Целевой контракт:

- `trace_id` идентифицирует execution, а не только entity;
- entity (`ticket_id`, `device_id`, `person_ref`) остается фильтром/correlation link;
- retry одного execution либо idempotently обновляет тот же trace, либо создает явную retry link;
- независимые executions не перезаписывают друг друга;
- error occurrence всегда согласуется со status/error_count trace;
- span history не теряется.

Предпочтительный identity input:

```text
idempotency_key / operation_id / server_request_id / request_id / correlation_id
```

Fallback UUID допустим только когда durable execution key действительно отсутствует. Не использовать raw actor identity в trace key.

### C5. Строгая проверка create trace

Заменить широкое условие на allowlist успешных контрактов, например:

```text
(source=requester_ticket_create AND event_type IN {ticket_create_succeeded, ticket_create_created})
```

Negative tests:

- `ticket_create_blocked`;
- success event другого source;
- trace без ticket id;
- failed trace;
- trace создан до ticket и не связан durable id;
- redacted attrs без обязательного contract version.

### C6. Redaction и privacy

Добавить property/fuzz tests для nested payloads:

- Authorization/Cookie/session/token/password/secret/private key;
- email/phone;
- raw request/response body;
- URL query parameters;
- exception chains;
- list/tuple/set/custom mapping;
- oversized/unicode/binary-like input.

Assertions выполняются:

- на ORM rows;
- на typed API response;
- на exported diagnostics bundle;
- на logs/artifacts;
- в browser DOM.

Raw sensitive marker в любом Observer artifact — blocking failure.

### C7. Observer non-mutation contract

Для каждого writer/projector/integrity checker:

1. snapshot доменных строк;
2. выполнить Observer path;
3. commit;
4. сравнить все business columns;
5. разрешить изменения только в Observer/audit tables.

Покрыть ticket, operation, outbox, registry binding, policy, consent и module desired state.

### C8. Known contamination governance

Перенести постоянные исключения из hardcoded runtime seed в управляемый manifest/DB migration/command.

Каждая запись содержит:

- owner zone;
- linked bug/incident;
- exact entity/dedupe scope;
- reason;
- created_at;
- mandatory `expires_at`;
- review status;
- evidence path.

Gate падает, если:

- активная suppression просрочена;
- scope слишком широкий;
- отсутствует owner/bug/evidence;
- suppression скрывает новый run_id;
- число suppressions растет без review.

### C9. Coverage matrix

Поддерживать machine-readable matrix:

| Flow | Source fact | Root kind | Required spans | Signature | Integrity rule | UI surface | Live scenario |
|---|---|---|---|---|---|---|---|
| Requester create | ticket + web event | `requester_web` | validate, preview, persist | create failure | context/create trace | requester/support/admin | `REQ-CREATE-*` |
| Tool run | operation/outbox/events | `tool_call` | queue, dispatch, execute, result | timeout/error | lifecycle/ACK | support/admin | `TOOL-RUN-*` |
| Agent auth | audit/telemetry | `agent_auth` | connect, handshake, decision | invalid token | account/protocol | admin | `AUTH-*` |
| Module reconcile | desired/module/audit | `module_reconcile` | plan, enqueue, apply | reconcile failure | module/toolset | admin/device | `MODULE-*` |
| Observer runtime | runtime/check runs | `observer_runtime` | project/check | lag/failure | self-health | admin | `OBS-*` |

Audit должен запрещать новый опасный flow без строки matrix и test/live coverage declaration.

---

## 8. Workstream D — critical behavioral journeys

Для каждого journey нужны:

- service/unit tests;
- API/WS integration test;
- PostgreSQL assertions;
- Observer trace/integrity assertions;
- fixture UI test, если есть UI;
- real browser/native GUI live scenario;
- negative, retry и recovery cases;
- cleanup proof.

### D1. Requester lifecycle

| Scenario | API/behavior | DB evidence | Observer evidence | UI/live |
|---|---|---|---|---|
| Complete profile + primary device | preview/create succeeds | ticket, context v1, target, events | successful `requester_web` create trace | ticket visible, no raw ids |
| Incomplete profile | create blocked | no normal ticket row | blocked trace/signature, no false successful create | inline field/profile errors |
| No device allowed | manual triage create | ticket without forged dispatch target | missing-target trace, no critical integrity violation | clear no-device state |
| No device forbidden | preview/create blocked | no ticket | policy error trace | actionable message |
| On-behalf allowed | affected person target resolved | creator/affected/reason/context | no creator fallback/leak event | correct person/target summary |
| On-behalf denied | request rejected | no ticket | denied policy trace | no hidden affected data |
| Dynamic form validation | field-level typed errors | no partial ticket | validation trace without PII | `aria-invalid`, focus/status |
| Draft restore | local draft only until submit | no server ticket before create | no fake create trace | draft survives navigation |
| Chat retry | one logical message | one durable event or proven duplicate | separate execution/retry correlation | one rendered message |
| Resolve/feedback/reopen | canonical transitions | status/events/feedback/reopen rows | lifecycle traces | requester and support agree |

### D2. Support lifecycle

Проверить:

- queue list → claim/assign;
- status transition policy;
- waiting states;
- SLA/OLA clocks;
- public/private messages;
- attachment access;
- resolution confirmation;
- requester projection redaction;
- customer history;
- linked problem/change/quality data;
- concurrent claim;
- permission boundaries.

Для каждого изменения support UI сравнивать typed API payload, DB state и requester-visible projection.

### D3. Agent/Protocol V3 lifecycle

Проверить end-to-end:

1. authenticated handshake;
2. desired module/toolset reconcile;
3. command enqueue;
4. outbox dispatch;
5. agent seen/in-progress;
6. result/event persistence;
7. ACK persisted/duplicate/no-op;
8. reconnect replay;
9. cancellation;
10. timeout/retry exhaustion.

Negative cases:

- invalid token/device mismatch;
- malformed envelope;
- stale/duplicate seq;
- command result before started;
- operation terminal with active outbox;
- ACK without persistence proof;
- agent crash between in-progress and seen;
- duplicate side-effecting command;
- server restart during active operation;
- agent restart during telemetry upload.

### D4. Auth/account/session boundaries

Обязательные scenarios:

- requester A не видит ticket/device/person B;
- support/admin permissions разделены;
- expired/revoked web session;
- browser pairing replay;
- no raw token/cookie in log/Observer;
- account switch invalidates stale UI bootstrap;
- forged `device_id`, `person_id`, `actor_role` ignored;
- concurrent sessions and logout;
- requester on-behalf visibility остается creator-scoped для Knowledge.

### D5. Knowledge/Registry/Policy behavior

Проверить:

- requester/public/support/admin visibility;
- department tree/audience groups;
- stale or missing binding;
- safe search fallback with AI disabled;
- RAG exclusion before rerank/citation/prompt;
- form/catalog/policy snapshot versioning;
- policy publish token single use;
- archived/retired reference behavior;
- no PII in analytics;
- cleanup profiles для всех новых tables.

### D6. Полная domain regression matrix

| Domain | Ключевые инварианты | Минимальный автоматизированный слой | Обязательный live слой |
|---|---|---|---|
| Auth / web sessions | expiry, revocation, role/account isolation, cookie secrecy | service + API + DB constraints | requester/support/admin session switch |
| Registry / CMDB / access | person-device binding, primary uniqueness, visibility, archive semantics | repo/service/API + concurrency | real account/device linking |
| Tickets / chat | canonical lifecycle, ordering, idempotency, privacy | service/API/DB + WS | requester/support browser |
| Forms / Service Catalog | schema versions, conditional fields, publication token, fallback offering | contract/API/DB + fixture UI | requester create + admin publish |
| Routing / SLA / OLA | deterministic target, calendar clocks, escalation, queue permissions | pure policy + DB integration | support queue status |
| Knowledge Platform | ACL before retrieval/AI, versioning, bindings, indexing | repo/service/API/property tests | requester/support/admin search |
| Quality Loop | one effective feedback, reopen policy, QA privacy, analytics | service/API/DB | requester feedback + support QA |
| Problem Management | candidate dedupe, merge/cooldown, RCA/known-error visibility | service/scheduler/API/DB | admin problem + support link |
| Change Enablement | lifecycle, risk, approval, blackout, rollback/PIR | service/API/DB/concurrency | admin change workflow |
| Diagnostics / providers | capability version, credential ref secrecy, evidence chain | service/API/DB + provider fakes | bounded provider canary |
| Modules / recipes / playbooks | publish validation, desired state, step ordering, rollback | service/WS/agent integration | module/playbook canary |
| Operations / consent | started-before-dispatch, consent state machine, terminal event | API/WS/DB/concurrency | tool run approve/deny/timeout |
| Agent auth/update/runtime | stable identity, reconnect, update rollback, local DB version | pc_agent + server contract tests | Windows/Linux VM |
| Remote Assist | authorization, consent, session/event closure, artifact access | service/API/DB | explicit non-production session |
| Observer | complete projection, no mutation, redaction, integrity lifecycle | DB/API/property/volume | admin/support trace drilldown |
| Reports / analytics | aggregate correctness, tenant/role/privacy filters | query/service/API snapshot | browser totals against seeded pack |
| Release / deploy | exact commit, schema head, health, rollback evidence | scripts unit + command contract | canonical stand release gate |

Для каждого domain owner создать `coverage record` со ссылками на test nodes и live scenarios. Пустая ячейка в coverage record является backlog item, а не неявным «не применимо».

---

## 9. Workstream E — live validation

### E1. Preflight

До каждого live-run сохранить в manifest:

- exact local commit и deployed commit;
- branch;
- server/control/agent build versions;
- Alembic head;
- base URL и environment label;
- test users/roles как безопасные refs;
- VM/device ids;
- test data pack version;
- Observer active critical/high baseline;
- DB contamination snapshot;
- service health;
- clock/timezone;
- TLS mode;
- feature flags, влияющие на scenario.

Run блокируется, если deployed commit не совпадает с целевым или schema не на ожидаемом head.

### E2. Единый `run_id`

Формат:

```text
<surface>-<scenario>-<commit8>-<UTC timestamp>-<nonce>
```

`run_id` должен проходить через доступные correlation fields:

- `X-Request-ID` / `X-Correlation-ID`;
- API payload metadata только если контракт это разрешает;
- operation/trace attrs;
- test title/description marker;
- logs;
- evidence manifest.

Не добавлять test marker в бизнес-поля, которые видит пользователь, если есть технический correlation channel.

### E3. Evidence manifest v2

Создать схему `pc_client.live_evidence.v2`.

Обязательные поля:

```json
{
  "schema": "pc_client.live_evidence.v2",
  "run_id": "...",
  "scenario": "...",
  "status": "pass|fail|blocked",
  "commit": "...",
  "deployed_commit": "...",
  "environment": "...",
  "started_at": "...",
  "finished_at": "...",
  "entities": {
    "ticket_id": "...",
    "device_id": "...",
    "operation_id": "...",
    "trace_ids": []
  },
  "checks": [],
  "artifacts": [],
  "contamination": {},
  "cleanup": {}
}
```

Каждый check содержит:

- layer/surface;
- expected;
- actual summary;
- status;
- artifact path;
- query/request digest;
- timestamp;
- redaction status;
- not-applicable reason, если разрешено.

### E4. Обязательные сигналы по типу scenario

#### Web-visible flow

- real browser screenshot/DOM;
- console errors;
- failed network requests;
- typed API response;
- PostgreSQL row assertions;
- Observer trace/integrity result;
- support/requester projection consistency.

#### Agent/operation flow

- API/WS request and typed result;
- `operations`;
- `device_outbox`;
- `ticket_events`/`device_events`;
- agent SQLite outbox/seen state;
- agent/server logs;
- Observer trace/spans/signature;
- UI-visible operation result, если он существует.

#### DB/migration flow

- before/after head;
- schema assertion;
- transaction result;
- cleanup result;
- no unexpected persistent rows.

### E5. Before/after Observer gate

До scenario:

- запустить integrity scan с отдельным baseline run id;
- зафиксировать existing active/suppressed events.

После scenario:

- запустить scan с scenario run id;
- запросить связанные traces;
- сравнить delta.

Live pass запрещен при:

- новом active `critical/high/error`, связанном с run;
- missing required trace/span;
- checker failed/incomplete;
- trace status противоречит DB outcome;
- unexpected suppression;
- Observer writer failure;
- потерянной correlation.

### E6. Machine validator

Создать `scripts/validate_live_evidence.py`.

Validator проверяет:

- schema;
- commit parity;
- обязательные surfaces;
- существование artifacts;
- redaction flags;
- заполненность expected/actual;
- наличие DB и Observer checks;
- допустимые skips;
- отсутствие unresolved stop condition;
- cleanup complete;
- browser artifact для видимого flow.

Markdown остается human-readable приложением, но pass определяется JSON validator.

### E7. Stop conditions

Немедленно остановить live-run и пометить `blocked`, если:

- обнаружено новое нарушение целостности;
- auth/account boundary неоднозначна;
- deployed commit отличается;
- DB contamination смешалась с run;
- два последовательных probe дают разные API/DB/UI результаты;
- agent identity/device binding не доказаны;
- Observer scan incomplete;
- автоматизация собирается выполнить destructive действие вне выделенных test entities.

Restart/redeploy может быть диагностическим шагом, но не закрывает bug без root cause и regression proof.

### E8. Cleanup

Manifest обязан доказать:

- test tickets/operations/outbox очищены или помечены для controlled retention;
- test browser sessions завершены;
- временные users/bindings удалены;
- agent local queue не содержит run items;
- Observer contamination не была добавлена для сокрытия результата;
- remote services оставлены в документированном состоянии.

---

## 10. Workstream F — CI и release gates

### F1. Fast PR gate

Запускать:

1. `verify_workspace`;
2. scripts unit tests;
3. webapp unit/type/build;
4. affected server `no_db`;
5. affected DB domains;
6. fixture E2E для измененной UI-зоны;
7. cleanup/test inventory audits;
8. focused migration check при изменении migrations/models;
9. docs/link drift.

Fast gate не имеет права объявлять live readiness.

### F2. Full merge gate

Запускать все canonical layers:

- все server DB domains в изолированных БД;
- agent_ws;
- pc_agent;
- scripts;
- webapp unit/build/fixture E2E;
- migration/schema/cleanup audits;
- Observer integrity regression suite;
- JUnit aggregation;
- retry/flaky summary;
- duration regression report.

### F3. Nightly reliability gate

Запускать:

- full suite несколько раз с разным seed/order;
- concurrency tests;
- property/fuzz tests;
- migration from baseline snapshot;
- Observer volume tests выше query limits;
- cleanup contamination sentinel;
- test DB create/drop stress;
- slowest fixture comparison;
- flaky trend.

Никакой автоматической «починки» через повышение timeout без диагностических artifacts.

### F4. Release/live gate

Последовательность:

1. exact commit verification;
2. release/deploy;
3. health/schema preflight;
4. Observer baseline scan;
5. canary suite;
6. critical browser/agent scenarios;
7. DB/Observer reconciliation;
8. evidence validation;
9. cleanup;
10. final summary.

Gate выдает `green` только при совпадении commit, complete evidence и отсутствии новых blocking integrity events.

### F5. Метрики

Обязательные метрики:

- orphan tests: `0`;
- cleanup-unclassified tables: `0`;
- full gate shared DB runs: `0`;
- first-attempt pass rate;
- retry/flaky rate;
- p50/p95 duration по suite;
- top fixture setup/teardown;
- timed out/idle timed out;
- failed checker count;
- incomplete Observer scans;
- active critical/high integrity events;
- required Observer root-kind coverage;
- live scenarios без DB/Observer evidence: `0`;
- regression bugs без automated test: `0`.

Пороговые значения фиксировать после baseline, не выбирать произвольно.

---

## 11. Workstream G — bug fixing workflow

### G1. Карточка бага

Каждый bug должен иметь:

```text
Bug ID:
Severity:
Affected boundary:
First bad / last known good:
Environment:
Run ID:
Expected:
Actual:
Minimal reproduction:
API/WS evidence:
DB evidence:
Observer evidence:
UI/GUI evidence:
Root cause:
Fix:
Regression tests:
Live validation:
Contamination:
Residual risk:
```

### G2. Статусы

Использовать:

```text
open
reproduced
root-cause-confirmed
fix-in-progress
fixed-locally
verified-integration
verified-live
closed
blocked
```

`fixed-locally` не равно `closed`.

### G3. Обязательный порядок исправления

1. Зафиксировать failure artifact.
2. Определить первый расходящийся слой.
3. Написать минимальный failing test.
4. Исправить root cause, а не симптом.
5. Запустить focused test.
6. Запустить соседние contract layers.
7. Проверить DB/Observer invariants.
8. Для видимого/runtime изменения выполнить live scenario.
9. Сохранить evidence.
10. Обновить docs/CODEMAP/plan.
11. Закрыть bug только после проверки cleanup и residual risk.

### G4. Blocking bugs

Blocking:

- data loss/corruption;
- auth/privacy boundary;
- forged identity/target acceptance;
- duplicate side effect;
- ACK without persistence;
- false `resolved` integrity event;
- Observer leak of secrets/PII;
- migration/cleanup contamination;
- live/browser behavior не соответствует API/DB;
- release gate проверил не тот commit.

При blocking bug broad live-run останавливается; сначала создается минимальный reproducer и локализуется слой.

---

## 12. Workstream H — управление техническим долгом

### H1. Реестр

Каждая debt item имеет:

- `TD-ID`;
- owner zone;
- risk;
- affected contracts;
- evidence;
- trigger for escalation;
- target acceptance criteria;
- linked tests;
- status;
- last reviewed date.

### H2. Начальный backlog

| ID | Приоритет | Debt | Acceptance |
|---|---|---|---|
| `TD-001` | P0 | Observer bounded scan + global resolve | >limit regression green, no false resolve |
| `TD-002` | P0 | Manual DB cleanup inventory drift | schema audit green, all tables classified |
| `TD-003` | P0 | Scripts tests вне canonical CI | scripts suite blocking full gate |
| `TD-004` | P1 | Web trace identity coalesces executions | repeated/retry/error→success tests green |
| `TD-005` | P1 | Integrity checker orchestration all-or-nothing | per-check status, no resolve on incomplete |
| `TD-006` | P1 | Shared DB fallback неявен | explicit opt-in, release fail-closed |
| `TD-007` | P1 | Filename-based suite ownership | catalog + unowned audit |
| `TD-008` | P1 | Evidence pack не доказывает completeness | manifest v2 validator |
| `TD-009` | P2 | Fixture/API contract duplication | generated/schema-validated fixtures |
| `TD-010` | P2 | Retry скрывает first-attempt failure | flaky status/artifact/trend |
| `TD-011` | P2 | Hardcoded known contamination | owner/expiry/review gate |
| `TD-012` | P2 | Архивный risk document не связан с tests | актуализировать каждый active risk regression test |
| `TD-013` | P2 | Agent ACK/in-progress race из risk register | deterministic concurrency/restart tests |
| `TD-014` | P2 | Два run_tool entry paths | single facade contract test |
| `TD-015` | P3 | Single-process outbox dispatch scaling | load/locking design + multi-instance test plan |
| `TD-016` | P2 | Scheduler RPC historical NOT_IMPLEMENTED risk | scheduler runtime/admin RPC tests linked in `quality/active_risks.json` |
| `TD-017` | P2 | Legacy orchestrator execution branches | execution scheduler/action trace tests linked in `quality/active_risks.json` |
| `TD-018` | P3 | ModuleManager handshake inventory edge case | startup inventory + handshake reconcile tests linked in `quality/active_risks.json` |
| `TD-019` | P3 | SERVER_PUBLIC_BASE_URL production reachability | release/config evidence tracked in `quality/active_risks.json` |

### H3. Debt budget

Каждый feature/bug PR:

- не добавляет новую unclassified table;
- не добавляет unowned test;
- не добавляет Observer flow без coverage row;
- не увеличивает suppression count без review;
- не добавляет retry как единственное исправление flake;
- либо уменьшает debt, либо явно регистрирует новую debt item с acceptance criteria.

---

## 13. Фазы реализации

### Phase 0 — baseline и защита от false green

- [x] `QG-001` Добавить `scripts_pytest_no_db`.
- [x] `QG-002` Добавить strict test inventory audit.
- [x] `QG-003` Включить `audit_db_cleanup_profiles.py --strict`.
- [x] `QG-004` Сохранить baseline JUnit/durations/retries.
- [x] `QG-005` Маркировать fixture E2E отдельно от live browser.
- [x] `QG-006` Запретить release-pass на shared DB.

**Gate:** все существующие тесты имеют owner; scripts tests реально запускаются; DB mode виден в summary.

### Phase 1 — Observer и DB safety

- [x] `OBS-101` Написать >limit false-resolve regression.
- [x] `OBS-102` Реализовать complete-scope resolution.
- [x] `OBS-103` Сохранить acknowledged state при повторном scan.
- [x] `OBS-104` Добавить per-check execution report и failure isolation.
- [x] `OBS-105` Ужесточить successful create trace predicate.
- [x] `OBS-106` Characterize и исправить web execution trace identity.
- [x] `DB-101` Создать schema-to-cleanup audit.
- [x] `DB-102` Классифицировать все текущие tables.
- [x] `DB-103` Закрыть `change_*` и новый Knowledge cleanup drift.
- [~] `DB-104` Добавить migration suite.

**Gate:** incomplete checker не resolve-ит события; cleanup audit показывает zero drift; fresh/baseline migrations green.

### Phase 2 — behavioral contracts

- [x] `BEH-201` Requester create/block/no-device/on-behalf matrix.
- [x] `BEH-202` Chat retry/idempotency.
- [x] `BEH-203` Resolve/feedback/reopen.
- [x] `BEH-204` Support claim/status/SLA/privacy.
- [x] `BEH-205` Tool operation/outbox/result/ACK.
- [x] `BEH-206` Consent approve/deny/timeout/cancel race.
- [x] `BEH-207` Agent reconnect/replay/duplicate.
- [x] `BEH-208` Auth/account/session isolation.
- [x] `BEH-209` Knowledge/Registry audience rules.
- [x] `BEH-210` Observer non-mutation/redaction property tests.

**Gate:** каждый critical journey имеет API, DB и Observer assertions; visible journeys имеют fixture UI tests.

### Phase 3 — доказательный live gate

- [x] `LIVE-301` Ввести evidence manifest v2.
- [x] `LIVE-302` Реализовать validator.
- [x] `LIVE-303` Добавить exact commit/schema preflight.
- [x] `LIVE-304` Добавить before/after integrity delta.
- [x] `LIVE-305` Создать critical behavior data pack.
- [~] `LIVE-306` Автоматизировать requester/support browser scenarios.
- [~] `LIVE-307` Автоматизировать agent/operation scenarios.
- [x] `LIVE-308` Доказать cleanup.
- [x] `LIVE-309` Интегрировать Observer canary report.
- [ ] `LIVE-310` Сформировать один release summary.

**Gate:** pass невозможен без browser/API/DB/Observer evidence и commit parity.

### Phase 4 — надежность и скорость

- [x] `PERF-401` Test fixture timing budget.
- [x] `PERF-402` Domain-level bounded parallelism по измерениям.
- [x] `FLAKE-403` Retry/flaky registry.
- [x] `PROP-404` Property/state-machine tests.
- [~] `COV-405` Targeted branch coverage critical packages.
- [x] `MUT-406` Mutation testing для status/policy/redaction/idempotency pure logic.
- [x] `FIX-407` Schema-validated fixture builders.
- [x] `CI-408` Affected-suite selection с обязательным full merge gate.

**Gate:** ускорение не уменьшает coverage и не использует timeout/retry как маскировку.

### Phase 5 — управление активным техдолгом

- [x] `TD-501` Перенести active risks из архивного документа в реестр.
- [x] `TD-502` Закрыть ACK/in-progress race tests.
- [x] `TD-503` Унифицировать run_tool facade.
- [x] `TD-504` Удалить бессрочные contaminations.
- [x] `TD-505` Проверить Observer retention/query plans на объемах.
- [x] `TD-506` Обновить CODEMAP/QUICK_LOOKUP/TESTING_RULES.
- [x] `TD-507` Зафиксировать multi-instance outbox prerequisites.

**Gate:** у каждого active risk есть owner, test и measurable acceptance criteria. `[x]` в этой фазе означает governance/registry/gating, а не устранение всех underlying risks из `quality/active_risks.json`.

Checkpoint 2026-06-24 OBS-101/OBS-102/OBS-104: `93911118` перевел Observer integrity scan на fail-closed completeness contract, а `940b8252` закрыл focused DB proof для scan completeness. Top-level checkers возвращают `ObserverIntegrityCheckResult`, bounded checkers используют `LIMIT + 1` windows, `runtime_presence` возвращает incomplete при отсутствии state, unknown `source_complete` больше не resolve-ит source по умолчанию, runner source явно помечается complete, а DB regression доказывает 201/301/501 boundary и resolve-only-current behavior. Coverage: `server/tests/test_observer_integrity_scan_scope.py` passed (`8 passed in 0.31s`), `server/tests/test_observer_integrity_scan_completeness.py` passed in isolated PostgreSQL (`4 passed in 473.93s`). Remaining for P0 Observer scan completeness `[x]`: passing live release summary and release preflight/full gate on the current frozen commit/environment.

Checkpoint 2026-06-24 OBS-104: Observer integrity runner now has bounded per-check isolation/reporting. Each checker gets a timeout-bounded execution report with `passed|degraded|failed|timed_out`, started/finished/duration, scanned/window metadata, generated/active/suppressed/resolved counts and redacted error details; reports are persisted in `observer_integrity_check_runs` under a scan `scan_id` and returned by `POST /api/web/admin/observer/integrity/scan` in `checks`. Failed/timed-out checkers still create `observer.integrity_runner` self-health events, independent checkers continue, and source resolution is allowed only for checker reports with `status=passed` and `complete=true`. Coverage: RED/GREEN `server/tests/test_observer_integrity_scan_scope.py::test_run_scan_reports_checker_status_counts_and_resolves_only_passed_complete`, `::test_run_scan_times_out_slow_checker_and_does_not_resolve_source`, full no-DB scope suite (`10 passed in 0.34s`), isolated PostgreSQL `server/tests/test_observer_integrity_scan_completeness.py::test_run_scan_persists_per_checker_reports`, full DB completeness suite (`5 passed in 481.79s`), `scripts/test_navigation_catalog.py scripts/test_task_intake.py`, schema cleanup audit from models, docs drift and workspace sanity.

Checkpoint 2026-06-25 CI/P0: plain full CI for implementation commit `b3ac0d3abf1995119ca7772802b65f89383ecdf7` is green. Command: `python scripts/run_ci_suite.py --workspace . --commit b3ac0d3abf1995119ca7772802b65f89383ecdf7`; summary artifact `artifacts/ci/b3ac0d3abf1995119ca7772802b65f89383ecdf7/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=True`, and 21/21 passed steps. Observer scan completeness remains `[~]`, not `[x]`, because release preflight and the full live behavior pack still need to pass for the same frozen commit/environment.

Checkpoint 2026-06-25 P0 status refresh: frozen candidate is `66be2997b551027a0776d9587ac433117ab451b6`. P0 Observer scan completeness remains `[~]`: code-side and focused DB proof are present, exact full CI for this candidate is green, `artifacts/live/release-summary.json` exists but is `status=blocked`, the full `critical_behavior_v1` live pack still needs 17 passing v2 scenario manifests, and release preflight/full gate have not passed for the same commit/environment. Exact preflight command `python scripts/release_candidate_preflight.py --commit 66be2997b551027a0776d9587ac433117ab451b6 --environment stand --allow-local-dirty` finds green CI and webapp bundle, then rejects the live summary because all required scenarios are missing.

Checkpoint 2026-06-25 LIVE/P0 automation: `scripts/run_live_behavior_suite.py` default browser surfaces now cover `requester,support,admin,reports`; `webapp/scripts/live-browser-scenarios.mjs` has admin credentials plus registry, problems, changes, modules, playbooks, observer and reports probes; `scripts/build_live_release_summary.py` uses the same browser surface set for suite-plan counts. RED/GREEN coverage: `scripts/test_run_live_behavior_suite.py`, `scripts/test_build_live_release_summary.py`; dry-run now reports 14 browser scenarios and exact-context release summary reports 17 required scenarios, 17 missing manifests.

Checkpoint 2026-06-25 LIVE/P0 scaffold identity: `scripts/live_evidence_pack.py` now accepts `support`/`reports` surfaces plus `--scenario-key`, `--release-run-id`, exact commit, deployed commit, environment, branch and schema preflight fields. `scripts/run_live_behavior_suite.py --evidence-root ...` can create per-scenario blocked `pc_client.live_evidence.v2` manifest folders while planning/running critical behavior probes, so the remaining 17 live scenarios no longer need manual manifest identity edits before evidence fill-in. This does not close P0 Observer scan completeness: generated manifests are blocked until real preflight, API/DB, Observer delta, Observer canary, cleanup and browser/agent evidence are collected, validated and summarized as `pc_client.live_release_summary.v1 status=pass` for the same frozen commit/environment. Coverage: RED/GREEN `scripts/test_live_evidence_pack.py::test_live_evidence_pack_records_scenario_key_and_release_context`, `scripts/test_run_live_behavior_suite.py::test_dry_run_can_scaffold_live_evidence_pack_for_selected_scenario`; focused live tooling suite `scripts/test_live_evidence_pack.py scripts/test_run_live_behavior_suite.py scripts/test_build_live_release_summary.py scripts/test_validate_live_evidence.py` passed (`23 passed in 0.30s`).

Checkpoint 2026-06-25 CI/P0 current candidate refresh: frozen candidate is `f13e21dfa1b2af6162803171ed39698465d7c758`. Plain full `python scripts/run_ci_suite.py --workspace . --commit f13e21dfa1b2af6162803171ed39698465d7c758` is green: `artifacts/ci/f13e21dfa1b2af6162803171ed39698465d7c758/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=True`, and 21/21 passed steps. P0 Observer scan completeness remains `[~]`, not `[x]`: exact-context `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit f13e21dfa1b2af6162803171ed39698465d7c758 --environment stand --output artifacts/live/release-summary.json --markdown-output artifacts/live/release-summary.md --json` returns `status=blocked` with 17 missing required scenarios, and `python scripts/release_candidate_preflight.py --commit f13e21dfa1b2af6162803171ed39698465d7c758 --environment stand --allow-local-dirty` accepts green CI/webapp bundle but rejects that live summary. Side budget check: `python scripts/summarize_fixture_timings.py artifacts/ci/f13e21dfa1b2af6162803171ed39698465d7c758 --enforce-budget` fails because `run_migrations/setup` is `455.861032s`, above the 180s max and 120s p95 budgets; this is a residual fixture timing risk, not a full-CI failure.

Checkpoint 2026-06-25 CI/P0 live evidence matrix refresh: latest evidence candidate is `7cd3c92861997a5fcecdc013adb856bdf847d67d`. Plain full `python scripts/run_ci_suite.py --workspace . --commit 7cd3c92861997a5fcecdc013adb856bdf847d67d` is green: `artifacts/ci/7cd3c92861997a5fcecdc013adb856bdf847d67d/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=True`, and 21/21 passed steps, including the Observer diagnostics DB suite (`125 passed, 41 deselected`) and full agent/runtime/web API layers. Exact live scaffold for `release_run_id=critical-behavior-7cd3c928-20260625` now has 17/17 scenario folders: 14 browser scenarios from `run_live_behavior_suite.py --dry-run --evidence-root artifacts`, 2 agent/operation scenarios from `--mode agent-operation`, and the `canonical_stand_release_gate` manifest from `live_evidence_pack.py`. P0 Observer scan completeness remains `[~]`, not `[x]`: `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit 7cd3c92861997a5fcecdc013adb856bdf847d67d --environment stand --release-run-id critical-behavior-7cd3c928-20260625 --expected-schema-head 129 --output artifacts/live/release-summary.json --markdown-output artifacts/live/release-summary.md --json` returns `status=fail`, `passed_scenario_keys=[]`, `missing_scenario_keys=[]`, and all 17 `failed_scenario_keys` because each scaffolded manifest is still blocked/validation-fail without real preflight, Observer delta, Observer canary, checks/artifacts and cleanup evidence. `python scripts/release_candidate_preflight.py --commit 7cd3c92861997a5fcecdc013adb856bdf847d67d --environment stand --release-run-id critical-behavior-7cd3c928-20260625 --expected-schema-head 129 --allow-local-dirty` accepts the green CI and webapp bundle but rejects that live summary with `status='fail'` and all 17 failed scenarios. Side budget check remains open: `python scripts/summarize_fixture_timings.py artifacts/ci/7cd3c92861997a5fcecdc013adb856bdf847d67d --enforce-budget` fails because `run_migrations/setup` is `455.858967s`, above the 180s max and 120s p95 budgets; this is a residual fixture timing risk, not a full-CI failure.

Checkpoint 2026-06-25 QG/P1 suite catalog source of truth: `quality/test_suites.toml` is now the single CI/test-suite catalog for all 21 canonical layers, affected-suite base layers, server DB/API filename ownership, server source-prefix routing and DB/WS parallel group order. New `scripts/suite_catalog.py` loads the TOML for both `scripts/run_ci_suite.py` and `scripts/audit_test_inventory.py`; the runner rejects Python-only/catalog-order drift, and inventory audit no longer imports runner hardcoded DB routing. RED/GREEN coverage: `scripts/test_run_ci_suite.py::test_server_db_api_layer_paths_uses_workspace_suite_catalog` and `scripts/test_audit_test_inventory.py::test_inventory_audit_uses_workspace_suite_catalog_for_server_db_ownership` failed before the loader change and pass now; focused verification `python -m pytest scripts/test_run_ci_suite.py scripts/test_audit_test_inventory.py -q --tb=short` passed (`30 passed in 4.49s`). `P1/P2 suite catalog source of truth` is now `[x]`.

Checkpoint 2026-06-25 P1 web Observer execution identity: `auth.middleware.request_id_middleware` assigns a server-side `server_request_id` to each HTTP request and returns it as `X-Server-Request-ID`; web actor-context helpers pass `server_request_id`, optional client `request_id`/`correlation_id`, and durable execution keys to `server/observer/web_event_writer.py`. The writer now records these attrs and prefers `idempotency_key`/`operation_id`, then `server_request_id`, then client ids for execution identity; requester/support chat writes pass `message_id` as `idempotency_key`. Coverage: RED/GREEN `server/tests/test_web_event_writer_no_db.py::test_web_observer_actor_context_generates_server_request_id_without_client_header`; focused fast suite `server/tests/test_web_event_writer_no_db.py server/tests/test_auth_security.py` passed (`22 passed, 9 warnings in 1.29s`); DB/API regression `server/tests/test_requester_workspace_api.py::test_requester_distinct_messages_without_client_request_id_get_distinct_observer_traces` passed in focused isolated PostgreSQL (`1 passed in 474.87s`) and inside full CI on `66be2997b551027a0776d9587ac433117ab451b6` (`server_pytest_db_web_api`: `392 passed, 6 skipped, 301 deselected`). P1 web Observer execution identity is now `[x]`.

Checkpoint 2026-06-25 OBS-006/P1 occurrence semantics: `observer_integrity_events` now distinguishes scan observations from real repeated incidents. Migration `130` adds `scan_observation_count`, `recurrence_count` and `last_reopened_at`; existing legacy `occurrence_count` values are copied into `scan_observation_count`, while `occurrence_count` remains as a backward-compatible alias of `recurrence_count`. `ObserverIntegrityRepo.upsert_event()` increments observations for every repeated scan, preserves `acknowledged`, increments recurrence only when a `resolved` condition reappears, and records `last_reopened_at`. Admin/support Observer payloads and compact support ticket observer payloads expose the new fields. RED/GREEN evidence: `server/tests/test_observer_integrity_scan_scope.py::test_upsert_event_preserves_acknowledged_status_when_condition_persists` and `::test_upsert_event_counts_recurrence_only_when_resolved_condition_returns` failed before the repo change and pass now; focused Observer suite `python -m pytest server/tests/test_observer_integrity_scan_scope.py server/tests/test_observer_integrity.py::test_observer_integrity_protocol_gap_resolves_and_repeated_scan_dedupes server/tests/test_observer_integrity.py::test_observer_integrity_recurrence_count_increments_only_after_resolution -q --tb=short` passed (`13 passed in 466.76s`); support API serialization `python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary -q --tb=short` passed (`1 passed in 464.50s`); migration/schema contract `python -m pytest server/tests/test_migration_schema_contract.py -q --tb=short` passed (`4 passed in 466.34s`). `P1 integrity occurrence_count semantics` is now `[x]`.

Checkpoint 2026-06-25 CI/P0 latest candidate refresh after migration `130`: latest evidence candidate is `bd84158f7d120296e36fe06872fa2fb0e1681a36`. Plain full `python scripts/run_ci_suite.py --workspace . --commit bd84158f7d120296e36fe06872fa2fb0e1681a36` is red: `artifacts/ci/bd84158f7d120296e36fe06872fa2fb0e1681a36/summary.json` reports `status=red`. Passed layers before the blocker include `verify_workspace`, webapp bundle/unit/fixture E2E, CI audits, `migration_schema` (`4 passed in 466.69s`), `server_pytest_db_knowledge` (`194 passed, 35 deselected`), `server_pytest_db_tickets` (`401 passed, 75 deselected`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`; includes `test_observer_integrity_scan_completeness.py` and recurrence/dedupe tests), `server_pytest_db_agent_runtime` (`127 passed, 123 deselected`) and `server_pytest_db_web_api` (`392 passed, 6 skipped, 301 deselected`). The blocker is `server_pytest_agent_ws`: the log printed `server/tests/test_tool_started_event.py::test_tool_call_started_created_before_command PASSED [75%]`, then the CI wrapper terminated the step with `returncode=124`, `timed_out=True`, `timeout_reason=idle_timeout`, `duration_seconds=923.193`. P0 Observer scan completeness remains `[~]`, not `[x]`: code-side/focused DB proof and the Observer diagnostics full-CI layer are green, but exact full CI, live release summary and release preflight have not passed for the same commit/environment. Next required action is to diagnose/rerun/fix the WS idle timeout, then rebuild exact live release summary/preflight with `--expected-schema-head 130`.

Checkpoint 2026-06-25 CI/P0 agent_ws selected rerun: `python scripts/run_ci_suite.py --workspace . --commit df3023ecc5f6466852d92fc7061ce44a27dd8ee3 --layer server_pytest_agent_ws` passed after template preparation completed. Summary `artifacts/ci/df3023ecc5f6466852d92fc7061ce44a27dd8ee3/summary.json` reports `status=green`, `gate_mode=selected`, `full_merge_gate_satisfied=false`, `timed_out=false`, `duration_seconds=862.872`; pytest log reports `29 passed, 1797 deselected in 857.82s`. Fixture timing shows `db_template_prepare` took `448.962791s`, followed by template clone and skipped-template migrations. This resolves the immediate selected WS-layer rerun, but does not close P0 Observer scan completeness: latest exact full CI still needs a new plain full gate, and exact live release summary/preflight/full gate still need passing evidence for the same commit/environment.

Checkpoint 2026-06-25 CI/P0 latest candidate green full gate: latest evidence candidate is `5ef5136dec8d621b6a82409c58dd6714694820f3`. Plain full `python scripts/run_ci_suite.py --workspace . --commit 5ef5136dec8d621b6a82409c58dd6714694820f3` is green: `artifacts/ci/5ef5136dec8d621b6a82409c58dd6714694820f3/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, and 21/21 passed steps. Key P0-relevant layers include `migration_schema` (`4 passed in 467.30s`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`, including scan completeness tests), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`). Exact preflight `python scripts/release_candidate_preflight.py --workspace . --commit 5ef5136dec8d621b6a82409c58dd6714694820f3 --environment stand --expected-schema-head 130 --allow-local-dirty` accepts the green CI artifact and webapp bundle, then rejects stale failing `artifacts/live/release-summary.json` from `7cd3c92861997a5fcecdc013adb856bdf847d67d` because it is `status='fail'`, has `expected_schema_head='129'`, and contains 17 failed scenario keys. P0 Observer scan completeness remains `[~]`, not `[x]`: code-side/focused DB/full-CI proof is now complete, but a passing exact-context `pc_client.live_release_summary.v1`, release preflight and full release gate are still required for `5ef5136dec8d621b6a82409c58dd6714694820f3`/`stand`/schema head `130`.

Checkpoint 2026-06-25 CI/P0 current HEAD plan refresh: latest verified implementation revision is `a0b47ee1a28f8168c753c87aea913ab9287039e1`. Plain full `python scripts/run_ci_suite.py --workspace . --commit a0b47ee1a28f8168c753c87aea913ab9287039e1` is green: `artifacts/ci/a0b47ee1a28f8168c753c87aea913ab9287039e1/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, `flaky_summary.status=pass`, `clean_green=true`, and 21/21 passed steps. Key P0-relevant layers include `migration_schema` (`4 passed in 467.15s`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`, including `test_operation_lifecycle_marks_incomplete_when_limit_plus_one_rows_are_filtered`, `test_web_cabinet_marks_incomplete_at_ticket_limit_plus_one`, `test_runtime_presence_marks_incomplete_at_device_limit_plus_one`, `test_run_scan_resolves_only_current_missing_event_after_complete_db_scan` and `test_run_scan_persists_per_checker_reports`), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`). Exact preflight `python scripts/release_candidate_preflight.py --workspace . --commit a0b47ee1a28f8168c753c87aea913ab9287039e1 --environment stand --expected-schema-head 130 --allow-local-dirty` accepts the green CI artifact and webapp bundle, then rejects stale failing `artifacts/live/release-summary.json` from `7cd3c92861997a5fcecdc013adb856bdf847d67d`/schema head `129`. Exact-context summary probe `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit a0b47ee1a28f8168c753c87aea913ab9287039e1 --environment stand --expected-schema-head 130 --json` returns `status=blocked` because all 17 critical scenarios still lack passing live evidence manifests. P0 Observer scan completeness is explicitly `[~]`, not `[x]`: code-side/focused DB/full-CI proof is complete for the verified implementation revision, but passing `pc_client.live_release_summary.v1`, release preflight and full release gate remain required on the same commit/environment.

Checkpoint 2026-06-26 CI/P0 current verified checkpoint refresh: latest verified P0/CI checkpoint is `2b18e79b8530e6386550e2b0978161b54bb991b2`. Plain full `python scripts/run_ci_suite.py --workspace . --commit 2b18e79b8530e6386550e2b0978161b54bb991b2` is green: `artifacts/ci/2b18e79b8530e6386550e2b0978161b54bb991b2/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, `flaky_summary.status=pass`, `clean_green=true`, and 21/21 passed steps. Key P0-relevant layers include `migration_schema` (`4 passed in 464.20s`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`, including scan completeness tests), `server_pytest_db_agent_runtime` (`127 passed, 123 deselected`), `server_pytest_db_web_api` (`392 passed, 6 skipped, 301 deselected`), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`). Exact-context summary probe `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit 2b18e79b8530e6386550e2b0978161b54bb991b2 --environment stand --expected-schema-head 130 --json` returns `status=blocked` because all 17 critical behavior scenarios lack passing live evidence manifests. Exact preflight `python scripts/release_candidate_preflight.py --workspace . --commit 2b18e79b8530e6386550e2b0978161b54bb991b2 --environment stand --expected-schema-head 130 --allow-local-dirty` accepts the green CI artifact and webapp bundle, then rejects stale failing `artifacts/live/release-summary.json` from `7cd3c92861997a5fcecdc013adb856bdf847d67d`/schema head `129`. P0 Observer scan completeness remains `[~]`, not `[x]`: code-side/focused DB/full-CI proof is complete for the current verified checkpoint, but passing `pc_client.live_release_summary.v1`, release preflight and full release gate remain required on the same commit/environment.

Checkpoint 2026-06-26 LIVE/P0 first exact live slice: stand was updated to committed revision `ba64229a2c91dab2f6eb22dc8ecdbc27d45d3eda` with `python scripts\release_server_to_remote.py --workspace . --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --environment stand --release-run-id critical-behavior-ba64229a-20260626 --expected-schema-head 130`; remote migrations reached schema head `130` and HTTPS smoke passed. A false live-browser blocker was fixed in `webapp/scripts/live-browser-scenarios.mjs`: `ensureLoggedIn()` now waits for visible login/password inputs after protected-route redirect and React hydration. Coverage: `node --check webapp/scripts/live-browser-scenarios.mjs` and `python -m pytest scripts/test_run_live_behavior_suite.py -q` passed (`7 passed`). First real `critical_behavior_v1` scenario slice ran with `python scripts/run_live_behavior_suite.py --pack test_data_packs/critical_behavior_v1.json --scenario-key requester_support_admin_session_switch --surfaces requester --base-url https://192.168.100.17:9443 --out-dir artifacts/live_behavior_suite/critical-behavior-ba64229a-20260626 --evidence-root artifacts --release-run-id critical-behavior-ba64229a-20260626 --commit ba64229a2c91dab2f6eb22dc8ecdbc27d45d3eda --deployed-commit ba64229a2c91dab2f6eb22dc8ecdbc27d45d3eda --environment stand --branch codex/helpdesk-process-model --expected-schema-head 130 --actual-schema-head 130 --json`; browser report passed for `/app/requester` and `/app/support`, both probes had `loginSubmitted=true`, expected text matched and console/page errors were zero. The scenario manifest `artifacts/live/critical-behavior-ba64229a-20260626__requester_support_admin_session_switch/manifest.json` records API/browser partial evidence plus `api-login-check.json`, but remains `status=blocked`; `python scripts/validate_live_evidence.py --manifest artifacts/live/critical-behavior-ba64229a-20260626__requester_support_admin_session_switch/manifest.json` still fails on missing finished/preflight, Observer delta/canary, contamination and cleanup evidence. Exact `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit ba64229a2c91dab2f6eb22dc8ecdbc27d45d3eda --environment stand --release-run-id critical-behavior-ba64229a-20260626 --expected-schema-head 130 --output artifacts/live/release-summary.json --markdown-output artifacts/live/release-summary.md --json` remains `status=fail`, with `missing_scenario_keys=[]`, `passed_scenario_keys=[]`, and all 17 scenario keys still failed. P0 Observer scan completeness remains `[~]`, not `[x]`.

Checkpoint 2026-06-26 CI/P0 live-runner fix checkpoint: latest verified P0/CI checkpoint is `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` (`scripts: wait for live browser login inputs`). Plain full `python scripts/run_ci_suite.py --workspace . --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` is green: `artifacts/ci/ffa831a4ee84bf0e2897a8a96e9423acb2a0605a/summary.json` reports `status=green`, `gate_mode=full`, `full_merge_gate_satisfied=true`, `flaky_summary.status=pass`, `clean_green=true`, and 21/21 passed steps. Key P0-relevant layers include `migration_schema` (`4 passed`), `server_pytest_db_observer_diagnostics` (`126 passed, 42 deselected`, including scan completeness tests), `server_pytest_db_tickets` (`401 passed, 75 deselected`), `server_pytest_db_agent_runtime` (`127 passed, 123 deselected`), `server_pytest_db_web_api` (`392 passed, 6 skipped, 301 deselected`), `server_pytest_agent_ws` (`29 passed, 1797 deselected`) and `pc_agent_pytest` (`482 passed, 4 deselected, 7 subtests passed`). Stand was then fast-forwarded to `ffa831a4ee84bf0e2897a8a96e9423acb2a0605a` with quick deploy `python scripts\release_server_to_remote.py --workspace . --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --environment stand --release-run-id critical-behavior-ffa831a4-20260626 --expected-schema-head 130`; remote migrations stayed at schema head `130` and HTTPS smoke passed. The first exact live slice for `requester_support_admin_session_switch` required resetting the selected requester/support test passwords through `/api/web/admin/access/users/{login}/password` with cookie auth and CSRF Origin; API login checks then returned HTTP 200 with requester/user and support/support roles, and browser probes passed for `/app/requester` and `/app/support` with expected Russian markers and no console/page errors. The exact scenario manifest `artifacts/live/critical-behavior-ffa831a4-20260626__requester_support_admin_session_switch/manifest.json` now links `api-login-check.json`, `browser-report.json` and screenshots, but intentionally remains `status=blocked`. `python scripts/validate_live_evidence.py --manifest artifacts/live/critical-behavior-ffa831a4-20260626__requester_support_admin_session_switch/manifest.json` still fails on 22 missing evidence requirements, mainly finished timestamp, Observer delta, Observer canary, contamination and cleanup. Exact-context live summary `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit ffa831a4ee84bf0e2897a8a96e9423acb2a0605a --environment stand --release-run-id critical-behavior-ffa831a4-20260626 --expected-schema-head 130 --output artifacts/live/release-summary.json --markdown-output artifacts/live/release-summary.md --json` returns `status=fail`, with `failed_scenario_keys=['requester_support_admin_session_switch']` and 16 `missing_scenario_keys`. Additional Observer canary attempt for the same scenario wrote `observer-canary.json` and `observer-canary-report.md`, but failed before coverage collection: `run_observer_canary_suite.py --source-coverage-only` posts to `/api/ui_login`, and stand returns HTTP 410 `LEGACY_AUTH_DISABLED` because legacy token login is disabled in favor of `/api/web/session/login`. Exact preflight accepts the green CI artifact and webapp bundle, then rejects the failing live summary. P0 Observer scan completeness remains `[~]`, not `[x]`: code-side/focused DB/full-CI proof is complete for the current verified checkpoint, but modernized Observer canary auth plus passing `pc_client.live_release_summary.v1`, release preflight and full release gate remain required on the same commit/environment.

Checkpoint 2026-06-26 Observer canary auth refresh: local `scripts/run_observer_canary_suite.py` no longer posts to disabled `/api/ui_login`; it authenticates through `/api/web/session/login`, extracts the `pc_client_web_session` cookie from the diagnostic client, and reuses that UI token for the existing canary bearer calls. Targeted tests are green: `python -m pytest scripts/test_run_observer_canary_suite.py -q --tb=short` (`18 passed`) and `python -m pytest server/tests/test_auth_security.py::test_legacy_ui_login_disabled_by_default server/tests/test_web_session_api.py::test_web_session_login_sets_http_only_cookie -q --tb=short` (`2 passed`). Live source coverage proof on stand is green: `python scripts/run_observer_canary_suite.py --source-coverage-only` wrote `artifacts/observer_canaries/observer_canary_20260626_074728.json`, `coverage.ok=true`, with all 9 source root kinds observed and no missing root kinds. P0 Observer scan completeness remains `[~]`, not `[x]`, because exact live release summary, release preflight and full release gate are still not passing for the same frozen commit/environment.

Checkpoint 2026-06-24 TD-504: Observer known contamination is now manifest-owned in `quality/observer_known_contamination.json` instead of a hardcoded indefinite runtime list. `scripts/audit_observer_contamination.py --strict` and CI layer `observer_contamination_audit` fail active rows without owner, linked issue, exact scope, reason, created/expiry dates, review status or evidence path, and fail expired or broad suppressions. Runtime seeding reads the manifest, updates old NULL-expiry DB rows with the manifest expiry, and `ObserverIntegrityRepo.find_contamination()` no longer treats `expires_at=NULL` as a match. Current reviewed rows are three exact historical P0/P1/P6 entries, all expiring on 2026-07-24.

Checkpoint 2026-06-24 TD-505: Observer retention/search/detail volume paths now have an explicit no-DB query-plan contract in `server/tests/test_observer_query_plan_no_db.py` and Alembic revision `128`. The contract keeps retention cleanup on `observer_traces(status, started_at)`, trace list filters on `(root_kind|ticket_id|device_id|operation_id|job_id, started_at)`, trace detail/span filters on `observer_spans(trace_id, started_at|tool_name|module_name|event_type)`, and error/detail/signature stats on `observer_error_occurrences(trace_id, created_at|error_kind|error_signature)` plus `(ticket_id, error_signature, created_at)`. Coverage: RED/GREEN focused test, model metadata indexes, and idempotent migration `server/app/db/migrations/versions/20260624_128_observer_query_plan_indexes.py`.

Checkpoint 2026-06-24 TD-506: CODEMAP, QUICK_LOOKUP and TESTING_RULES now name the same CI gate set for the quality/Observer work: `test_inventory_audit`, `db_cleanup_profile_audit`, `fixture_builder_audit`, `active_risk_audit`, `observer_contamination_audit`, `branch_coverage_audit`, `mutation_smoke`, `migration_schema`, `scripts_pytest_no_db`, server pytest layers and agent/webapp layers. The docs also route Observer retention/query-plan work to `server/tests/test_observer_query_plan_no_db.py` and migration `128`, so future docs/context lookup no longer omits active-risk or contamination gates.

Checkpoint 2026-06-24 TD-507: DeviceOutbox multi-instance dispatch remains blocked as `single_process_only` until the prerequisites in `quality/outbox_multi_instance_prerequisites.json` pass. TD-015 is now an accepted active-risk gate with explicit DB coordination, lock ownership, agent connection ownership, lease recovery and multi-instance test-plan requirements. Guard coverage is `server/tests/test_outbox_multi_instance_prerequisites.py` plus the existing single-process dispatcher tests; no horizontal dispatch behavior was enabled in this step.

---

## 14. Первый execution slice

Выполнять в таком порядке:

1. [x] `server/tests/test_observer_integrity_scan_scope.py` — reproducer `limit + 1`.
2. [x] Исправление resolution API без изменения доменной логики.
3. [x] `scripts/test_db_cleanup_schema.py` + dynamic audit.
4. [x] Добавление отсутствующих DB classifications/profiles.
5. [x] `scripts_pytest_no_db` в CI и тест состава шагов.
6. [x] Tests acknowledgement lifecycle и failed-checker behavior.
7. [x] Tests web trace repeated/retry/error→success.
8. [x] Strict successful create-trace predicate.
9. [x] Evidence manifest v2 validator.
10. [x] Один pilot live journey: requester create → ticket DB → Observer trace → real browser → cleanup.

Checkpoint 2026-06-23: items 1-10 are implemented locally. Live pilot `quality-observer-pilot-4cf3137c-20260623` used deployed commit `4cf3137ce085c0b772ac1599ae960f7c6cd456a1`, browser requester create `T-000783`, DB/Observer proof, exact cleanup dry-run/apply/verify, and a passing `pc_client.live_evidence.v2` manifest under `artifacts/live/quality-observer-pilot-4cf3137c-20260623/`.

Checkpoint 2026-06-23 QG-002: `scripts/audit_test_inventory.py --strict` is implemented and wired into `scripts/run_ci_suite.py` as `test_inventory_audit` before pytest layers. Current inventory audit reports 422 test files, all owned by canonical suites, with zero strict issues.

Checkpoint 2026-06-23 QG-003: `scripts/audit_db_cleanup_profiles.py --strict` is wired into `scripts/run_ci_suite.py` as `db_cleanup_profile_audit` before pytest layers. Current strict cleanup-profile audit reports 304 server test files, 0 missing profiles, 64 no_db files and 7 likely_agent_ws skips; mixed `web_api` DB-backed files are explicitly marked `db_cleanup("full")` instead of being forced into unsafe narrow profiles.

Checkpoint 2026-06-23 QG-006: `scripts/ci_artifacts.py::require_green_ci_artifact` rejects otherwise-green CI summaries when any server DB/WS layer log contains a shared-test-DB fallback marker. Release preflight, deploy and full release gates now cannot use shared `pc_support_test` fallback as release-pass evidence; rerun full CI with `TEST_DATABASE_ADMIN_URL` and isolated `pc_support_test_<runid>` databases.

Checkpoint 2026-06-23 QG-004: `scripts/run_ci_suite.py` now writes `summary.baseline_artifacts` with canonical JUnit XML paths, pytest duration baselines, fixture timing artifacts and Playwright fixture retry policy. `pc_agent_pytest` now also runs with `-vv --durations=80 --junitxml`, and fixture E2E records `ci_retries=1`, `trace=on-first-retry` and `passed_after_retry_status=flaky`.

Checkpoint 2026-06-24 FLAKE-403: `scripts/run_ci_suite.py` now enforces a tracked retry/flaky registry at `quality/flaky_registry.json`. The `webapp_fixture_e2e` layer runs Playwright with `--reporter=list,json`, writes `artifacts/ci/<sha>/playwright-webapp-fixture-e2e.json`, and records `summary.flaky_summary` with `passed_after_retry` node ids, first/final statuses, worker indexes, previous error and trace/video/log attachments. Unknown or invalid retry-pass records turn the CI summary red; registry-matched records remain flaky evidence and never become clean green. Coverage: RED/GREEN `scripts/test_run_ci_suite.py::test_flaky_summary_fails_unknown_retry_pass` and `::test_flaky_summary_allows_registry_match_without_clean_green`, plus full `scripts/test_run_ci_suite.py`.

Checkpoint 2026-06-24 PROP-404: `server/tests/test_property_state_contracts_no_db.py` adds deterministic property/state-machine coverage without a new dependency. The pack checks Observer redaction over nested dict/list/tuple/set payloads for non-mutation, idempotency, safe hash/id preservation and secret removal; ticket status normalization for canonical/legacy/strict-vs-soft mode invariants; and workflow profile FSM graphs for valid allowed-status edges, suggested path validity, requester transition boundaries, reachable terminal states and default profile serialization round-trips. Coverage: RED/GREEN focused module run, then `server_pytest_no_db` ownership via inventory audit.

Checkpoint 2026-06-24 COV-405: `quality/critical_branch_coverage.json` now records targeted branch coverage for critical pure logic in `shared/redaction.py`, `server/tickets/statuses.py` and `server/tickets/workflow_profiles.py`. `scripts/audit_branch_coverage.py --strict` validates schema, package owners, unique branch ids, non-empty `tested_by` refs and existing pytest node ids, and `scripts/run_ci_suite.py` runs it as `branch_coverage_audit` before pytest layers. Current registry covers 3 packages and 9 branch records with zero audit issues. Coverage: RED/GREEN `scripts/test_audit_branch_coverage.py`, `scripts/test_run_ci_suite.py`, and strict audit output.

Checkpoint 2026-06-24 MUT-406: `quality/mutation_smoke_targets.json` and `scripts/run_mutation_smoke.py` add targeted temp-workspace mutation smoke for critical pure logic without mutating the real working tree. The runner copies `server/shared/scripts/quality/mcp_helpdesk_server` into a temp workspace, applies exact source replacements, runs configured pytest node ids, treats only assertion failures as killed mutants, and fails on survivors or collection/infrastructure errors. Current registry has 4 mutants covering bearer scalar redaction, safe token hash evidence, strict status FSM aliases and workflow self-loop policy; `python scripts/run_mutation_smoke.py --json --timeout 60` kills all 4, and `scripts/run_ci_suite.py --layer mutation_smoke` passes. Coverage: RED/GREEN `scripts/test_run_mutation_smoke.py` and runner step tests.

Checkpoint 2026-06-24 FIX-407: `quality/fixture_builders.json`, `scripts/fixture_schema_builders.py` and `scripts/audit_fixture_builders.py` add schema-validated fixture/data-pack builders for `test_data_packs/web_first_phase_e.json` and `test_data_packs/critical_behavior_v1.json`. The strict audit validates registry shape, JSON Schema contracts, duplicate fixture keys, source-pack refs, automated test refs, live scenario data refs, required live evidence/manifest requirements and secret-free payloads. `scripts/run_ci_suite.py` runs it as `fixture_builder_audit` before branch coverage and mutation smoke. Coverage: RED/GREEN `scripts/test_audit_fixture_builders.py`, runner step tests, `python scripts/audit_fixture_builders.py --strict --json` and `python scripts/run_ci_suite.py --layer fixture_builder_audit --idle-timeout 30`.

Checkpoint 2026-06-24 CI-408: `scripts/run_ci_suite.py` now supports affected-suite selection through `--changed-path <path>` and `--affected-from <git-ref>`. Affected runs select the base fast-gate layers plus mapped server DB domains, server no-DB, webapp fixture E2E, migration schema or pc_agent layers based on changed paths; unknown non-generated paths fall back to the full canonical layer list. CI summaries now record `gate_mode`, `effective_layers`, `affected_selection`, `full_merge_gate_required` and `full_merge_gate_satisfied`. `scripts/ci_artifacts.py` rejects green affected or `--layer` summaries for release/deploy full-gate evidence; only a green plain full `python scripts/run_ci_suite.py` artifact satisfies the full merge gate. Coverage: RED/GREEN `scripts/test_run_ci_suite.py` affected-selection tests, `scripts/test_ci_artifacts.py` full-gate rejection test, and full runner/artifact helper test modules.

Checkpoint 2026-06-23 QG-005: `scripts/run_ci_suite.py` writes `summary.evidence_layers.webapp_fixture_e2e` with `mode=fixture_e2e` and `canonical_live_browser=false`. Playwright fixture E2E remains a CI/browser-fixture layer and cannot be confused with live browser signoff evidence from `docs/LIVE_TESTING_DEBUG_RULES.md`.

Checkpoint 2026-06-23 DB-104: `server/tests/test_migration_schema_contract.py` is wired into `scripts/run_ci_suite.py` as the `migration_schema` layer with `PC_CLIENT_TEST_DB_TEMPLATE=0`, `junit-migration-schema.xml` and fixture timing artifacts. The layer proves direct empty-DB Alembic upgrade to exact heads, idempotent repeated `upgrade head`, actual migrated schema vs SQLAlchemy metadata plus explicit migration-only allowlist, DB cleanup schema zero drift, required constraints/indexes/defaults including nullable no-device ticket columns, and smoke insert/select/delete for recent runtime tables. The first strict migration run found missing cleanup coverage for `knowledge_article_segments`, `knowledge_segmentation_*`, `ticket_*_archive` and `ticket_retention_runs`; cleanup classification/static full-cleanup coverage is now updated and `scripts/audit_db_cleanup_schema.py --schema-from-models --strict` reports zero drift.

Checkpoint 2026-06-23 BEH-201: `server/tests/test_requester_workspace_api.py` now carries an API + DB + Observer matrix for requester create paths: no-agent normal-form block (`REQUESTER_AGENT_REQUIRED`), no-device preview/create, on-behalf out-of-scope deny (`ON_BEHALF_SCOPE_DENIED`), and authorized on-behalf create. `server/web_api/requester_handlers.py` writes redacted `requester_web` Observer traces for requester preview/create block paths (`ticket_preview_blocked`, `ticket_create_blocked`) without raw person/device/request payloads. Focused verification: four BEH-201 scenarios passed in one DB-backed run.

Checkpoint 2026-06-23 BEH-202: requester and support chat endpoints now treat API retries with the same `message_id` as idempotent. A duplicate `message_id` resolves the already persisted `chat_message` and returns its original event id instead of creating a second row; retry responses do not repeat requester workflow transitions, support first-response SLA closure, Observer writes, or realtime pushes. Coverage is `test_requester_ticket_message_retry_is_idempotent_by_message_id` and `test_web_support_message_retry_is_idempotent_by_message_id`.

Checkpoint 2026-06-23 BEH-203: requester lifecycle actions now keep feedback/reopen consistent with Quality Loop policy. Latest positive feedback disables `actions.can_reopen` and blocks direct requester `/reopen`; latest low-CSAT feedback still permits reopen and records `ticket_reopen_events`. Existing requester close/feedback/reopen Observer tests cover redacted `requester_closure` lifecycle traces for `closure_confirmed`, `feedback_submitted` and `ticket_reopened`.

Checkpoint 2026-06-23 BEH-204: support assignment now writes a redacted web-cabinet Observer trace `source=support_assignment`, `event_type=support_assignment_changed`, and typed support detail projects it as `observer.web_flow.support_assignment`. The BEH-204 matrix now covers support assign Observer redaction, status/confirmation Observer redaction, support chat retry idempotency, and first-response SLA/privacy behavior: internal support notes do not stop FRT or project into requester timeline fields, while the first public support reply stops FRT once and returns requester-safe projection fields.

Checkpoint 2026-06-24 BEH-205/TD-502: Protocol V3 agent recovery now handles an incoming duplicate command whose `seen_commands.status='in_progress'` row belongs to a previous runtime before the normal startup replay path runs. The agent converts that row to a durable terminal `command_result` with `error.code=AGENT_RESTARTED`, queues it in `pending_command_results` until `command_result_ack`, sends no `command_ack`, and does not rerun the side-effecting tool. Coverage: `pc_agent/tests/test_command_restart_recovery.py::test_previous_runtime_in_progress_command_recovers_without_ack_or_rerun` plus the existing restart replay, pending ACK cleanup, controlled retry metadata and canceled-command idempotency tests.

Checkpoint 2026-06-23 BEH-206: `UserConsentService` now re-checks the linked operation before applying browser/agent approve or deny. If an operation consent is still pending but the operation already reached `cancel_requested`, `canceled`, `denied`, `failed`, `succeeded` or `timed_out`, the server atomically marks the consent `canceled`, writes `user_consent_canceled`, and skips both `ConsentDecision` and `DeviceOutbox` side effects. `OperationService.approve_consent()` / `deny_consent()` also write `ConsentDecision` only after the guarded operation transition succeeds. Coverage: requester approve-after-cancel and deny-after-timeout paths in `server/tests/test_user_consent_api.py::test_requester_decision_after_operation_no_longer_actionable_cancels_consent_without_side_effects`.

Checkpoint 2026-06-23 BEH-207: agent duplicate terminal command responses now use the durable `pending_command_results` path before sending. If a cached `success`/`canceled` result or cached/recovered `AGENT_RESTARTED` result is redelivered and the websocket drops during duplicate-send, the result remains queued for reconnect replay until `command_result_ack`. Coverage: `pc_agent/tests/test_command_restart_recovery.py::test_cached_terminal_duplicate_send_failure_remains_pending_for_replay` plus command-result replay/ACK cleanup, seen-command retry policy, canceled-command idempotency and server `command_result_ack` tests.

Checkpoint 2026-06-24 BEH-208: React web-session state now treats bootstrap, refresh, login and logout as ordered account transitions. A delayed `/api/web/session/me` bootstrap for a previous account cannot overwrite a newer successful login/logout state, which closes the account-switch stale UI bootstrap case while server-side `AuthContext`, cookie, account-session and requester visibility boundaries remain authoritative. Coverage: RED/GREEN `webapp/src/features/auth/session-provider.test.tsx::ignores stale bootstrap responses after a newer login succeeds` plus existing web-session logout/revoke/CSRF and requester/account-session isolation tests.

Checkpoint 2026-06-24 BEH-209: Knowledge search analytics now redacts requester PII and Registry identifiers from stored `query_text_redacted` before zero-result/gap analytics. The redactor keeps query hashes for aggregation but removes raw emails, phone numbers, person/account-session/ticket ids and secret-like key/value markers while existing audience-rule enforcement continues to filter search, suggestions, portal, Ask/RAG and support suggestions before projection. Coverage: RED/GREEN `server/tests/test_knowledge_contract_no_db.py::test_search_analytics_redaction_removes_registry_ids_phone_and_secret_markers` plus `server/tests/test_knowledge_access_service.py` department-tree/audience-group contract tests.

Checkpoint 2026-06-24 BEH-210: Observer redaction helpers now treat `collections.abc.Mapping` payloads like normal dicts, returning a new redacted dict without mutating the original custom mapping. This closes the custom-mapping branch of the C6 nested payload matrix and adds a pure non-mutation assertion for Observer redaction before detail/export writers consume the payload. Coverage: RED/GREEN `server/tests/test_observer_redaction_no_db.py::test_observer_redaction_handles_custom_mapping_without_mutating_input` plus existing web event writer and integrity no-DB observer tests.

Checkpoint 2026-06-24 LIVE-303: `pc_client.live_evidence.v2` manifests now require an explicit `preflight` block for branch, local/deployed commit, expected/actual schema head, schema status, service health and `checked_at`. The validator enforces commit parity across top-level and preflight fields, rejects deployed/local commit drift, requires actual schema head to match expected head, and blocks non-pass schema/health preflight statuses. `scripts/live_evidence_pack.py` scaffolds the preflight block with blocked placeholders so draft manifests remain invalid until exact commit/schema evidence is filled. Coverage: RED/GREEN `scripts/test_validate_live_evidence.py::test_validate_live_evidence_requires_commit_schema_preflight` and `::test_validate_live_evidence_rejects_commit_or_schema_preflight_mismatch`, plus `scripts/test_live_evidence_pack.py`.

Checkpoint 2026-06-24 LIVE-304: `pc_client.live_evidence.v2` manifests now require `observer_delta` with separate baseline/scenario integrity scan ids, before/after active and suppressed event refs, stop-condition delta refs, required/linked/missing trace ids, DB/trace consistency, checker/writer/correlation statuses and `checked_at`. The validator blocks live pass when a scan is incomplete, new active critical/high/error refs appear, unexpected suppressions appear, required traces are missing, trace outcome contradicts DB outcome, Observer writer/correlation is not pass, or baseline/scenario run ids are not separate. `scripts/live_evidence_pack.py` now creates `observer-delta.md` and a blocked `observer_delta` scaffold. Coverage: RED/GREEN `scripts/test_validate_live_evidence.py::test_validate_live_evidence_requires_observer_integrity_delta` and `::test_validate_live_evidence_rejects_observer_integrity_delta_stop_conditions`, plus `scripts/test_live_evidence_pack.py`.

Checkpoint 2026-06-24 LIVE-305: `test_data_packs/critical_behavior_v1.json` now defines a versioned `pc_client.critical_behavior_data_pack.v1` for Workstream D critical behavior live gates. The pack covers all 17 domain records from the matrix with owners, critical invariants, existing automated test refs, live scenario refs, mandatory API/DB/Observer/live-manifest evidence, browser evidence for visible scenarios and required `preflight`/`observer_delta` manifest sections. It references `test_data_packs/web_first_phase_e.json` for shared users/agents/forms and contains no raw secret fields. Coverage: RED/GREEN `server/tests/test_critical_behavior_data_pack.py`.

Checkpoint 2026-06-24 LIVE-306: `scripts/run_live_behavior_suite.py` now reads `test_data_packs/critical_behavior_v1.json`, selects requester/support live scenarios that require browser evidence, and builds/runs per-scenario commands for `webapp/scripts/live-browser-scenarios.mjs`. The Node Playwright probe uses real `/app/requester`, `/app/requester/tickets`, `/app/requester/new`, `/app/help`, `/app/support` and `/app/tickets` routes without `page.route()` mocks, logs in with role-specific environment credentials, captures screenshots plus DOM snippets, checks Russian page/title markers, and fails on console/page errors. Dry-run output lists eight requester/support browser scenarios and their exact commands; full live pass still requires API/DB/Observer evidence in the v2 manifest. Coverage: RED/GREEN `scripts/test_run_live_behavior_suite.py`, dry-run `python scripts/run_live_behavior_suite.py --pack test_data_packs/critical_behavior_v1.json --surfaces requester,support --dry-run --json`, and `node --check webapp/scripts/live-browser-scenarios.mjs`.

Checkpoint 2026-06-24 LIVE-307: `scripts/run_live_behavior_suite.py` now also supports `--mode agent-operation` for agent/runtime and operation-lifecycle scenarios from `test_data_packs/critical_behavior_v1.json`. The mode selects `native_agent` and `operation_lifecycle` records and builds commands for existing safe probes: `scripts/live_agent_uia_state_probe.py` with `--expect-connected` plus bounded UIA output/screenshot paths, and `scripts/live_ws_v3_probe.py malformed-outbox` with a scenario run id for protocol/operation evidence. Dry-run output currently lists `tool_run_approve_deny_timeout` and `windows_linux_vm_agent_runtime`; full live pass still requires API/DB/Observer/agent SQLite evidence in the v2 manifest. Coverage: RED/GREEN `scripts/test_run_live_behavior_suite.py`, dry-run `python scripts/run_live_behavior_suite.py --pack test_data_packs/critical_behavior_v1.json --mode agent-operation --surfaces native_agent,operation_lifecycle --dry-run --json`, plus `python scripts/live_agent_uia_state_probe.py --help` and `python scripts/live_ws_v3_probe.py --help`.

Checkpoint 2026-06-24 LIVE-309: `pc_client.live_evidence.v2` manifests now require an `observer_canary` block that points to the JSON and Markdown reports from `scripts/run_observer_canary_suite.py`. The validator loads the JSON report, requires coverage `ok=true`, non-empty required root kinds, no missing root kinds, no failed scenarios, report/manifest summary parity, pass coverage/status fields and an ISO `checked_at`; `scripts/live_evidence_pack.py` creates `observer-canary.md` and blocked manifest placeholders so a live pass cannot be claimed without canary evidence. Coverage: RED/GREEN `scripts/test_validate_live_evidence.py::test_validate_live_evidence_requires_observer_canary_report`, `::test_validate_live_evidence_rejects_observer_canary_failures`, and `scripts/test_live_evidence_pack.py`.

Checkpoint 2026-06-24 LIVE-310: `scripts/build_live_release_summary.py` now produces a single `pc_client.live_release_summary.v1` JSON/Markdown summary from `test_data_packs/critical_behavior_v1.json` and completed `artifacts/live/**/manifest.json` files. It validates each manifest through `scripts/validate_live_evidence.py`, reports browser and agent-operation suite plan counts, required manifest sections, pass/fail/missing scenario coverage and release blockers; CLI exit is non-zero until every critical behavior scenario has a passing v2 manifest. Current default run against existing artifacts is correctly `blocked` with 17 missing critical scenario manifests. Coverage: RED/GREEN `scripts/test_build_live_release_summary.py` and dry-run `python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --json`.

Checkpoint 2026-06-24 LIVE-311: `scripts/build_live_release_summary.py` now filters live manifests by exact release context: `--commit`, `--environment`, `--release-run-id` and `--expected-schema-head`. A passing manifest from an older commit/run/schema no longer satisfies a current scenario, and a failing manifest in the current release context blocks even when old pass evidence exists. `scripts/ci_artifacts.py` now exposes `require_live_release_summary()`, and both `scripts/release_candidate_preflight.py` and `scripts/release_server_to_remote.py --gate full` require a passing `pc_client.live_release_summary.v1` at `artifacts/live/release-summary.json` for the candidate commit/environment before release. Coverage: RED/GREEN `scripts/test_build_live_release_summary.py::test_build_live_release_summary_filters_to_exact_release_context_and_fail_wins`, `scripts/test_ci_artifacts.py::test_require_live_release_summary_accepts_exact_pass_context`, `scripts/test_release_candidate_preflight.py::test_main_checks_exact_ci_and_bundle_for_clean_candidate`, `scripts/test_release_server_to_remote.py::test_main_requires_green_ci_by_default`, full affected script suite `python -m pytest scripts/test_build_live_release_summary.py scripts/test_ci_artifacts.py scripts/test_release_candidate_preflight.py scripts/test_release_server_to_remote.py -q --tb=short`, and historical exact-context smoke returning `blocked` with 17 missing current-run manifests.

Checkpoint 2026-06-24 PERF-401: `scripts/summarize_fixture_timings.py` now applies a default fixture timing budget to CI timing JSONL artifacts and writes `budget_profile`, `budget_status` and `budget_violations` into `fixture-timings-summary.json`. Budgets are attached to the affected fixture/phase stats and currently cover heavy setup/teardown phases such as `run_migrations`, `cleanup_db`, `_cleanup_db_async`, `test_app`, `test_client`, light HTTP fixtures and `test_agent`; `--enforce-budget` makes the summarizer exit non-zero on budget violations without raising pytest timeouts. Coverage: RED/GREEN `scripts/test_summarize_fixture_timings.py`.

Checkpoint 2026-06-24 PERF-402: `scripts/run_ci_suite.py` now accepts `--parallel-measurements <fixture-timings-summary.json>` to cap bounded DB/WS layer parallelism from measured fixture timing budget status. Passing/no-data summaries keep conservative parallelism, while `budget_status=fail` caps effective workers to 1 and records `summary.parallel_measurement_decision`; this prevents increasing DB/WS concurrency when timing evidence already shows slow fixture setup. Coverage: RED/GREEN `scripts/test_run_ci_suite.py::test_parallel_measurements_cap_workers_after_budget_failure` and `::test_parallel_measurements_can_disable_parallel_group`, plus full `scripts/test_run_ci_suite.py`.

После pilot расширять matrix, а не создавать отдельные несвязанные live scripts.

---

## 15. Предлагаемые новые/изменяемые файлы

### Новые

- `quality/test_suites.toml`
- `quality/db_table_classification.toml`
- `quality/observer_coverage_matrix.json`
- `scripts/audit_test_inventory.py`
- `scripts/audit_db_cleanup_schema.py`
- `scripts/validate_live_evidence.py`
- `scripts/run_live_behavior_suite.py`
- `scripts/build_live_release_summary.py`
- `scripts/test_audit_test_inventory.py`
- `scripts/test_audit_db_cleanup_schema.py`
- `scripts/test_validate_live_evidence.py`
- `scripts/test_build_live_release_summary.py`
- `server/tests/test_observer_integrity_scan_scope.py`
- `server/tests/test_observer_integrity_runner.py`
- `server/tests/test_observer_web_event_identity.py`
- `server/tests/test_db_cleanup_schema_contract.py`
- `server/tests/test_migration_schema_contract.py`
- `test_data_packs/critical_behavior_v1.json`

### Изменяемые

- `scripts/run_ci_suite.py`
- `scripts/test_run_ci_suite.py`
- `server/tests/conftest.py`
- `server/observer/integrity_service.py`
- `server/app/repos/observer_integrity_repo.py`
- `server/observer/web_event_writer.py`
- `server/observer/checks/web_cabinet.py`
- другие checker-модули после введения scan scope;
- `scripts/live_evidence_pack.py`
- `scripts/run_observer_canary_suite.py`
- `docs/TESTING_RULES.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`
- `docs/QUICK_LOOKUP.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`

Названия новых файлов допускается скорректировать, но контракты и gates из плана должны сохраниться.

---

## 16. Команды проверки

### Существующие обязательные

```powershell
python scripts/verify_workspace.py
python scripts/audit_db_cleanup_profiles.py --strict
python scripts/run_ci_suite.py --workspace .
python scripts/run_observer_canary_suite.py --help
python scripts/live_evidence_pack.py --help
```

### Focused Observer

```powershell
python -m pytest server/tests/test_observer_integrity.py -vv
python -m pytest server/tests/test_observer_web_cabinet.py -vv
python -m pytest server/tests/test_trace_overlay_api.py -vv
```

### Существующий test-harness/CI runner

```powershell
python -m pytest server/tests/test_test_harness_no_db.py -vv
python -m pytest scripts/test_run_ci_suite.py -vv
```

### Предлагаемые DB/migration suites

```powershell
python -m pytest server/tests/test_db_cleanup_schema_contract.py -vv
python -m pytest server/tests/test_migration_schema_contract.py -vv
python scripts/run_ci_suite.py --layer migration_schema
```

Эти два DB/migration modules являются deliverables Phase 1 и до их создания не должны указываться как выполненная проверка.

### Предлагаемые

```powershell
python scripts/audit_test_inventory.py --strict
python scripts/audit_db_cleanup_schema.py --strict
python scripts/validate_live_evidence.py --manifest artifacts/live/<run_id>/manifest.json
python scripts/run_live_behavior_suite.py --pack test_data_packs/critical_behavior_v1.json
python scripts/build_live_release_summary.py --pack test_data_packs/critical_behavior_v1.json --live-root artifacts/live --commit <release-commit> --environment <environment> --release-run-id <release-run-id> --expected-schema-head <schema-head> --json
```

---

## 17. Definition of Done для bug fix

Bug закрывается только когда выполнено все применимое:

- [ ] есть failure evidence до исправления;
- [ ] root cause подтвержден;
- [ ] regression test падал на старом поведении;
- [ ] focused test проходит;
- [ ] соседние contract layers проходят;
- [ ] DB state проверен;
- [ ] Observer state проверен;
- [ ] Observer не изменил business state;
- [ ] redaction проверена;
- [ ] real browser/native GUI проверен для видимого изменения;
- [ ] live manifest валиден;
- [ ] cleanup завершен;
- [ ] нет новых active critical/high integrity events;
- [ ] docs/CODEMAP обновлены;
- [ ] residual risks перечислены;
- [ ] не использованы необоснованные skip/xfail/retry/timeout increases.

---

## 18. Definition of Done для фазы плана

Фаза считается завершенной, если:

1. все checkbox items имеют commit/PR/evidence refs;
2. все новые tests принадлежат suite;
3. все новые DB tables классифицированы;
4. все новые Observer flows есть в coverage matrix;
5. CI summary показывает first-attempt/retry/infra status;
6. обязательные live scenarios имеют валидный manifest;
7. blocking bugs отсутствуют или phase остается open;
8. documentation drift check проходит.

---

## 19. Риски реализации

| Риск | Митигирование |
|---|---|
| Ускорение CI уменьшит изоляцию | Сначала baseline и contamination sentinel, затем parallelism |
| Dynamic cleanup удалит reference fixtures | Явная classification + dry-run + protected-table tests |
| Новый trace identity усложнит поиск по ticket | Отделить execution identity от entity correlation/indexes |
| Per-check isolation скроет checker failure | Общий scan `degraded/failed`, self-health event, no resolve |
| Live automation станет destructive | Выделенные entities, allowlist actions, stop conditions, dry-run |
| Coverage станет vanity metric | Targeted branch/mutation coverage только для critical logic |
| Flaky registry превратится в permanent quarantine | Owner, expiry, blocking threshold, no silent exclusion |
| Data pack разойдется с runtime | Schema/version validation и preflight against live registry |
| Документы снова разойдутся | Machine-readable catalogs генерируют human tables |

---

## 20. Приложение: завершенная задача requester create UX

Предыдущий `PLANS.md` фиксировал завершенную переработку создания обращения:

- одна форма вместо отдельных description/review steps;
- inline local/server validation;
- preview перед create;
- field errors и `aria-invalid`;
- отсутствие Knowledge suggestions до создания;
- draft restore;
- fixture Playwright, Vitest, TypeScript/build и real browser evidence;
- live validation выполнялась для remote commit `4e79d34b64efc20788c2be729a0bd6e77980dc4d`.

Эта работа считается historical baseline, но не заменяет новые regression/live gates. При изменении requester create flow сценарии из раздела D1 должны выполняться повторно на exact deployed commit.
