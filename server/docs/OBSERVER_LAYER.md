# OBSERVER_LAYER

Каноническая документация по observer-слою `pc_client`.

Этот слой не заменяет helpdesk-домен и не становится новым видом тикета. Он остаётся техническим overlay поверх уже существующих источников исполнения.

## 1. Цель

Observer нужен для ответа на вопросы вида:

- что именно сейчас сломано;
- где в цепочке `ticket -> operation -> tool -> module -> result` произошёл сбой;
- это единичный случай или массовая signature/degradation;
- как быстро открыть trace по тикету, устройству, tool, module или problem fingerprint.

## 2. Каноническая модель

- `Ticket` — бизнес-контейнер.
- `Trace` — сквозной технический след одного исполнения.
- `Span` — участок trace.
- `Span link` — причинная связь между кусками исполнения, которые не обязаны быть строгим деревом.
- `Error occurrence` — конкретный факт сбоя в trace/span.
- `Error signature` — агрегированная группа похожих сбоев.

Ключевой инвариант: observer не дублирует ticket business state и не становится source of truth для helpdesk-логики.

## 3. Источники данных

Observer сейчас проецируется поверх:

- `operations`
- `ticket_events`
- `device_events`
- `agent_runtime_audit`
- agent-side `action_trace`

Runtime-audit-only auth/provisioning events are first-class projection sources too. When an audit row has no `operation_id` or `ticket_id`, observer assigns a stable synthetic trace id and projects nearby same-device lifecycle audit rows into a trace so Codex/API/UI searches can still drill into the failing step.

Проекция и поиск живут в:

- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/app/db/models.py`

## 4. Хранилище observer

Основные таблицы:

- `observer_traces`
- `observer_spans`
- `observer_span_links`
- `observer_error_occurrences`
- `observer_error_signatures`

Ticket-root anchor:

- `tickets.observer_root_trace_id`

Это техническая опора для полного trace жизненного цикла тикета.

### Coverage Matrix

| Flow | Source row | Target root_kind | Spans | Signatures | Bundle/search |
| --- | --- | --- | --- | --- | --- |
| Agent invalid token / handshake auth | `agent_runtime_audit` | `agent_auth` | yes | yes | `q=invalid_token`, `root_kind=agent_auth` |
| Agent uploaded local telemetry | `agent_observer_events` | `agent_runtime`, `agent_update`, `tool_call`, `module_install` | yes | warning/error only | `device_id`, `trace_id`, `operation_id`, `q=agent.update` |
| Module reconcile pre-operation failure | `agent_runtime_audit` with `source=module_reconcile` | `module_reconcile` | yes | yes | `q=reconcile`, `root_kind=module_reconcile` |
| Playbook local/skipped/preflight step | `playbook_run`, `playbook_step_run` | `playbook_run` | yes | failed steps only | `playbook_run_id`, `step_run_id`, `q=MODULE_PRECHECK_FAILED` |
| Passport evidence add/link/verify/reject/archive | `ticket_events` (`passport_evidence_*`) | ticket-root trace | yes | no | `ticket_id`, `q=passport_evidence`, `source_ref`, `evidence_id` |
| Web auth/API boundary failure | rate-limited `agent_runtime_audit` with `source=web_auth` | `web_auth` | yes | yes | `route=/api/...`, `q=AUTH_REQUIRED`, `q=FORBIDDEN` |
| Observer projector degraded health | bounded `agent_runtime_audit` with `source=observer_runtime` | `observer_runtime` | yes | yes | `root_kind=observer_runtime`, runtime endpoint |

## 5. Runtime и проекция

Observer runtime:

- сканирует committed source rows;
- проецирует hot traces инкрементально;
- делает background historical backfill;
- применяет retention/sampling settings;
- поддерживает materialized agent/module spans поверх agent action trace.

Нормальный путь для горячих кейсов — background refresh, а не ручной rebuild.

`rebuild` остаётся emergency/debug инструментом.

## 6. Root flows и опасные зоны

Для большинства рискованных мест observer должен иметь отдельный `root_kind`.

Канонические опасные flow:

- `ticket`
- `run_tool`
- `consent`
- `agent_update`
- `device_provisioning`
- `agent_auth`
- `agent_runtime`
- `module_install`
- `module_update`
- `module_remove`
- `module_live_test`
- `module_preferred_gate`
- `module_reconcile`
- `playbook_run`
- `web_auth`
- `observer_runtime`
- `ws_delivery`
- `retry_exhausted`

Если появляется новый опасный execution flow, он обязан получить observer coverage и понятный `root_kind`.

## 7. API observer

Admin / tech API:

- `GET /api/admin/tech/traces/runtime`
- `GET /api/admin/tech/observer/quick`
- `GET /api/admin/tech/observer/search`
- `GET /api/admin/tech/diagnostics/bundle`
- `GET /api/admin/tech/traces`
- `GET /api/admin/tech/traces/{trace_id}`
- `POST /api/admin/tech/traces/rebuild`
- `GET /api/admin/tech/signatures`
- `GET /api/admin/tech/signatures/{error_signature}`
- `GET /api/admin/tech/degradations`
- `GET /api/admin/settings/observer`
- `PATCH /api/admin/settings/observer`

Ticket-scoped API:

- `GET /api/tickets/{ticket_id}/observer`
- `GET /api/web/support/bootstrap`
- `GET /api/web/support/tickets/{ticket_id}`
- `GET /api/web/admin/bootstrap`
- `GET /api/web/admin/observer/quick`
- `GET /api/web/admin/observer/traces`
- `GET /api/web/admin/observer/traces/{trace_id}`

Codex/live debugging entrypoints:

- `GET /api/admin/tech/observer/search?q=...` correlates by trace, ticket, operation, device, tool, module or signature text and returns matching traces/signatures plus next checks.
- `GET /api/admin/tech/diagnostics/bundle?...` accepts `trace_id`, `ticket_id`, `operation_id`, `device_id`, `playbook_run_id`, `step_run_id`, `route`, `q`, `lookback_hours` and optional `include_agent_actions=1`; the redacted payload includes trace detail, related traces, ticket/device context, agent audit, recent warning/error logs, signatures, degradations and recommended next checks.
- Auth/provisioning debugging should start with `q=connection_request`, `q=invalid_token`, `root_kind=device_provisioning`, or `root_kind=agent_auth`. These queries must find operation-less `agent_runtime_audit` traces and signatures for warning/error events such as `connection_request_token_limit`, `device_fingerprint_mismatch`, `connection_request_rejected`, and `invalid_token`.

Ticket observer summary нужен для support/ticket UI и не должен требовать похода в raw tech traces.

Typed support detail (`GET /api/web/support/tickets/{ticket_id}`) embeds a compact observer payload for `/app/tickets`: root trace status/url, root kind, health label (`empty`, `ok`, `running`, `error`), latest error label/stage/time, top ticket-local signature, compact related/active/error trace rows and compact recent occurrences. Full spans, span links and raw occurrence detail stay in `/app/admin/observer`.

Latest operation snapshots in the same typed support detail payload carry trace relation metadata for the support workspace: `ticket_root`, `operation_child`, `retry_child`, `playbook_child` or `unknown`, plus operation trace URL, ticket root trace URL and retry lineage (`retry_of_operation_id`, `retry_source_trace_id`). The support UI should use these fields to label links as root trace, operation trace, retry trace or playbook trace instead of showing a raw `Trace: <id>` chip.

Passport/evidence audit is trace-visible through ticket events. Evidence write handlers must write `source_ref`, `section_key`, verification/export metadata and `observer_provenance` in `passport_evidence_added`, `passport_evidence_linked`, `passport_evidence_verified`, `passport_evidence_rejected`, `passport_evidence_archived`, `passport_evidence_superseded` and `passport_evidence_unverified` events; the event row `trace_id` must be resolved through `TicketEventsRepo` to the existing ticket-root trace unless the event is deliberately operation-bound. This lets support reconstruct why a fact satisfied or failed closure without reading raw DB rows.
Summary counts (`trace_count`, `active_trace_count`, `error_trace_count`) должны считаться по полному набору trace-ов тикета, а не по ограниченному recent-срезу.

## 8. Live canary coverage

`python scripts/run_observer_canary_suite.py` is the canonical live observer canary. In addition to consent, module lifecycle, retry exhaustion, disconnect and WS replay flows, it now seeds and verifies first-class source probes for:

- `module_reconcile`;
- `playbook_run`;
- `web_auth`;
- `observer_runtime`.

The canary report includes `coverage.required_root_kinds`, `coverage.observed_root_kinds`, `coverage.missing_root_kinds` and trace references. Use `--markdown-report-path artifacts/observer_canaries/<name>.md` when the result needs to be attached to release notes or a handoff. The same run checks that the current local `pc_agent.version.AGENT_VERSION` exists in the stable build registry for `windows_amd64` and `linux_alt_x86_64`; it does not force-update production devices by default.
Signature rows в ticket summary обязаны различать глобальный `occurrences_count` и ticket-local `ticket_occurrences_count`, чтобы support UI не путал историю конкретного тикета с общей картиной по signature.
Новый typed web boundary должен рекламировать observer capability endpoints через bootstrap payloads, чтобы React workspace не зашивал raw tech/ticket URLs прямо в feature-код.

## 8. UI-поверхности

Admin tech panel:

- quick diagnosis dashboard;
- trace/signature/degradation search;
- runtime status/backfill health;
- trace detail с agent action trace.

Support workspace:

- trace summary выбранного тикета;
- root trace excerpt;
- related traces;
- signatures и recent occurrences.
- `/app/tickets` shows the compact Observer diagnostic card from typed support detail in the context sidebar; it presents operator-readable health, counters, root trace, latest error, top signature, compact trace rows and action links, while raw trace ids and summary endpoint stay secondary.

New React workspaces:

- `/app/support` должен получать observer capability map через `GET /api/web/support/bootstrap`;
- `/app/support` должен получать ticket-scoped observer summary внутри typed detail payload `GET /api/web/support/tickets/{ticket_id}`, а не собирать trace drawer из raw legacy ticket endpoints;
- `/app/support` tool surface должен ходить через typed endpoints `GET /api/web/support/tickets/{ticket_id}/tools` и `POST /api/web/support/tickets/{ticket_id}/tools/run`, а рабочая лента должна показывать `tool_call_started` / `tool_call_result` рядом с observer root trace metadata, чтобы оператор видел traced execution без возврата в legacy `/support`/`/ticket`;
- `/app/support` playbook surface должен ходить через typed endpoints `GET /api/web/support/tickets/{ticket_id}/playbooks` и `POST /api/web/support/tickets/{ticket_id}/playbooks/run`; support UI обязан показывать ticket-scoped playbook run failures (`playbook_run`, `playbook_step_run`, `MODULE_NOT_ON_SERVER`, missing required params) рядом с кнопкой запуска, а не только в raw observer workbench;
- `/app/support` должен получать live invalidation через typed realtime bridge `GET /api/web/realtime/bootstrap` -> `/ws_ui`, чтобы очередь, карточка тикета и tool timeline обновлялись по `ticket_event_committed` / `operation_updated` без ручного polling-сцепления в feature-коде;
- `/app/admin` должен получать observer capability map через `GET /api/web/admin/bootstrap`.
- `/app/admin` должен брать overview tech/observer срез через typed endpoint `GET /api/web/admin/observer/quick`, а не рендерить raw payload legacy `/api/admin/tech/observer/quick` прямо из React.
- `/app/admin/observer` должен уметь работать и без выбранного `device_id`: global quick summary и trace list обязаны грузиться в общем режиме, а device-scoped drilldown включается только после выбора устройства или конкретной трассы.
- `/app/admin` должен брать trace list и detail drilldown через typed endpoints `GET /api/web/admin/observer/traces` и `GET /api/web/admin/observer/traces/{trace_id}`, чтобы device-scoped выборка и span/error detail не зависели от raw legacy `/api/admin/tech/traces*`.
- `/app/admin/observer` теперь считается полноценным observer workbench, а не просто quick-summary экраном: канонический набор вкладок для React surface — `quick`, `traces`, `signatures`, `degradations`, `runtime`; trace detail обязан быстро показывать spans, error occurrences и span links, а agent actions брать из diagnostic bundle, чтобы два параллельных запроса не конкурировали за materialized action sync.
- `/app/admin/observer` trace search работает на сервере: typed traces принимают `q`, `trace_id`, `ticket_id`, `operation_id`, `tool_name`, `module_name`, `error_signature` и `min_duration_ms`, поэтому UI не ограничен фильтрацией первой загруженной страницы.
- `/app/admin/observer` trace detail показывает `GET /api/admin/tech/diagnostics/bundle` с next checks, logs/audit counters и компактными agent action rows; long `error_signature`, trace and operation identifiers must wrap inside drilldown cards; server-side action compaction обязан ограничивать большие `details` payloads, а materialized action-span sync включается только через `sync_agent_actions=1`, чтобы `tool response` traces не подвешивали detail/bundle UI.
- `/app/admin/observer?trace_id=...` is the canonical deep link from support trace cards: it must switch to the traces tab, pass `trace_id` into the typed traces query, select the requested trace and load detail/bundle for that trace. `ticket_id` and `operation_id` query params are accepted as additional typed trace filters for support/admin handoff.
- `/app/admin/observer` допускает гибрид transport model: быстрый список и фильтры идут через typed `/api/web/admin/observer/*`, а signature/degradation/runtime/settings/detail surfaces могут читать прямые tech/settings endpoints (`/api/admin/tech/signatures*`, `/api/admin/tech/degradations`, `/api/admin/tech/traces/runtime`, `/api/admin/settings/observer`) пока они остаются canonical source of truth для observer backend.
- `/app/admin/device` может поверх карточки устройства встраивать тот же typed observer quick slice, но без отдельного transport-контракта: глобальная `/app/admin/observer` и device-centric `/app/admin/device` обязаны читать один и тот же `/api/web/admin/observer/*` boundary.
- `/app/admin` может рядом показывать typed modules/actions panel (`GET /api/web/admin/modules`, `PATCH /api/web/admin/modules/rollout_settings`, `PATCH /api/web/admin/modules/{module_name}/preferred`), но observer quick/drilldown при этом остаётся изолированным typed tech slice и не должен деградировать до вызовов legacy `/api/admin/tech/*` из module UI.
- `/app/*` сначала проходит через `GET /api/web/session/me`; observer surfaces в новом web-layer не должны пытаться ходить в trace API до подтверждённой web session.
- Новый `webapp/src/shared/realtime/client.ts` остаётся единственной точкой знания про `ui_hello`, `skip_catchup`, ping и websocket reconnect; observer/support/admin feature-код должен реагировать только на domain-level invalidation и не зависеть от raw transport payload shape.

Канонический operator UX для ticket-scoped trace живёт в `/support`.
Legacy `/ticket` shell остаётся отдельной рабочей страницей тикета и не считается основной observer-поверхностью для support workflow.

Module lab-test observer coverage:

- `GET /api/modules/{module_name}/{version}/live_test_candidates` is a preflight report, not a trace source by itself.
- `POST /api/modules/{module_name}/{version}/live_tests` creates a `module_live_test` trace with `module.lab_agent_select`, `module.install_module_package` and `module.run_tool` spans.
- Preferred rollout blocks for Windows modules create a `module_preferred_gate` trace and return `observer_trace_id` with `MODULE_WINDOWS_LIVE_TEST_REQUIRED`.

## 9. First-class деградации

Observer поддерживает первоклассные observer query по:

- `min_duration_ms`
- `min_retry_count`
- `min_timeout_rate`
- `min_retry_rate`
- `min_slow_rate`
- `root_kind`

Нормальный путь диагностики массовых проблем:

1. quick diagnosis;
2. degradations/signatures;
3. конкретный trace;
4. detail spans/errors/actions.

## 10. Agent-side мост

Если модуль не пишет собственный runtime audit, fallback-слой обязан оставаться доступным через:

- `pc_agent/core/action_trace.py`
- observer sync в `server/tech/handlers.py`
- materialized agent/module spans в `server/observer/service.py`

Это обязательная страховка от “тихих” модульных провалов.

## 11. Retention, sampling, redaction

Observer runtime обязан:

- хранить settings в DB-backed конфиге;
- не тащить чувствительные поля в detail/export/raw attrs;
- редактировать секреты через `shared/redaction.py`;
- иметь управляемый sampling для шумных success traces.

Observer detail должен оставаться пригодным для диагностики, но не превращаться в экспорт сырых секретов.

Agent action rows в admin tech detail/bundle являются диагностическим индексом, а не raw export: вложенные dict/list значения сворачиваются до типа, размера и небольшого sample, длинные строки обрезаются.

## 12. Канонический workflow диагностики

1. Открыть `GET /api/admin/tech/observer/quick` или tech-panel quick dashboard.
2. Если известен любой id/текст, начать с `GET /api/admin/tech/observer/search?q=...`.
3. Для Codex/prod debugging собрать `GET /api/admin/tech/diagnostics/bundle?...` по `trace_id`, `operation_id`, `ticket_id`, `device_id` или `q`.
4. Если кейс ticket-bound, открыть `GET /api/tickets/{ticket_id}/observer`.
5. Для нового `/app/admin/observer` сначала получить global или device-scoped trace list через `GET /api/web/admin/observer/traces`, затем открыть fast detail `GET /api/admin/tech/traces/{trace_id}` и bundle `GET /api/admin/tech/diagnostics/bundle?trace_id=...&include_agent_actions=1`.
6. Для массовых отказов пройти вкладки `signatures` и `degradations` через canonical endpoints `/api/admin/tech/signatures*` и `/api/admin/tech/degradations`, не сводя React workbench к raw JSON dump.
7. Runtime health, rebuild и sampling/retention settings проверять в той же рабочей области через `/api/admin/tech/traces/runtime`, `POST /api/admin/tech/traces/rebuild` и `GET/PATCH /api/admin/settings/observer`.
8. Для архивных кейсов использовать rebuild только если background backfill ещё не догнал исторический диапазон.

## 13. Что нужно обновлять вместе с observer

Если меняется observer-слой, dangerous flow, trace API, support/admin observer UI или module observer contract, синхронно обновлять:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`

Observer docs должны поддерживаться в актуальном состоянии наравне с CODEMAP.
