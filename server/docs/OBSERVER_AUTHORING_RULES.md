# OBSERVER_AUTHORING_RULES

Правила расширения observer-слоя без деградации качества.

Этот документ обязателен для server, agent и module authoring задач, которые добавляют новые execution flow, опасные шаги или trace-visible API/UI.

## 1. Главные инварианты

- Observer остаётся overlay, а не бизнес-доменом.
- `Ticket` и `Problem` не заменяются trace-моделью.
- Новая instrumentation не должна требовать ручного поиска по сырым логам как основного пути диагностики.
- Любой новый dangerous flow должен быть виден в observer минимум на уровне `trace -> spans -> error/signature`.

## 2. Когда observer обновлять обязательно

Обязательное обновление observer требуется, если меняется:

- новый `root_kind` или рискованный execution flow;
- ticket lifecycle instrumentation;
- tool/module execution pipeline;
- consent/update/module lifecycle;
- agent authorization, device provisioning and handshake/token lifecycle;
- ws/outbox/ack/nack/replay path;
- retry/timeout/cancel semantics;
- support/admin observer UI;
- observer API, retention/sampling или redaction behavior.

## 3. Чеклист для нового dangerous flow

### 3.1 Определить trace-модель

Нужно явно определить:

- `root_kind`
- ключевые spans
- источники ошибок
- expected signatures
- degradation dimensions

Если это ticket-bound flow, нужно понять, должен ли он продолжать ticket-root trace или быть linked child trace.

### 3.2 Протащить корреляцию

Новый flow обязан иметь устойчивую корреляцию по нужным ids:

- `trace_id`
- `ticket_id` если есть тикет
- `operation_id` если есть operation
- `device_id`
- `tool_name` / `module_name` если применимо

Недопустимо терять trace continuity и каждый раз создавать новый случайный trace без причины.

Для support workspace lifecycle events (`chat_message`, `status_changed`, `queue_changed`, `priority_changed`, `worklog_added`, `approval_*`, `passport_evidence_*`) не передавать ad-hoc `uuid4()` как trace id. Такие события должны идти через `TicketEventsRepo.add_event()` без explicit trace id или с заранее полученным `ensure_ticket_observer_root_trace_id()`, чтобы существующий `tickets.observer_root_trace_id` оставался единой историей тикета. Operation-bound events (`tool_call_started`, `tool_call_result`, `operation_retried`, playbook/tool execution) должны сохранять `operation_id`; repo resolution тогда связывает событие с operation trace, а ticket-root causality восстанавливается через observer projection/span links.

### 3.3 Добавить source records

Observer строится поверх фактов исполнения. Новый flow должен оставлять минимум один из слоёв:

- server-side source rows (`operations`, `ticket_events`, `device_events`, runtime audit);
- agent-side `action_trace`;
- module breadcrumbs через observer SDK.

Если flow не оставляет ни одного пригодного источника, observer coverage считается отсутствующей.

Auth/provisioning flows that do not have an operation must write `agent_runtime_audit`. Observer projects operation-less audit rows as synthetic traces and classifies them by `root_kind`: `device_provisioning`, `agent_auth`, or `agent_runtime`. Warning-level actionable events must still become signatures when they represent a support-visible failure, for example `connection_request_token_limit`, `device_fingerprint_mismatch`, `connection_request_rejected`, or `invalid_token`.

Agent telemetry, playbook local steps, module reconcile, web-auth/API boundary failures and observer-runtime self-health are first-class observer sources. Use `agent_observer_events` for bounded agent-uploaded telemetry; use existing `playbook_run`/`playbook_step_run` rows for local playbook steps; write structured `agent_runtime_audit` rows with `source=module_reconcile`, `source=web_auth` or `source=observer_runtime` for server-originated failures that would otherwise be log-only. These flows map to `root_kind=module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime`.

Passport evidence writes are ticket-bound observer sources. Any evidence add/link/verify/reject/archive endpoint must write a `passport_evidence_*` `ticket_events` row with a repo-resolved ticket-root `trace_id`, `source_ref`, `section_key`, verification/export metadata and an `observer_provenance` object (`domain=passport_evidence`, action, source_ref, required_fact). Do not make evidence provenance support-visible only through raw `ticket_evidence_items`.

Web-first requester cabinet events must use `server/observer/web_event_writer.py::write_web_cabinet_observer_event()`. These traces use `root_kind=requester_web` and stable source values such as `account_session`, `requester_profile`, `requester_ticket_preview`, `requester_ticket_create`, `requester_knowledge`, `requester_chat`, `requester_closure`, `support_chat`, `support_status`, `support_assignment`, `web_form_runtime`, `device_linking` and `registry_binding`. Requester ticket-create diagnostic target traces may use `event_type=diagnostic_target_missing|diagnostic_target_offline|diagnostic_target_ambiguous`; payloads may include only diagnostic target source/status/reason and boolean evidence flags, not raw requester text, person ids, target ids or tokens. Requester Knowledge traces include suggest, Ask and ticket-create attempt guard outcomes; attempt guard payloads may include only sanitized counts/results/surface/scope summaries, not raw query text or item/version ids. Requester chat/closure traces may include only message/attachment/status/reason/feedback/reopen flags and counts, not raw message text, metadata, closure/reopen reason text, requester comments, feedback ids or Knowledge item ids. Support chat/status/assignment traces may include only visibility/status/present/confirmation/assignment flags and counts, not raw support message text, resolution text, root-cause text, internal/public comments, assignment reason/comment text, actor ids, assignee ids, tokens or raw confirmation prompt content. The writer stores technical observer rows only; it must not create a parallel business table or become the ticket source of truth. Actor ids, emails, phones, cookies, auth headers, passwords, tokens, pairing/access codes, raw query text, raw form values and raw request/response bodies must be redacted or hashed before persistence.
Web-cabinet calls must pass a durable execution key in actor context when available (`server_request_id`, `request_id`, `correlation_id`, `idempotency_key` or `operation_id`). Do not rely on `ticket_id` alone for trace identity when multiple independent actions can occur on the same ticket. Error-to-success recovery may end with `trace.status=succeeded`, but previous error spans/occurrences and `error_count` must remain visible.

### 3.4 Материализовать диагностически полезные spans

Spans нужны не “для галочки”, а чтобы человек видел этапы.

Минимум:

- вход в flow;
- опасные steps;
- terminal step;
- failure stage при ошибке.

Для модулей и внешних/опасных действий полезные span names обычно такие:

- `tool.entry`
- `module.resolve`
- `module.execute`
- `module.step`
- `network.request`
- `subprocess.run`
- `artifact.publish`
- `consent.wait`
- `retry.sleep`

### 3.5 Добавить signature/degradation coverage

Если flow может массово ломаться, у него должны быть:

- нормализованные `error_signature`;
- деградационные метрики/группировка, если важны timeout/retry/slow patterns.

Нельзя оставлять массовый класс сбоев только текстом exception.

### 3.6 Добавить UI-поверхность

Новый observer-visible flow должен быть доступен хотя бы в одном из уровней:

- quick diagnosis;
- trace search/detail;
- support ticket observer summary, если flow ticket-bound.

Если рискованный flow существует только в API, но не виден в UI, observer считается неполным.

### 3.7 Проверить redaction

Нельзя писать в details/raw attrs/action trace:

- raw token;
- password;
- cookie;
- consent token;
- секреты внешних интеграций;
- чувствительные персональные поля без необходимости.

Все подобные поля идут через redaction helpers. Helpers должны возвращать redacted copy, а не мутировать исходные payload objects; custom `Mapping` values обрабатываются как обычные dict.

### 3.7.1 OBS1 integrity events

`observer_integrity_events` are for runtime invariant violations, not generic logs. Each event must include stable `dedupe_key`, severity, source, expected/actual, redacted evidence, runbook and correlation ids when available. The only product-side mutation allowed is writing or resolving the observer event itself. Do not store raw tokens, cookies, requester message text, public access hashes, raw artifact paths or unrestricted result payloads.

Web-cabinet integrity checks live in `server/observer/checks/web_cabinet.py` with source `observer.web_cabinet`. They should detect missing immutable `ticket_context_v1`, missing requester ticket-create observer coverage, on-behalf creator-target fallback, forged requester target acceptance, profile gate bypass, requester-side on-behalf Knowledge audience leakage and missing Customer History projection from existing ticket/observer/Registry/Customer History state, then surface through `/api/web/admin/observer/integrity` and support ticket detail. They must not auto-fix ticket context, mutate requester data, synthesize Customer History rows or enqueue diagnostics.
Integrity checkers that use bounded reads must return complete/incomplete coverage through `ObserverIntegrityCheckResult`; use `LIMIT + 1`, count/cursor pagination or another full-coverage proof, not the number of generated violations after Python-side filtering. Incomplete, failed or legacy/plain-list checker results must not resolve existing events for their source. Repeated observations must preserve operator `acknowledged` state until a complete scan proves the condition disappeared. Missing requester-create coverage must use the strict success predicate, not any trace with matching ticket/source text.

Known historical contamination belongs in `quality/observer_known_contamination.json` first, then seeds `observer_known_contamination` with exact entity scope. Broad suppression by phase, device, timestamp or wildcard is not acceptable. Active rows must be owned, linked to a bug/incident, reviewed, evidence-linked and time-boxed with a future `expires_at`; `scripts/audit_observer_contamination.py --strict` is the CI gate, and DB rows with `expires_at=NULL` are treated as non-matching.

### 3.8 Зафиксировать canary

Для нового опасного flow нужен воспроизводимый canary или live scenario:

- что именно запускать;
- где смотреть trace/signature/degradation;
- чем подтверждается успех observer coverage.

## 4. Специальные правила для модулей

Каждый новый `BaseCollector` tool method обязан:

- иметь верхнеуровневый `self.trace_span("tool.entry", ...)`;
- писать дополнительные breadcrumbs на опасных шагах;
- не удалять scaffold observer instrumentation без эквивалентной замены;
- проходить hard CI guard.

Если модуль делает `subprocess`, `network`, `retry`, `timeout`, `artifact`, `consent`, `publish`, эти шаги должны быть trace-visible.

## 5. Специальные правила для server-side flow

Новый server-originated flow обязан:

- продолжать существующий trace, если это логически одна цепочка;
- не рвать ticket-root trace случайным `uuid4()`, если есть родительский observer context;
- оставлять observer-visible факты, а не только лог строкой.

## 6. Специальные правила для API

Если добавляется observer API:

- endpoint должен быть discoverable через CODEMAP и observer docs;
- ответ должен быть компактным и redacted;
- диагностический API для прод-тестирования должен иметь Codex-friendly форму: один запрос по `trace_id`/`ticket_id`/`operation_id`/`device_id`/`q`, redacted payload, links и recommended next checks;
- ticket-bound observer summary должен быть пригоден для support UI;
- web-cabinet trace filters (`root_kind`, `source`, `person_id`, `error_code`, `event_type`, `route`, `ticket_id`, `device_id`) must be supported by typed admin observer search before relying on them in runbooks or support handoffs;
- tech API должен поддерживать быстрый drilldown, а не только сырой dump.
- web bootstrap contracts (`/api/web/support/bootstrap`, `/api/web/admin/bootstrap`) должны отдавать capability links для observer surfaces, а не заставлять frontend разбрасывать raw trace URLs по коду.
- stdio MCP debug surfaces such as `helpdesk-server-debug` must use a pure service/facade layer (`server/observer/debug_facade.py`) instead of importing HTTP handlers or `aiohttp request.app`; they must stay read-only, bounded and redacted, and must not call `run_tool`, DeviceOutbox, approvals, WS RPC or observer rebuild.

Additional API rules for explainable operation traces:

- New operation/tool execution code must preserve explanation inputs for observer detail: `operation_id`, `ticket_id`, `tool_name`, `module_name`, `actor_role`, and, when available, `actor_id` / display name, `trigger_type`, `retry_of_operation_id`, `playbook_run_id`, `diagnostic_policy_id`, form trigger id and selected `preset_id` or params. Do not rely on span names alone to explain why an operation started.
- Tool labels and preset summaries must come from toolset snapshots, manifests or catalog metadata when available. Observer UI must not hardcode labels for a single module such as `system.collect`.
- Operation stage spans must separate intermediate progress from terminal failure: `queued` is not a separate error when a later `failed` stage carries the root cause. Trace-visible APIs should expose `stage_label`, `stage_state`, `stage_note` and `is_failure_stage` for stage rows.

## 7. Специальные правила для UI

Если меняется admin/support observer UI:

- использовать observer API, а не ручную сборку из unrelated endpoints;
- сохранять “обычный оператор -> quick diagnosis -> drilldown” путь;
- не прятать trace detail только за raw JSON.
- новые React workspace-экраны должны читать observer capabilities из typed web boundary, а не хардкодить tech/ticket endpoints в компонентах.
- новые React workspace-экраны не должны запускать observer fetch до успешного `GET /api/web/session/me` и подтверждённой web session.
- admin observer surfaces должны поддерживать оба режима одного typed boundary: global обзор без выбранного `device_id` и device-scoped quick/drilldown после выбора устройства; отсутствие выбранного устройства не должно тихо отключать observer query целиком.

- `/app/admin/observer` считается полноценным workbench: вкладки `quick`, `traces`, `signatures`, `degradations`, `runtime` должны оставаться согласованными между собой, а trace detail обязан показывать spans, error occurrences, span links и agent actions в одном экране вместо деградации до "open raw payload".
- Admin observer cards and details must lead with operator-readable fields (`ticket_code`, `ticket_title`, device hostname/label, operation/tool label, latest error label, `display_title`, `display_subtitle`) and keep raw UUID-like ids as secondary metadata. Search and handoff flows must accept familiar ticket numbers such as `T-000520`, not only `ticket_id`.
- Admin observer trace detail must render the server-provided `explanation` projection before raw spans: launch source, actor, tool/module/preset, human diagnosis, launch path and next actions. Raw `operation.tool_call`, `operation.stage.*`, UUIDs and attrs belong in the technical/debug part of the page.
- если React observer surface использует mix typed `/api/web/admin/observer/*` и canonical `/api/admin/tech/*` / `/api/admin/settings/observer`, это допустимо только при явной фиксации в docs и при сохранении единого operator flow без legacy iframe/tech-panel jump.

## 8. Минимальный набор проверок

### Module lab-test flows

Published module verification is observer-visible even when it is not ticket-bound:

- live-test run root kind: `module_live_test`;
- preferred rollout gate root kind: `module_preferred_gate`;
- required live-test spans: `module.lab_agent_select`, `module.install_module_package`, `module.run_tool`;
- Windows preferred-gate failures must return `observer_trace_id` with `MODULE_WINDOWS_LIVE_TEST_REQUIRED`.

Candidate listing (`GET /api/modules/{module_name}/{version}/live_test_candidates`) remains a read-only preflight report. Do not create noisy traces for candidate browsing; trace the selected run/gate decision.

Перед завершением observer-правок нужны:

- `python scripts/verify_workspace.py`
- релевантный `pytest` для server/pc_agent
- browser check через `http://192.168.100.17:8666/admin`
- если менялся dangerous flow: live canary или observer suite

## 9. Документация обязательна

Любая observer-правка должна обновлять docs наравне с кодом.

Минимальный набор:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`

Если меняется routing/навигация или playbook:

- `scripts/navigation_catalog.py`
- Codex skill `pc-client-observer-diagnostics`

Observer нельзя считать завершённым, если код уже поменяли, а canonical docs ещё нет.
