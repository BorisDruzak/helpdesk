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
- `module_install`
- `module_update`
- `module_remove`
- `ws_delivery`
- `retry_exhausted`

Если появляется новый опасный execution flow, он обязан получить observer coverage и понятный `root_kind`.

## 7. API observer

Admin / tech API:

- `GET /api/admin/tech/traces/runtime`
- `GET /api/admin/tech/observer/quick`
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

Ticket observer summary нужен для support/ticket UI и не должен требовать похода в raw tech traces.
Summary counts (`trace_count`, `active_trace_count`, `error_trace_count`) должны считаться по полному набору trace-ов тикета, а не по ограниченному recent-срезу.
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

New React workspaces:

- `/app/support` должен получать observer capability map через `GET /api/web/support/bootstrap`;
- `/app/support` должен получать ticket-scoped observer summary внутри typed detail payload `GET /api/web/support/tickets/{ticket_id}`, а не собирать trace drawer из raw legacy ticket endpoints;
- `/app/support` tool surface должен ходить через typed endpoints `GET /api/web/support/tickets/{ticket_id}/tools` и `POST /api/web/support/tickets/{ticket_id}/tools/run`, а рабочая лента должна показывать `tool_call_started` / `tool_call_result` рядом с observer root trace metadata, чтобы оператор видел traced execution без возврата в legacy `/support`/`/ticket`;
- `/app/support` должен получать live invalidation через typed realtime bridge `GET /api/web/realtime/bootstrap` -> `/ws_ui`, чтобы очередь, карточка тикета и tool timeline обновлялись по `ticket_event_committed` / `operation_updated` без ручного polling-сцепления в feature-коде;
- `/app/admin` должен получать observer capability map через `GET /api/web/admin/bootstrap`.
- `/app/admin` должен брать overview tech/observer срез через typed endpoint `GET /api/web/admin/observer/quick`, а не рендерить raw payload legacy `/api/admin/tech/observer/quick` прямо из React.
- `/app/admin/observer` должен уметь работать и без выбранного `device_id`: global quick summary и trace list обязаны грузиться в общем режиме, а device-scoped drilldown включается только после выбора устройства или конкретной трассы.
- `/app/admin` должен брать trace list и detail drilldown через typed endpoints `GET /api/web/admin/observer/traces` и `GET /api/web/admin/observer/traces/{trace_id}`, чтобы device-scoped выборка и span/error detail не зависели от raw legacy `/api/admin/tech/traces*`.
- `/app/admin/observer` теперь считается полноценным observer workbench, а не просто quick-summary экраном: канонический набор вкладок для React surface — `quick`, `traces`, `signatures`, `degradations`, `runtime`; trace detail обязан показывать spans, error occurrences, span links и agent actions через `GET /api/admin/tech/traces/{trace_id}?include_agent_actions=1`.
- `/app/admin/observer` допускает гибрид transport model: быстрый список и фильтры идут через typed `/api/web/admin/observer/*`, а signature/degradation/runtime/settings/detail surfaces могут читать прямые tech/settings endpoints (`/api/admin/tech/signatures*`, `/api/admin/tech/degradations`, `/api/admin/tech/traces/runtime`, `/api/admin/settings/observer`) пока они остаются canonical source of truth для observer backend.
- `/app/admin/device` может поверх карточки устройства встраивать тот же typed observer quick slice, но без отдельного transport-контракта: глобальная `/app/admin/observer` и device-centric `/app/admin/device` обязаны читать один и тот же `/api/web/admin/observer/*` boundary.
- `/app/admin` может рядом показывать typed modules/actions panel (`GET /api/web/admin/modules`, `PATCH /api/web/admin/modules/rollout_settings`, `PATCH /api/web/admin/modules/{module_name}/preferred`), но observer quick/drilldown при этом остаётся изолированным typed tech slice и не должен деградировать до вызовов legacy `/api/admin/tech/*` из module UI.
- `/app/*` сначала проходит через `GET /api/web/session/me`; observer surfaces в новом web-layer не должны пытаться ходить в trace API до подтверждённой web session.
- Новый `webapp/src/shared/realtime/client.ts` остаётся единственной точкой знания про `ui_hello`, `skip_catchup`, ping и websocket reconnect; observer/support/admin feature-код должен реагировать только на domain-level invalidation и не зависеть от raw transport payload shape.

Канонический operator UX для ticket-scoped trace живёт в `/support`.
Legacy `/ticket` shell остаётся отдельной рабочей страницей тикета и не считается основной observer-поверхностью для support workflow.

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

## 12. Канонический workflow диагностики

1. Открыть `GET /api/admin/tech/observer/quick` или tech-panel quick dashboard.
2. Если кейс ticket-bound, открыть `GET /api/tickets/{ticket_id}/observer`.
3. Для нового `/app/admin/observer` сначала получить global или device-scoped trace list через `GET /api/web/admin/observer/traces`, затем при необходимости открыть `GET /api/admin/tech/traces/{trace_id}?include_agent_actions=1`.
4. Для массовых отказов пройти вкладки `signatures` и `degradations` через canonical endpoints `/api/admin/tech/signatures*` и `/api/admin/tech/degradations`, не сводя React workbench к raw JSON dump.
5. Runtime health, rebuild и sampling/retention settings проверять в той же рабочей области через `/api/admin/tech/traces/runtime`, `POST /api/admin/tech/traces/rebuild` и `GET/PATCH /api/admin/settings/observer`.
6. Для архивных кейсов использовать rebuild только если background backfill ещё не догнал исторический диапазон.

## 13. Что нужно обновлять вместе с observer

Если меняется observer-слой, dangerous flow, trace API, support/admin observer UI или module observer contract, синхронно обновлять:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`

Observer docs должны поддерживаться в актуальном состоянии наравне с CODEMAP.
