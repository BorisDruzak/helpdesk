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

Ticket observer summary нужен для support/ticket UI и не должен требовать похода в raw tech traces.

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
3. По необходимости провалиться в `trace_id` или `error_signature`.
4. Для живого agent-side trail включить `include_agent_actions=1`.
5. Для архивных кейсов использовать rebuild только если background backfill ещё не догнал исторический диапазон.

## 13. Что нужно обновлять вместе с observer

Если меняется observer-слой, dangerous flow, trace API, support/admin observer UI или module observer contract, синхронно обновлять:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`

Observer docs должны поддерживаться в актуальном состоянии наравне с CODEMAP.
