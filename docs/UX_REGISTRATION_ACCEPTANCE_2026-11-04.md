# Пошаговая регистрация сотрудников — приёмка 04.11.2026

Установлено и проверено на Helpdesk staging (`192.168.101.118`). Стенд оставлен
работающим по прямому указанию пользователя. Production не изменялся.

## Результат для сотрудника

1. ФИО: фамилия, имя, необязательное отчество; предварительный логин.
2. Отдел и связь: поиск по общему справочнику, телефон или внутренний номер.
3. Пароль: проверка и завершение регистрации с уже заполненным профилем.

Логин формирует сервер: `Иван Петров → ipetrov`, при совпадении `ipetrov2`.
Существующие логины не переименовываются. Новая запись получает только роль
`user` и кабинет заявителя. Сотрудники из кадрового документа не импортировались.

После регистрации открывается главная кабинета. Форма обращения открывается
только по явному нажатию «Создать обращение». Регистрация не создаёт заявку.
Старый неполный профиль также проходит пошаговое заполнение и возвращается на
главную. Локация не требуется; исторические значения сохраняются.

## Справочники и сохранность данных

Из двух таблиц DOCX извлечены 42 заголовка и сформирован один список из 30
уникальных отделов. Муниципальные и технические работники используют общие
отделы. Исправлены только три зафиксированных варианта написания.
SHA256 исходного документа:
`5ed409e76c1544dd0387af9cf1b97aad73c6b093d156524621dc9480db9c436a`.
В репозитории опубликованы только названия отделов.

Через штатные аудируемые операции Registry созданы 30 отделов, архивированы
29 точно определённых тестовых подразделений и 29 тестовых локаций. Они убраны
из активного выбора. Записи не удалены, исторические ссылки не переназначены.

До/после публикации совпали хеши данных 41 существующей карточки человека,
одного актива, нуля строк членства и 72 снимков обращений. Повторная публикация
не добавила записи или аудит. Финальное чтение БД: 30 активных отделов точно
совпадают с каталогом; активных локаций 0; архивных отделов/локаций по 29;
людей 42 после одной собственной тестовой регистрации; обращений по-прежнему 72.

## Релиз и восстановление

Ветка: `codex/ui-support-001`. Локальные коммиты, без push/PR:

- `d4a5b8774900502721180938c1988cdf30e7361a` —
  `feat(auth): configure staging requester registration`.
- `fc3117756335c045894db9bdefa79b97184115b9` —
  `feat(auth): guide requester signup with complete profiles`.
- `153dc3faf16f2759469c84758f131d58a4f538ca` —
  `feat(registry): publish shared requester department catalog`.

Установленный SHA приложения: `153dc3faf16f2759469c84758f131d58a4f538ca`.
Применена миграция `151 → 152`: таблица квитанций повторной регистрации.
Аккаунт, профиль и квитанция создаются атомарно. Повтор запроса проверяет
исходные данные и пароль; пароли в квитанциях не хранятся. Проверка сложности
пароля учитывает окончательный логин с суффиксом.

Перед релизом сделана штатная приватная резервная копия:
`/var/backups/helpdesk-onboarding-20261104/backup.json`, размер 13 362 460 байт,
SHA256 `dcce467628b26d42cf6e6909c518ccd3c9784c6514fa0e2c7437fe0455c27bd3`.
Исходный релиз `376b46c012160473fe2ebc40a0185784f692e487`, миграция 151.
Установка выполнена через `scripts/deploy_helpdesk_release.py` штатным staging
wrapper. Файлы работающего релиза вручную не правились.

Финально: сервис `helpdesk-staging.service` active, HTTPS health 200 с проверкой
TLS; self-registration и SSO включены. 21 нормализованный SHA256 исходных файлов
совпал с Git blobs установленного коммита. OIDC initiation использует staging
client, PKCE S256, без `acr_values`/MFA claims. Полный новый вход с реальными AD
учётными данными в этой приёмке не выполнялся; это ограничение проверки,
предыдущая AD-приёмка не заменяет свежий вход.

## Проверки

Проверки запускались по мере реализации; итоговые исправления проверены
фокусными повторами. Полный CI, нагрузочная проверка и production gate не запускались.

| Команда / проверка | Результат |
| --- | --- |
| `pnpm --dir webapp test` | 160 файлов / 955 тестов прошли до последней небольшой правки profile-save-home |
| `pnpm --dir webapp test src/pages/requester/profile-page.test.tsx src/features/auth/guided-registration.test.tsx` | 11 прошли на итоговых изменениях; отдельный profile-save-home повтор — 7 прошли |
| `pnpm --dir webapp build` | TypeScript и Vite прошли; итоговый bundle `index-DyQ-Ziaa.js` |
| `python -m pytest server/tests/test_web_session_api.py server/tests/test_domain_import_boundaries.py -m no_db -q --tb=short` | 63 прошли |
| noDB signup/schema/script targets | 24 прошли; configuration helper отдельно 3; catalog pure отдельно 6 |
| `python tmp/onboarding-20261104/db_tests.py` | Исходный расширенный прогон: 60 прошли / 2 устаревших fixture-ожидания упали; исправлены ниже |
| `python tmp/onboarding-20261104/db_review_green.py` | 4 прошли: скрытые поля сохраняются, policy окончательного логина, текущий архивный отдел, bootstrap без required location |
| Исправленный noDB chat-conflict fake | 1 прошёл; production-код переписки не менялся |
| Первичный изолированный signup DB прогон | 5 прошли: повтор UUID, конкурирующие однофамильцы, rollback, обычная роль, legacy signup |
| Catalog DB integration в расширенном прогоне | прошёл: точный synthetic-only archive, 30 отделов, no-op, stale fingerprint, сохранённые ссылки |
| `npx playwright test tests/requester-registration.spec.ts tests/requester-workspace.spec.ts -g "registration\|existing incomplete\|rating and reopen" --output ../tmp/onboarding-20261104/browser-review-final` из `webapp` | 5 прошли на свежем bundle: signup 3 размера, существующий неполный профиль, rating/reopen с актуальными кнопками раскрытия |
| `python scripts/verify_workspace.py`, `git diff --check` | прошли |

Тесты PostgreSQL выполнялись только в изолированных временных БД с отдельной
ролью на staging-host, не против рабочей staging БД. Временные БД и роли удалены.
Первичный review-red показал потерю скрытой metadata; исправление подтверждено
green-прогоном. Две ошибки расширенного прогона — старое required-location
ожидание и fake без `get_ticket(for_update=True)` — исправлены и проверены
фокусно; повтор всех 62 не заявляется. В старом browser rating/reopen fixture
добавлены два явных раскрытия уже существующих действий, без изменения продукта.

Независимый read-only review завершён без оставшихся actionable findings.
Проверены публичная проекция схемы, повтор неопределённого ответа после reload,
проверка окончательного логина, архивный текущий отдел и сохранение скрытых полей.
GitNexus использован для архитектурного контекста; транзакционные defaults и
динамические вызовы подтверждены исходниками/тестами. Новых зависимостей и
изменений HTTP-контрактов Endpoint Platform нет.

## Живой браузер

Через отдельный Playwright MCP браузер зарегистрирован собственный синтетический
пользователь `tproverochnyy-onbording`, роль `user`, только `requester` workspace.
Регистрация 201, канонический вход 200, профиль заполнен и сохранён; выбран
«Отдел информационных технологий», локация отсутствует. Перезагрузка и новый
парольный вход сохранили готовность профиля. Главная открылась до ручного
перехода в форму обращения. Автоматических ticket POST — 0, реальная заявка
не создавалась. Page errors и console errors — 0, API ответы 200/201.

После проверки выполнен выход из синтетической записи. Открыта публичная форма
регистрации; размер агентского браузера восстановлен. Пользовательская вкладка
и её профиль не менялись. Синтетический аккаунт оставлен как след приёмки,
секреты не выводились и не сохранялись в evidence.

Приватные доказательства: `tmp/onboarding-20261104/` — логи, backup receipt,
`catalog-applied.json`, `postdeploy.json`, `final-readback.json`,
`live-registration-1366.png`, `live-home-1366.png`. Скриншоты и кадровые данные
не включены в Git. Стандартные предупреждения Vite chunk size, aiohttp/Authlib
и Windows teardown отделены от ошибок приложения.

## Файлы коммитов реализации

Точный состав: `git show --name-only <SHA>` для трёх коммитов выше.
Основные изменённые поверхности:

- `scripts/configure_helpdesk_registration.py`, его тест;
  `scripts/helpdesk_requester_departments.py`, его тест.
- `server/auth/requester_registration.py`, `middleware.py`;
  `server/web_api/session_handlers.py`, `dto/session.py`, `server/routes.py`.
- `server/app/db/models.py`, `server/app/repos/ui_users_repo.py`,
  `server/app/db/migrations/versions/20261104_152_requester_registration.py`.
- `server/registry/profile_schema_service.py`, `registration_form_service.py`,
  `requester_departments_20260831.json`; `server/requester/identity_service.py`.
- `server/tests/test_requester_profile_without_location_no_db.py`,
  `test_requester_registration_api_no_db.py`, `test_requester_registration_db.py`,
  `test_requester_registration_no_db.py`, `test_requester_departments_db.py`,
  `test_requester_workspace_api.py`.
- `webapp/src/features/auth/register-page.tsx`, `register-page.test.tsx`,
  `registration-wizard.tsx`, `requester-registration.ts`, `guided-registration.test.tsx`.
- `webapp/src/features/requester/profile-runtime/index.tsx`,
  `profile-runtime.test.tsx`, `profile-without-location.test.tsx`;
  `webapp/src/features/requester/types.ts`, `webapp/src/app/navigation.tsx`.
- `webapp/src/pages/requester/home-page.tsx`, `profile-page.tsx`,
  `profile-page.test.tsx`, `profile-panels.tsx`, `profile-workflow.ts`.
- `webapp/tests/requester-registration.spec.ts`, `requester-workspace.spec.ts`.
- `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `server/docs/CODEMAP.md`,
  spec и plan от 04.11.2026, только собственный раздел `PLANS.md`.

Чужие изменения рабочего дерева сохранены. Последующий коммит приёмочной
документации не требует повторного развёртывания приложения.
