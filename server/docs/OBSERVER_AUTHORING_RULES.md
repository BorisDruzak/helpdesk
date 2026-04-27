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

### 3.3 Добавить source records

Observer строится поверх фактов исполнения. Новый flow должен оставлять минимум один из слоёв:

- server-side source rows (`operations`, `ticket_events`, `device_events`, runtime audit);
- agent-side `action_trace`;
- module breadcrumbs через observer SDK.

Если flow не оставляет ни одного пригодного источника, observer coverage считается отсутствующей.

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

Все подобные поля идут через redaction helpers.

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
- tech API должен поддерживать быстрый drilldown, а не только сырой dump.
- web bootstrap contracts (`/api/web/support/bootstrap`, `/api/web/admin/bootstrap`) должны отдавать capability links для observer surfaces, а не заставлять frontend разбрасывать raw trace URLs по коду.

## 7. Специальные правила для UI

Если меняется admin/support observer UI:

- использовать observer API, а не ручную сборку из unrelated endpoints;
- сохранять “обычный оператор -> quick diagnosis -> drilldown” путь;
- не прятать trace detail только за raw JSON.
- новые React workspace-экраны должны читать observer capabilities из typed web boundary, а не хардкодить tech/ticket endpoints в компонентах.
- новые React workspace-экраны не должны запускать observer fetch до успешного `GET /api/web/session/me` и подтверждённой web session.
- admin observer surfaces должны поддерживать оба режима одного typed boundary: global обзор без выбранного `device_id` и device-scoped quick/drilldown после выбора устройства; отсутствие выбранного устройства не должно тихо отключать observer query целиком.

- `/app/admin/observer` считается полноценным workbench: вкладки `quick`, `traces`, `signatures`, `degradations`, `runtime` должны оставаться согласованными между собой, а trace detail обязан показывать spans, error occurrences, span links и agent actions в одном экране вместо деградации до "open raw payload".
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
