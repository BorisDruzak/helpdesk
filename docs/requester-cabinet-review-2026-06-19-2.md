# Корректировки по проверке исполнения — requester cabinet

Дата проверки: 2026-06-19.

Проверенный диапазон: `e68c62e257bfaeffeb3e26bb41f00476c57ad843..00d948e8ea51759c60eaaf9efc604a9f51b31ac7`.

Новый проверенный коммит: `00d948e8ea51759c60eaaf9efc604a9f51b31ac7`.

## Вердикт

Коммит синхронизировал Knowledge bindings с текущими Service Catalog defaults и добавил setup-help offerings для профиля и привязки устройства. Критичных регрессий по маршрутам requester, shared UI, Tailwind-разметке, динамическим формам и конструктору профиля в изменённых файлах не найдено, потому что этот коммит не меняет соответствующий frontend runtime. Найдено одно проверенное терминологическое расхождение в публичных описаниях Service Catalog.

## Проверено

- `PLANS.md` на ветке `codex/helpdesk-process-model`.
- Diff `e68c62e257bfaeffeb3e26bb41f00476c57ad843..00d948e8ea51759c60eaaf9efc604a9f51b31ac7`.
- `server/tickets/service_catalog_defaults.py`.
- `content_packs/knowledge/primary-agent-requester-guides.yaml`.
- `scripts/validate_knowledge_pack_bindings.py`.
- `server/tests/test_knowledge_pack_bindings.py`.
- `server/tests/test_service_catalog_seed.py`.
- `docs/QUICK_LOOKUP.md` и `scripts/navigation_catalog.py` как drift/navigation контекст.

## Найденные расхождения и точные корректировки

### P1 — Публичные описания Service Catalog снова используют термин `Заявка`

Факт: новые публичные setup-help offerings в `server/tickets/service_catalog_defaults.py` используют `Заявка на помощь...` в `short_description` для помощи с профилем и привязкой устройства.

Почему это проблема: раздел 5 `PLANS.md` требует использовать `Обращение`, а не смесь `тикет` / `заявка` / `обращение`. Так как элементы Service Catalog имеют `visibility: public`, эти строки могут попасть в requester-visible каталог или подсказки.

Исправление:

- заменить `Заявка на помощь с обязательными полями профиля пользователя` → `Обращение за помощью с обязательными полями профиля пользователя`;
- заменить `Заявка на помощь с привязкой устройства или агента к аккаунту` → `Обращение за помощью с привязкой устройства к аккаунту` или `Обращение за помощью с подключением рабочего устройства`;
- добавить regression/static guard на публичные `public_title` / `short_description` Service Catalog defaults: не допускать `заявк` в requester-visible строках, кроме административной документации.

## Блок для вставки в конец `PLANS.md`

```md
## Корректировки по проверке исполнения

### Проверка 2026-06-19 — commit `00d948e8ea51759c60eaaf9efc604a9f51b31ac7`

**Вердикт:** коммит синхронизировал Knowledge bindings с текущими Service Catalog defaults и добавил setup-help offerings для профиля/привязки устройства. Критичных регрессий по маршрутам requester, shared UI, Tailwind-разметке, динамическим формам и конструктору профиля в изменённых файлах не найдено. Найдено одно терминологическое расхождение в публичных строках Service Catalog.

1. **P1 — Терминология Service Catalog:** в `server/tickets/service_catalog_defaults.py` заменить публичные `short_description` со словом `Заявка` на формулировки через `Обращение`; добавить static guard на requester-visible `public_title` / `short_description`, чтобы `заявк` не возвращалось в публичный каталог обращений.
```
