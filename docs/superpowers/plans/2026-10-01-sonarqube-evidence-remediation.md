# Helpdesk SonarQube Evidence and Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no implementation, Git publication, deployment, or SonarQube mutation by itself.

**Goal:** По выводам SonarQube MCP проверить исходники Helpdesk, отделить реальные дефекты от техдолга и контекстных срабатываний, записать проверяемые исправления.

**Architecture:** SonarQube служит входом для аудита, GitNexus — картой архитектуры, текущий исходный код и воспроизведения — доказательствами. Исправления бизнес-поведения предшествуют рефакторингу. Сохраняются границы Helpdesk/Endpoint, авторизация, транзакции и существующие интерфейсы.

**Tech Stack:** Python backend (asyncio, aiohttp, SQLAlchemy), React 19.2.5 / TypeScript frontend, pytest, Vitest, SonarQube MCP, GitNexus MCP. Новые зависимости не нужны.

**Spec:** Запрос пользователя в этом чате: «создай отдельный план… смотри вывод SonarQube MCP, проверяй его выводы по коду, записывай в план реальный проблем,техдолга — и исправления». Ограничения: [AGENTS.md](../../../AGENTS.md), [границы архитектуры](../../ARCHITECTURE_BOUNDARIES.md), [правила тестирования](../../TESTING_RULES.md).

## Scope and Global Constraints

- Текущий этап: реализация по отдельному запросу пользователя `/goal` от 2026-10-01. B1–B6 и D1–D5 исправлены в локальной рабочей копии; финальная DB/API-приёмка пройдена. [Evidence](../../SONARQUBE_REMEDIATION_2026-10-01.md) содержит результаты и границы проверки.
- SonarQube: проект `Helpdesk`, анализ ветки по умолчанию `main`, текущие issues `OPEN`/`CONFIRMED`.
- Проверенный локальный SHA: `e9c9bf37dc26af98e9da91b7d424bc4efcee7990`; повторная проверка исходников и MCP — 2026-10-01. Неотслеживаемые `.scannerwork/` и `sonar-project.properties` существовали до этого этапа.
- SHA анализа SonarQube текущий набор MCP-инструментов не сообщает. Нельзя объявлять его равным локальному SHA. Последнее полученное время анализа — 2026-09-30 15:46:21 UTC+5, из предыдущего ответа MCP; сегодня дата анализа этим набором инструментов не обновлена.
- Ограничение первоначального этапа создания плана «не менять код» заменено явным запросом выполнить исправления. SonarQube issues, правила, Quality Gate, анализы и suppression не изменять; scanner, production и полный CI не запускать. DB-тесты используют только временные изолированные staging-базы.
- Не переносить изменения в Endpoint Platform. При будущих изменениях потребления Endpoint сначала проверить GitNexus group и канонический контракт; существование локального адаптера не разрешает менять provider.
- Внешние библиотеки: перед реализацией библиотечно-зависимого поведения сверять установленную версию и Context7. Источники проекта и секреты в Context7 не отправлять.
- Severity SonarQube не равна приоритету исправления. В MCP фильтр `HIGH` может вернуть поле severity `CRITICAL` или `MAJOR`; сохранять оба значения, не выдавать их за одну шкалу.
- Issue может относиться к нескольким software qualities. Не складывать 285/45/2608 как число уникальных issues.
- Никаких blanket `noqa`/исключений тестов, механической замены всех `async`, `sort`, `CancelledError` или литералов ради зелёного отчёта.

## Current State: агрегаты SonarQube

| Severity фильтра MCP | Reliability | Security | Maintainability |
|---|---:|---:|---:|
| BLOCKER | 0 | 16 | 0 |
| HIGH | 40 | 14 | 628 |
| MEDIUM | 26 | 3 | 1124 |
| LOW | 219 | 12 | 856 |
| INFO | 0 | 0 | 0 |
| Всего | 285 | 45 | 2608 |

Quality Gate `OK`; conditions API — пустой список, объяснение условий отсутствует. Security hotspots `0`; duplication `1.6%`; NCLOC `205915`, lines `233432`.

Получены агрегаты с `pageSize=1`, ограниченные выборки 5–20 findings по quality/severity, файловые выборки `create_flow`, `workflow_service` и scheduler. Полный список проекта не загружался. Выборки не являются случайными и не доказывают частоту конкретного правила во всём проекте.

## Метод дальнейшего аудита

1. Проверить SHA, `git status --short`, локальный diff и MCP-агрегаты; сохранить параметры выборки, `paging.total`, страницу и issue key.
2. Получать следующую ограниченную выборку по риску и поверхности. Начинать с непроверенных SECURITY BLOCKER/HIGH и RELIABILITY HIGH; затем runtime MAINTAINABILITY HIGH, позже тестовый/косметический долг. Не скачивать весь проект.
3. Дедуплицировать по issue key. Проверить GitNexus query/context, затем актуальный символ, вызывающий путь и тесты. Даты создания issue не доказывают актуальность runtime-кода.
4. Для бага записывать вход → фактический результат → ожидаемый результат → путь пользователя/API → воспроизведение → ограничение доказательства. Для техдолга — конкретные обязанности/связность и стоимость изменения, а не предполагаемый сбой.
5. Привязать исправление к файлам, регрессионным тестам и критерию завершения. Сохранять явно `не реализовано`, `не проверено в браузере`, `production не проверен`, где применимо.
6. Обновлять этот реестр и краткий статус в `PLANS.md`. После реализации менять статус только по свежим результатам тестов; обновление SonarQube отделять от проверки runtime.

## Реальные дефекты

B1–B5 найдены при проверке области, подсвеченной `python:S3776` в `form_catalog.py`; SonarQube не сообщает эти пять багов отдельными findings. Связанный issue: `ab2731c1-5c87-400a-a003-360eb6d99326`, severity `CRITICAL`, строка 722, complexity 190/15. Не приписывать этим багам severity или отдельный rule ID анализатора.

### B1 — ноль считается пустым обязательным числом — P2 / подтверждён

- Код: `server/tickets/form_catalog.py:1183–1194`, frontend `webapp/src/features/requester/dynamic-form/index.tsx:666–676`.
- Воспроизведение: схема `number`, `required=true`, без min; `validate_form_submission(..., raw_values={"amount": 0})` возвращает `ValueError({"amount": "Поле обязательно"})`; значение `1` принимается. Настоящая frontend-функция `isEmptyDynamicValue` для `0` возвращает `false`.
- Причина: `value or ""` превращает 0 в пустую строку. Эффект: допустимый frontend-ответ отклоняется сервером на создании заявки; только формы, разрешающие 0.
- Исправление: отдельная проверка пустоты числа (`None`), без изменения min/max и required для других типов.
- Приёмка: тесты `test_required_number_accepts_zero`, `test_required_number_rejects_missing`, `test_number_min_still_rejects_zero`; значения 0, "0", 0.0, 1, отрицательное допустимое число, None, "". Backend/frontend должны согласованно разрешать ноль при min=0.

### B2 — разные условия видимости checkbox — P2 / подтверждён

- Код: `_normalize_visible_when` (`form_catalog.py:532–545`), `_field_is_visible`/`_condition_values` (1020–1036), frontend `isDynamicFieldVisible`/`valuesMatch` (79 и 688); тип `RequestFormField.visible_when` в `features/requester/types.ts` допускает boolean/number/null.
- Проверенная матрица после серверной нормализации:

| Вход equals | Сохранённое equals | checkbox | Backend visible | Frontend visible |
|---|---|---|---|---|
| true | "True" | true | true | false |
| "true" | "true" | true | false | true |
| false | "" | false | false | false |
| "false" | "false" | false | false | true |

- Эффект: поле, скрытое интерфейсом, сервер может требовать; значение видимого поля сервер исключает из `submitted_values`, далее оно отсутствует в `request_form_data` (`build_form_custom_fields`). Ошибка false разрушает само условие «покажи при снятой галочке».
- Исправление: единая типизированная семантика условий. При сравнении с checkbox нормализовать boolean и legacy "True"/"False"/"true"/"false" в boolean на обеих сторонах; не выполнять глобальный lowercase текстовых select-значений. Не терять false, числовой 0 и null в нормализации equals/in. Сохранять совместимость существующих пакетов без миграции БД.
- Приёмка: зеркальные parameterized pytest/Vitest для equals/in, true/false, legacy строк, 0, null, массива multi_select, обычных строк с разным регистром. Сохранённый pack → requester form → сбор payload → backend validation должны иметь одинаковую видимость, required и сохранённые значения. Проверить в браузере checkbox → зависимое поле → создание и повторное открытие заявки.

### B3 — ошибка скрытого поля остаётся в errors — P3 / подтверждён для API

- Код: `form_catalog.py:1164–1178` и 1224–1225.
- Воспроизведение: `kind="other"`, скрываемое условием `kind="quantity"` number-поле `amount="invalid"` → `ValueError({"amount": "Недопустимое значение"})`.
- Причина: ошибки собираются до определения видимости, затем скрытые поля пропускаются без удаления ошибки.
- Граница: текущий requester frontend отправляет `collectVisiblePayload`, исключая скрытые поля; обычный UI этим защищён. Баг касается payload API-клиентов/старых форм с остаточными значениями, не доказывает сбой текущего браузерного сценария.
- Исправление: вычислять нормализованные зависимости, но применять errors/required/constraints только к видимым полям; ошибка видимого dependency-поля должна сохраняться. Нельзя игнорировать все ошибки формы.
- Приёмка: `test_hidden_invalid_value_does_not_block_submission`, `test_visible_invalid_value_is_rejected`, `test_invalid_visibility_dependency_is_rejected`; скрытое поле отсутствует и в submitted_values, и в summary_rows.

### B4 — ошибочный regex принимается и молча отключает проверку — P3 / подтверждён

- Код: схема копирует `validation` без проверки regex (`form_catalog.py:798`); `_field_constraint_error:1136–1141` поглощает `re.error`. Admin pack save использует `validate_form_pack_schema` (`form_pack_handlers.py:170`).
- Воспроизведение: схема `validation.pattern="["` успешно нормализуется; submission `code="anything"` принимается.
- Эффект: ошибочно настроенное ограничение становится неработающим. Frontend умеет диагностировать invalid_pattern, но это не заменяет серверную проверку схемы. Утверждения о фактическом сломанном production-пакете нет.
- Исправление: проверять pattern/regex при сохранении и preview схемы; invalid pattern → понятный validation error до публикации. Для уже сохранённой ошибочной схемы вернуть безопасную ошибку конфигурации вместо молчаливого допуска. Согласовать поддерживаемый синтаксис regex Python/JS; не считать две реализации взаимозаменяемыми.
- Приёмка: `test_schema_rejects_invalid_pattern`, `test_submission_does_not_ignore_invalid_saved_pattern`, валидные pattern/regex aliases, anchors, Unicode; ошибочный pack не публикуется, корректный не меняет результаты.

### B5 — строка "false" превращается в отмеченный checkbox — P3 / подтверждён для API

- Код: `_normalize_field_value`, `form_catalog.py:1041–1042`: `bool(raw_value)`; frontend `normalizeDynamicFieldValue:380` корректно преобразует "false" в false.
- Воспроизведение: required checkbox `flag`, payload `{"flag": "false"}` → принят и сохранён как `true`.
- Эффект: некорректные типы payload API могут записать противоположный ответ пользователя и пройти required. Это не доказательство обхода отдельного механизма диагностического согласия: тот контракт не исследован в этом пункте.
- Исправление: строгая и согласованная нормализация checkbox; JSON boolean/null обязательны, legacy строковые значения поддерживать явно, если сохраняем совместимость. Неизвестные строки и объекты/массивы отклонять, не превращать truthiness в согласие.
- Приёмка: `test_checkbox_false_string_is_not_true`, `test_required_checkbox_false_is_rejected`, `test_checkbox_invalid_type_rejected`; матрица true/false, "true"/"false", "1"/"0", "yes"/"no", None, [], {}, "unexpected" с одинаковыми результатами backend/frontend.

### B6 — stop() поглощает отмену вызывающей задачи — P3 / подтверждён локально

- Sonar: `python:S7497`, issue `67f15ab8-be32-4f4f-9ffd-086834667540`, severity `MAJOR` (выборка quality RELIABILITY/HIGH), `server/app/services/problem_candidate_scheduler.py:58`.
- Воспроизведение без БД: создать scheduler с `session_maker=object()` и `enabled=false`; подставить task, который при первой отмене входит в асинхронный cleanup; запустить `stop()` отдельным task; после начала cleanup отменить task самого stop(). Результат: stop возвращается нормально, `cancelling()==1`, `cancelled()==false`.
- Эффект: supervisor/timeout не получает ожидаемый CancelledError остановки. Штатная отмена только дочерней задачи действительно должна поглощаться; механический unconditional raise ломает нормальный shutdown.
- Исправление: различать ожидаемую отмену собственного child и отмену текущего task; внешнюю отмену распространять после необходимой очистки. Не оставлять task работающим после очистки и не обнулять ссылку на живую задачу. Аналогичные stop-методы проверять по одному, не объявлять заранее дефектными.
- Приёмка: новый `server/tests/test_scheduler_stop_cancellation_no_db.py` (`pytestmark=no_db`); `test_stop_consumes_expected_child_cancellation`, `test_stop_propagates_parent_cancellation_during_cleanup`, `test_stop_without_task_is_noop`, повторный stop. Все тесты завершаются без pending tasks; никакого подключения к БД.

## Проверенный техдолг — не подтверждённые runtime-баги

| ID / приоритет | Доказательство | Исправление и критерий |
|---|---|---|
| D1 / P2 | `form_catalog.py:722`, S3776, 190/15: один валидатор объединяет fields/options, visibility, priority compatibility, policy refs и template metadata | После B1–B5 выделить нормализацию полей/условий, валидацию схемы, submission; сохранить фасад `validate_form_pack_schema(raw_pack, *, require_version=True)` и `validate_form_submission(pack, *, form_key, raw_values)`. Сравнить нормализованные пакеты, submission и ошибки на существующих fixtures; CODEMAP обновить при новых модулях. |
| D2 / P2 | `create_flow.py:431–880`: 450 строк, 33 параметра; S107 issue `1b9245a9-0b36-417a-8668-77a382f37031`; S3776 issue `a354e472-e745-49a1-b141-3c5467c29dfa`, 113/15 | Разделить trusted identity/binding, context/custom fields и запись/инициализацию. Группировать параметры в typed internal DTO через совместимый адаптер существующей keyword-only функции. Сохранить порядок routing→SLA→OLA, rollback, idempotency, browser_no_device и VerifiedRequesterBinding. Не объединять непроверенный requester_account с доверенным binding. |
| D3 / P2 | `workflow_service.py:317–750`: 434 строки; S3776 issue `e28e575f-9512-4249-981b-bf5802d6a588`, 98/15; проверки gates/policies, времён, SLA/OLA, revocation и events находятся в одном методе | Выделять чистые builders обновлений и последовательность side effects; сохранить CAS/WorkflowTransitionConflict, role checks, транзакцию, audit, reopen и закрытие public sessions. До рефакторинга зафиксировать результаты status transitions, critical failure и duplicate/concurrent request. |
| D4 / P2 | `webapp/src/pages/tickets/detail-page.tsx`: 3411 строк файла; компонент от 1951 объединяет queries, drafts, diagnostics и presentation; S3776 issue `e917f83a-6724-45e1-a440-a02f51b6c03d`, 141/15 | Разделить controller/hooks и существующие секции по действиям оператора. Сохранить query keys/invalidation, состояния черновиков, diagnostic idempotency/session storage и права. Компонентные тесты и браузерные проверки на 1366×768 и 1920×1080; это рефакторинг поведения, не новый дизайн. |
| D5 / P3 | S9073: `test_support_endpoint_presence.py:68` объединяет online/version в одном assert. S1192: `models.py` повторяет строки FK/ondelete. S6903: `id_generators.py:10` использует utcnow, но строка уже содержит Z | Дробить assert при изменении соответствующего теста; константы вводить только для связанных значений с сохранением SQLAlchemy metadata; timestamp заменить aware UTC с прежним форматом Z. Нет доказательства неверного времени или схемы. Не начинать массовый cosmetic PR ради количества findings. |

## Контекстные срабатывания / изменения не требуются по имеющимся доказательствам

| Rule / пример | Проверка по коду | Решение |
|---|---|---|
| S7503, `domain_ports/unavailable.py:200`; issue `6c91ea83-a4fb-4eb1-b77e-3175921ae27f` | Заглушки реализуют async-интерфейсы, возвращают typed unavailable; `test_domain_ports.py` проверяет await-поведение | Сохранить async. Удаление async создаёт нарушение контракта. Не обобщать это решение на все S7503 в проекте. |
| S2871, `requester/queries.ts:103`; issue `b9013c41-6dc7-4841-93a0-06cf8d1a276e` | `.sort()` канонизирует технические статусы для query key. В `access-groups.tsx` сортируются permission codes/member IDs | localeCompare не исправляет доказанный баг здесь; стабильный порядок технических идентификаторов сохранить. Другие сортировки отображаемых названий требуют отдельной проверки. |
| S2115/S6698 в тестах backup/migration; issue `d795acc0-8c59-42ad-86b8-218662da2a64` | Синтетические тестовые значения и подменённый subprocess; runtime credentials передаются через environment. Backup failure и migration gates тестируются | Не считать тестовое значение утечкой production-пароля; не менять тесты/правила/статусы SonarQube. Это решение касается просмотренных тестов, не всех 45 security issues. |
| S5332, `test_validate_production_config.py:22`; issue `37fa049b-3eb5-4d72-bea9-2b4eff35e809` | HTTP — вход отрицательного теста, production policy должен его отвергнуть | Сохранить отрицательный тест. |
| S5443, `test_deploy_helpdesk_release.py:174/181/193` | /tmp-путь — аргумент проверки сгенерированной deploy-команды, реальный deploy этим тестом не запускается | Уязвимость production этим finding не доказана. Безопасность самого remote_install_command отдельно проверить перед изменением production-логики. |
| S8495, `_allowed_read_roles:75`; issue `ae1cdff2-65b8-4260-99fc-119cc97ecb7e` | Переменная длина tuple отражает включение auditor; позиционного unpacking нет, поиском найдено только определение | Не добавлять фиктивную роль ради одинаковой длины. Проверка доступов остаётся обязательной. |
| S5779, `run_playbook_fix_tests.py:38`; issue `23ec1c9f-8567-4d94-a1fe-8e298dabc491` | AssertionError собирается в failed, при наличии failed вызывается sys.exit(1) | Исключение не превращается в успех при обычном запуске. Режим python -O убирает assert; это отдельный риск тестового harness, не подтверждённый сбой production. |

## Review Focus

- Сохранённые legacy boolean-условия и false/0/null: B2/B5 обязаны проверять совместимость, не только новые формы.
- Скрытые ошибочные ответы и ошибочный видимый dependency: B3 не должен маскировать реальную ошибку пользователя.
- Уже опубликованная схема с invalid regex: B4 должен вернуть безопасную ошибку и не допускать данные молча.
- CancelledError родителя во время asynchronous child cleanup: B6 должен сохранить отмену и отсутствие orphan tasks.
- Registry/Endpoint unavailable, повторное создание и конкурентный transition: D2/D3 сохраняют права, transactional atomicity и audit при всех отказах.

## Implementation Tasks — выполнены

### Task 1: B1 — пустота числовых полей

Files: изменить `server/tickets/form_catalog.py`; создать `server/tests/test_form_submission_edge_cases_no_db.py`. Interface: существующая `validate_form_submission`; return payload/ValueError остаются прежними, кроме исправления 0.

- [x] Добавить no_db parameterized tests из приёмки B1; убедиться, что required_zero падает до исправления.
- [x] Исправить проверку пустоты, выполнить `python -m pytest server/tests/test_form_submission_edge_cases_no_db.py -q`.
- [x] Проверить requester API-сценарий с допустимым 0 через существующие fixtures; исходная ошибка не должна замениться ошибкой priority/context.

### Task 2: B2/B5 — единая семантика checkbox и условий

Files: `server/tickets/form_catalog.py`, `webapp/src/features/requester/dynamic-form/index.tsx`, `webapp/src/features/requester/types.ts` только при необходимости; tests — предыдущий no_db файл и существующий `dynamic-form.test.tsx`.

- [x] Добавить зеркальные тестовые матрицы B2/B5; записать расхождения до изменения.
- [x] Исправить нормализацию/сравнение только для нужных типов, сохранив legacy boolean aliases и чувствительные к регистру обычные строки. Не менять публичную структуру pack/submission.
- [x] Запустить pytest и `npm --prefix webapp test -- src/features/requester/dynamic-form/dynamic-form.test.tsx`; сверить одинаковый payload после save/reload pack.
- [x] Проверить пользовательский сценарий в браузере по проектному workflow: чекбокс, required зависимое поле, сохранение и повторное открытие заявки. Зафиксировать console/network и реальные сохранённые значения.

### Task 3: B3/B4 — границы валидации

Files: `server/tickets/form_catalog.py`; существующие `form_pack_handlers.py` / `web_api/admin_handlers.py` только если требуется согласованное преобразование ошибки схемы; no_db тесты и `server/tests/test_ticket_form_packs.py` для DB/API-публикации.

- [x] Зафиксировать скрытое invalid number, видимое invalid dependency, invalid regex в новом и сохранённом pack.
- [x] Исправить применение errors только к видимым полям и проверку regex при нормализации схемы; сохранить validation aliases и metadata.
- [x] Запустить no_db тесты; затем подходящие DB/API-тесты публикации через изолированный harness по `docs/TESTING_RULES.md`. Проверить, что invalid pack не становится опубликованным.

### Task 4: B6 — отмена scheduler.stop

Files: `server/app/services/problem_candidate_scheduler.py`; новый `server/tests/test_scheduler_stop_cancellation_no_db.py`. Interface: `async stop() -> None`, нормальный stop остаётся идемпотентным, внешняя отмена распространяется.

- [x] Добавить тесты B6 с Event barriers вместо временных sleep; доказать сбой parent cancellation на исходном коде.
- [x] Различить отмену parent/child и обеспечить cleanup; проверить повторную отмену во время cleanup.
- [x] Запустить `python -m pytest server/tests/test_scheduler_stop_cancellation_no_db.py -q`; отдельно проверить `server/tests/test_problem_scheduler.py` через изолированный DB harness.
- [x] Аналогичные stop-методы добавлять в реестр только после отдельного воспроизведения; не переносить исправление автоматически.

### Task 5: D1–D4 — поэтапный рефакторинг после фикса багов

- [x] D1: выделить `server/tickets/form_field_values.py` и `form_schema_validation.py` с односторонними зависимостями; `form_catalog.py` сохраняет фасад и defaults. Не вводить import cycle. До перемещения сохранить characterization tests: результат schema/submission/errors и metadata.
- [x] D2: выделить internal typed input/context helpers в `server/tickets/create_flow.py` или соседний `create_context.py`; сохранить прежний external callable через адаптер. Проверки: create initialization, requester/public idempotency, no-device/binding identity, rollback required side effects.
- [x] D3: сначала выделить чистый builder timestamp/status updates внутри `workflow_service.py`, затем helpers исполнения side effects, сохраняя порядок и транзакцию. Проверки: workflow atomicity/concurrency/side-effect observability и closure/approval profiles.
- [x] D4: выделить `webapp/src/pages/tickets/hooks/use-ticket-detail-controller.ts` и существующие UI-секции в соседние компоненты. Проверки: `detail-page.test.tsx`, workspace tests, `npm --prefix webapp run build`, browser workflow/снимки обоих разрешений. Не сбрасывать черновик сообщения при background refetch.
- [x] После каждого независимого изменения обновить CODEMAP, этот план, evidence и Sonar baseline. Уменьшение complexity не считается успехом без сохранения поведения.

### Task 6: D5 — связанные локальные улучшения

- [x] Разделить presence assertions; добавить связанные FK/ondelete constants без изменения metadata.
- [x] Перейти на aware UTC с прежним форматом Z; проверить timestamp regression и cleanup schema audit.

## Verification — выполнено при создании плана

- [x] Git status/HEAD проверены; исходные отслеживаемые файлы без изменений до записи плана.
- [x] GitNexus `query(repo="helpdesk", ...)` использован перед исследованием; найден workflow и create/submission entrypoints. Выводы сверены с локальными исходниками. Статус свежести индекса этим query не доказан.
- [x] MCP: проект, Quality Gate, метрики, 15 агрегатных счётчиков и ограниченные выборки повторно прочитаны. SonarQube не изменялся.
- [x] B1–B5 воспроизведены прямым импортом реального `tickets.form_catalog` в `python -B`; B2/B5 сверены с настоящими TS-функциями, извлечёнными TypeScript AST и транспилированными в памяти без записи файлов.
- [x] B6 воспроизведён реальным `ProblemCandidateScheduler.stop()` с подставленной локальной async-задачей, без БД/сервиса.
- [x] Существующая узкая проверка: `python -B -m pytest -p no:cacheprovider scripts/test_helpdesk_database_backup.py scripts/test_production_migration_backup_gate.py scripts/test_validate_production_config.py server/tests/test_domain_ports.py server/tests/test_ticket_create_initialization_no_db.py server/tests/test_workflow_atomicity_no_db.py server/tests/test_public_create_atomicity_no_db.py -q --tb=short` → **57 passed in 0.87s**. Это историческая проверка до исправлений; финальные результаты приведены в evidence.
- [x] `python scripts/verify_workspace.py --workspace .` → **Verification passed for .**; `git diff --check` — успешно. Проверены UTF-8, относительные ссылки, наличие шести bug entries, пяти debt groups, пяти tasks и ссылки из `PLANS.md`.
- [x] Постоянные новые регрессионные тесты Tasks 1–4 созданы; начальные RED и последующие результаты описаны в evidence. Историческая verification выше относится к созданию плана.
- Браузер, PostgreSQL API acceptance, production, полный CI и новый Sonar analysis при создании плана не запускались. Утверждений о deployed runtime нет.

## Next Steps / Handoff

Пользователь выбрал локальное объединение с `main` после приёмки. Исправления
записаны отдельными тематическими коммитами; состав и SHA — в evidence.
Объединение выполняется fast-forward, без push, PR или deploy. Финальная
проверка на `main` и полный список файлов коммитов — в локальном integration receipt.


Реализация и приёмка B1–B6 и D1–D5 завершены: 140 backend unit/contract, 529 frontend, 109 в финальных DB/API-наборах и 3 Chromium-сценария прошли. Все временные DB-ресурсы удалены. Build, metadata/schema audit, inventory, workspace и diff checks прошли; независимое повторное review — без замечаний в проверенном объёме. Sonar issues остаются состоянием исходного анализа до отдельного авторизованного scanner run.

Для следующего аудита не загружать заново просмотренные выборки: у RELIABILITY/HIGH просмотрены page 1,size 5 и page 2,size 20 (позиции 6–20 ещё не исследованы этой новой выборкой); SECURITY page 1,size 15; MAINTAINABILITY/HIGH page 1,size 15, MEDIUM page 1,size 15; отдельные файловые выборки create_flow/workflow/scheduler. При новом анализе пагинация меняется — дедупликация по issue key обязательна.

Непроверенные security findings вне перечисленных тестов не закрыты выводом «это тесты». Непросмотренные runtime findings не считаются техдолгом автоматически. Coverage аудита ограничен указанными группами; полный аудит проекта не заявлен.

Новые модули и границы отражены в `server/docs/CODEMAP.md`; браузерный compatibility fixture описан в `docs/TESTING_RULES.md`. Активный router по-прежнему использует TicketListPage; D4 проверен непосредственно на compatibility-компоненте без смены маршрутизации. Итог исправлений и свежие команды проверок — в evidence.
