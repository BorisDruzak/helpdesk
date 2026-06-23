# PLANS.md — программа качества, live-проверок, Observer и БД

## Статус и область

- **Статус:** активный master-plan.
- **Дата анализа:** 2026-06-23.
- **Анализируемая ветка:** `codex/helpdesk-process-model`.
- **Анализируемая ревизия:** `ebaab32dc52e573c4cfde0aafe9a6aa7ee8fedcb`.
- **Основная цель:** сделать исправление багов воспроизводимым, тесты — достоверными, live-проверки — доказательными, а технический долг — управляемым.
- **Критические зоны:** ticket/requester/support behavior, Protocol V3, agent runtime, PostgreSQL, Observer overlay, webapp, CI/release scripts.
- **Не является целью:** превращать Observer в источник бизнес-истины, подменять live-проверку fixture/mocked E2E-тестом или запускать разрушающие проверки на production-данных.

Этот документ заменяет узкий task-local план по форме создания обращения. Завершенная работа по той задаче сохранена в приложении в конце файла.

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
server_request_id / correlation_id / operation_id / durable event_id
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
- [ ] `QG-003` Включить `audit_db_cleanup_profiles.py --strict`.
- [ ] `QG-004` Сохранить baseline JUnit/durations/retries.
- [ ] `QG-005` Маркировать fixture E2E отдельно от live browser.
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
- [ ] `DB-104` Добавить migration suite.

**Gate:** incomplete checker не resolve-ит события; cleanup audit показывает zero drift; fresh/baseline migrations green.

### Phase 2 — behavioral contracts

- [ ] `BEH-201` Requester create/block/no-device/on-behalf matrix.
- [ ] `BEH-202` Chat retry/idempotency.
- [ ] `BEH-203` Resolve/feedback/reopen.
- [ ] `BEH-204` Support claim/status/SLA/privacy.
- [ ] `BEH-205` Tool operation/outbox/result/ACK.
- [ ] `BEH-206` Consent approve/deny/timeout/cancel race.
- [ ] `BEH-207` Agent reconnect/replay/duplicate.
- [ ] `BEH-208` Auth/account/session isolation.
- [ ] `BEH-209` Knowledge/Registry audience rules.
- [ ] `BEH-210` Observer non-mutation/redaction property tests.

**Gate:** каждый critical journey имеет API, DB и Observer assertions; visible journeys имеют fixture UI tests.

### Phase 3 — доказательный live gate

- [x] `LIVE-301` Ввести evidence manifest v2.
- [x] `LIVE-302` Реализовать validator.
- [ ] `LIVE-303` Добавить exact commit/schema preflight.
- [ ] `LIVE-304` Добавить before/after integrity delta.
- [ ] `LIVE-305` Создать critical behavior data pack.
- [ ] `LIVE-306` Автоматизировать requester/support browser scenarios.
- [ ] `LIVE-307` Автоматизировать agent/operation scenarios.
- [x] `LIVE-308` Доказать cleanup.
- [ ] `LIVE-309` Интегрировать Observer canary report.
- [ ] `LIVE-310` Сформировать один release summary.

**Gate:** pass невозможен без browser/API/DB/Observer evidence и commit parity.

### Phase 4 — надежность и скорость

- [ ] `PERF-401` Test fixture timing budget.
- [ ] `PERF-402` Domain-level bounded parallelism по измерениям.
- [ ] `FLAKE-403` Retry/flaky registry.
- [ ] `PROP-404` Property/state-machine tests.
- [ ] `COV-405` Targeted branch coverage critical packages.
- [ ] `MUT-406` Mutation testing для status/policy/redaction/idempotency pure logic.
- [ ] `FIX-407` Schema-validated fixture builders.
- [ ] `CI-408` Affected-suite selection с обязательным full merge gate.

**Gate:** ускорение не уменьшает coverage и не использует timeout/retry как маскировку.

### Phase 5 — закрытие активного техдолга

- [ ] `TD-501` Перенести active risks из архивного документа в реестр.
- [ ] `TD-502` Закрыть ACK/in-progress race tests.
- [ ] `TD-503` Унифицировать run_tool facade.
- [ ] `TD-504` Удалить бессрочные contaminations.
- [ ] `TD-505` Проверить Observer retention/query plans на объемах.
- [ ] `TD-506` Обновить CODEMAP/QUICK_LOOKUP/TESTING_RULES.
- [ ] `TD-507` Зафиксировать multi-instance outbox prerequisites.

**Gate:** у каждого active risk есть owner, test и measurable acceptance criteria.

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

Checkpoint 2026-06-23 QG-002: `scripts/audit_test_inventory.py --strict` is implemented and wired into `scripts/run_ci_suite.py` as `test_inventory_audit` before pytest layers. Current inventory audit reports 422 test files, all owned by canonical suites, with zero strict issues. `QG-003` remains open: current `python scripts/audit_db_cleanup_profiles.py --strict` still reports existing DB cleanup profile debt.

Checkpoint 2026-06-23 QG-006: `scripts/ci_artifacts.py::require_green_ci_artifact` rejects otherwise-green CI summaries when any server DB/WS layer log contains a shared-test-DB fallback marker. Release preflight, deploy and full release gates now cannot use shared `pc_support_test` fallback as release-pass evidence; rerun full CI with `TEST_DATABASE_ADMIN_URL` and isolated `pc_support_test_<runid>` databases.

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
- `scripts/test_audit_test_inventory.py`
- `scripts/test_audit_db_cleanup_schema.py`
- `scripts/test_validate_live_evidence.py`
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
```

Эти два DB/migration modules являются deliverables Phase 1 и до их создания не должны указываться как выполненная проверка.

### Предлагаемые

```powershell
python scripts/audit_test_inventory.py --strict
python scripts/audit_db_cleanup_schema.py --strict
python scripts/validate_live_evidence.py artifacts/live/<run_id>/manifest.json
python scripts/run_live_behavior_suite.py --pack test_data_packs/critical_behavior_v1.json
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
