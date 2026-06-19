# Корректировки по проверке исполнения — requester cabinet

Дата проверки: 2026-06-19.

Проверенный коммит: `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f` (`server: complete requester cabinet refactor`).

Базовый коммит плана: `a37d7378b17a3c607db6b8e207a8002b15113c8d` (`docs: replace active plan with requester UI refactor`).

## Вердикт

Рефакторинг кабинета пользователя фактически перенёс requester UI на разделённые маршруты, shared runtime и отдельные страницы, но часть отметок `PLANS.md` о полном закрытии фаз преждевременна. Ниже зафиксированы только проверенные расхождения по коду и плану.

## Проверено

- `PLANS.md` после коммита `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f`.
- Изменённые requester routes/pages/runtimes: `webapp/src/app/router.tsx`, `webapp/src/pages/requester/new-request-page.tsx`, `webapp/src/pages/requester/tickets-page.tsx`, `webapp/src/features/requester/dynamic-form/index.tsx`, `webapp/src/features/requester/profile-runtime/index.tsx`, `webapp/src/features/requester/labels.ts`, `webapp/src/features/requester/api.ts`.
- Конструктор профиля: `webapp/src/features/admin/registry/registry-profile-schema-tab.tsx`.
- Изменённые серверные и документационные файлы по diff коммита `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f`.

## Найденные расхождения и точные корректировки

### P1 — Терминология requester UI нарушает Russian terminology contract

Факт: в `webapp/src/pages/requester/new-request-page.tsx` остались requester-visible строки с термином `заявка` и английским `preview`:

- `Детали заявки`;
- `Проверить заявку`;
- `Не удалось проверить заявку`;
- `Каталог заявок`;
- `Безопасный preview`.

Почему это проблема: раздел 5 `PLANS.md` требует использовать `Обращение`, а не смесь `тикет` / `заявка` / `обращение`; UI должен быть Russian-first и без технических терминов.

Исправление:

- заменить `Детали заявки` → `Детали обращения`;
- заменить `Проверить заявку` → `Проверить обращение`;
- заменить `Не удалось проверить заявку` → `Не удалось проверить обращение`;
- заменить `Каталог заявок` → `Каталог обращений` или `Подходящий тип обращения`;
- заменить `Безопасный preview` → `Безопасная проверка`;
- расширить static/localization guard на requester-visible строки `заявк` и `preview`.

### P1 — Detail/chat URL строится на `ticket_id`, а не на безопасном пользовательском коде

Факт: `webapp/src/pages/requester/tickets-page.tsx` строит ссылку `/app/requester/tickets/${ticket.ticket_id}`, а `webapp/src/pages/requester/new-request-page.tsx` после создания ведёт на `/app/requester/tickets/${result.ticket_id}`. При этом типы содержат и `ticket_id`, и `ticket_code`.

Почему это проблема: разделы 1, 5, 7 и Definition of Done требуют human request code и отсутствие raw IDs в requester-visible UI/URL.

Исправление:

- использовать в requester URL человекочитаемый безопасный код обращения (`ticket_code` или отдельный requester-safe slug/public code), а не внутренний `ticket_id`;
- добавить серверный resolver `safe_code -> internal ticket_id` с проверкой владения обращением;
- оставить `ticket_id` только внутри API-контракта;
- добавить тест, который проверяет отсутствие UUID/internal id в requester DOM и URL.

### P1 — Dynamic request `file` field считается поддержанным, но публикация и runtime заблокированы

Факт: `webapp/src/features/requester/dynamic-form/index.tsx` включает `file` в `ALL_DYNAMIC_REQUEST_FIELD_TYPES`, но `validateDynamicFormSchema()` блокирует публикацию file-полей (`requester_file_upload_disabled`), а `RequestFormFieldControl` рендерит disabled file input и текст, что публикация requester-visible file поля заблокирована.

Почему это проблема: Phase F и Definition of Done отмечены как выполненные, включая тезис, что каждый поддержанный конструктором тип работает. При текущей реализации `file` не является полноценно работающим requester-visible типом.

Исправление — выбрать один из двух путей:

1. Реализовать draft upload до создания обращения: TTL, size/type limits, caller-owned references, serialization, validation, preview, create payload, constructor preview и E2E.
2. Либо явно убрать `file` из publishable requester scope/DoD до реализации upload и оставить его как непубликуемый тип с отдельной пометкой в плане.

### P2 — Frontend может показать raw server error text

Факт: `webapp/src/features/requester/api.ts` формирует `RequesterApiError` из серверных `message` / `error`, а `requesterErrorMessage()` в `webapp/src/features/requester/labels.ts` возвращает `error.message` напрямую. Страницы затем показывают это пользователю.

Почему это проблема: раздел 5 `PLANS.md` запрещает raw server exception text в requester-visible errors.

Исправление:

- показывать только whitelist пользовательских сообщений или маппинг `error_code/status -> безопасный русский текст`;
- серверное `message` использовать только если оно явно помечено как requester-safe;
- добавить тест: backend отдаёт технический текст, requester UI показывает безопасный fallback.

### P3 — Progress log и commit strategy разошлись с фактическим коммитом

Факт: `PLANS.md` содержит правило `Do not combine the whole refactor into one commit`, но `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f` одним коммитом закрывает Phase A–N и большой набор frontend/server/docs файлов. Также phase completion records ещё содержат `Commit(s): not committed yet`.

Почему это проблема: это не runtime-регрессия, но ухудшает трассируемость исполнения плана.

Исправление:

- добавить в `PLANS.md` traceability note, что Phase A–N фактически попали в commit `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f`;
- обновить phase completion records, где указано `Commit(s): not committed yet`;
- в следующих итерациях держать фазовые коммиты меньше или явно фиксировать исключение.

## Блок для вставки в конец `PLANS.md`

```md
## Корректировки по проверке исполнения

### Проверка 2026-06-19 — commit `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f`

**Вердикт:** рефакторинг кабинета пользователя перенёс requester UI на разделённые маршруты и shared runtime, но часть отметок о полном закрытии фаз преждевременна. Ниже зафиксированы проверенные расхождения.

1. **P1 — Терминология requester UI:** заменить `Детали заявки`, `Проверить заявку`, `Не удалось проверить заявку`, `Каталог заявок`, `Безопасный preview` на Russian-first формулировки через `обращение` / `Безопасная проверка`; добавить static guard на `заявк` и `preview`.
2. **P1 — URL обращения:** заменить requester route param с raw `ticket_id` на безопасный человекочитаемый код обращения с серверным resolver и тестом на отсутствие internal id в DOM/URL.
3. **P1 — Dynamic file field:** либо реализовать draft upload до создания обращения, либо исключить `file` из publishable requester scope/DoD до реализации.
4. **P2 — Ошибки API:** не показывать `message/error` сервера напрямую; маппить `error_code/status` в безопасные русские пользовательские сообщения.
5. **P3 — Трассируемость:** обновить phase completion records с `Commit(s): not committed yet` на commit `a64d4cc87e9cd49d7a2533bd65e89f5a7701782f` и зафиксировать исключение из правила не объединять весь refactor в один commit.
```
