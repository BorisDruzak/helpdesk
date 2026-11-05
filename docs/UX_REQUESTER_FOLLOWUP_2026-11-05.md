# Исправления кабинета сотрудника — 05.11.2026

Все четыре конкретных замечания к интерфейсу исправлены и установлены на
Helpdesk staging. Сервис оставлен работающим. Production и Endpoint не изменялись.
WorkTime исследован отдельно; общий вход с локальным паролем Helpdesk не реализован.

## Поведение

- Регистрация: одно поле «Отдел» одновременно ищет и выбирает отдел. В БД
  отправляется ID явно выбранного варианта; произвольный текст не сохраняет
  старый ID. Стрелки/Enter выбирают вариант без перехода на следующий шаг.
- У пароля и подтверждения отдельные кнопки показа/скрытия. Они не отправляют
  форму, не теряют значения и не сохраняют пароль в браузерное хранилище.
- В создании обращения один поиск по каталогу. Нажатие на пустое поле открывает
  все доступные категории, категория раскрывает опубликованные проблемы.
  Раскрытие не запускает сценарий. Выбор проблемы запускает или продолжает её
  сценарий; обычная категория открывает прежнюю форму. Второй поиск и отдельный
  select категории удалены. Черновики, ссылки, ограничения доступности и
  повторное открытие того же сценария сохранены.
- Привязка: инструкция «скрытые значки Windows → правый клик Endpoint Agent →
  Привязать компьютер к Helpdesk → Скопировать код». Два присланных изображения
  показываются по раскрытию. Объяснены срок действия, новый код и отсутствие
  агента. Скриншот с настоящим кодом не публиковался. Проверка владения и
  существующий разбор конфликтов не менялись.

## WorkTime: подтверждённая причина и следующий шаг

На стенде открыта `/employee/login`: предлагается доменный вход через
`/auth/employee/login`. Текущий Endpoint runtime:
`/opt/endpoint-staging/releases/endpoint-platform-1b6ce5a83dd1`.
Его `auth/oidc.py` проверяет issuer, subject и `ad_object_guid`, затем обращается
к `helpdesk_identity_client.resolve(...)`. `auth/employee_sessions.py` принимает
отдельную cookie `endpoint_employee_session` и перепроверяет активность личности
и исходной SSO-сессии. Helpdesk-навигация сейчас содержит обычную фиксированную
ссылку, без передачи Helpdesk-сессии или пароля.

Поэтому новая локальная учётная запись Helpdesk сама по себе не даёт входа в
WorkTime. Для доменного аккаунта используется общий SSO и подтверждённая связь
с карточкой сотрудника; один и тот же отображаемый логин такой связи не доказывает.
Свежий вход с реальными AD credentials не выполнялся, привязки не создавались.

Для входа именно через локальную сессию Helpdesk нужен отдельный согласованный
контракт: кнопка «Войти через Helpdesk», короткоживущий одноразовый код перехода,
проверка кода сервером Endpoint и активной карточки сотрудника. Пароль/Helpdesk
cookie между сервисами передавать не нужно. Следует отдельно определить
допустимость локальных сотрудников без AD и источник их личности в WorkTime;
доменную личность и полномочия нельзя назначать по совпадению ФИО/логина.
Это дальнейшее изменение двух сервисов, не переключатель текущей ссылки.

GitNexus group status: индексы и контракты helpdesk-platform актуальны, missing
repos отсутствуют; uncommitted/local changes учитывались отдельно. Вывод о
WorkTime основан также на чтении фактического runtime, а не только на индексе
или старой локальной ветке. Новых межсервисных контрактов в этой работе нет.

## Проверки

- RED: четыре новые проверки ожидаемо упали на исходном поведении, 11 прошли.
- Итоговый `pnpm --dir webapp test` с пятью целевыми файлами:
  `src/pages/requester/new-request-page.test.tsx`,
  `src/features/auth/guided-registration.test.tsx`,
  `src/features/requester/catalog-search.test.tsx`,
  `src/features/requester/scenario-entrances.test.tsx`,
  `src/pages/requester/device-link-page.test.tsx` — **41 passed**, 5.29s.
- `pnpm --dir webapp build` — TypeScript/Vite прошли. Итоговый bundle:
  `index-CUzyHLNP.js`, совпадает с канонической сборкой релиза.
- `pnpm --dir webapp exec playwright test tests/requester-registration.spec.ts
  tests/requester-usability.spec.ts tests/requester-workspace.spec.ts`:
  первый общий прогон — 27 passed/3 failed. Новые три сначала поймали неточный
  selector текста кнопки, затем реальную недоступность `/guides` на сервере.
  Selector исправлен; изображения импортированы через Vite в `/assets`.
- Итоговый повтор `pnpm --dir webapp exec playwright test
  tests/requester-usability.spec.ts --output
  ../tmp/requester-usability-20261105/browser-green-final` — **3 passed**, 10.6s.
  Проверены1366×768,1920×1080,390×844; обе картинки загружены, горизонтального
  body-scroll нет, кнопка привязки видна на desktop без прокрутки. Повтор signup
  и существующего неполного профиля отдельно — 4 passed. Это разные прогоны,
  а не заявление о едином повторном запуске всех30.
- `python scripts/verify_workspace.py`, `git diff --check` — прошли.
- Независимый read-only review, включая финальный перенос assets: замечаний нет.

Полный CI/backend/нагрузочный прогон не требовался и не запускался: серверная
логика, API, схема и зависимости не менялись. Warnings Vite/NO_COLOR отделены
от ошибок приложения. Browser fixtures не считаются доказательством реального
создания заявки или привязки устройства.

## Развёртывание и живая приёмка

Приложение установлено штатным `scripts/deploy_helpdesk_release.py` через staging
wrapper, только на `192.168.101.118`. Точный SHA:
`ecd784075a2d758125ae5568ff2b682aeb57c639`.
Сервис active, HTTPS health200 с проверкой TLS;28 исходных файлов совпали с Git
по нормализованным хешам. Обе PNG доступны по HTTPS200 с `image/png`, байтовые
SHA256 совпали с файлами сборки. Self-registration/SSO включены, OIDC initiation
по-прежнему использует PKCE S256 без запроса MFA claims/acr_values.

Приватная резервная копия перед релизом:
`/var/backups/helpdesk-requester-usability-20261105/backup.json`,
13 491 799 байт, SHA256
`c110e5fc6d9924f7e8b38356c8fab17c9c4ccbd7b0ebaf240bfa0615eca25844`.
Исходный SHA153dc3faf16f2759469c84758f131d58a4f538ca; миграция остаётся152.
Локальный вызов wrapper с аргументом HEAD был отклонён его SHA guard до SSH;
повтор выполнен с полным SHA. Работающий релиз вручную не правился.

В пользовательской IAB-сессии проверены реальные категории и поиск «принтер»:
одно поле поиска каталога, старых category-select/локального поиска0. Сохранённая
категория «Сканирование и распознавание» осталась выбрана; реальные проблемы
показаны внутри неё. Проблемы не запускались, формы не отправлялись. Обе картинки
инструкции loaded; console errors0. До refresh проверено отсутствие введённого
кода. Вкладка возвращена на исходную страницу привязки, код остаётся пустым.

В отдельном браузере на реальной странице регистрации проверены поиск и выбор
отдела и обе кнопки видимости пароля. Только GET capabilities/me/options200,
регистрация не отправлялась; новых аккаунтов/заявок/привязок не создано. Ошибок
консоли0; временный viewport восстановлен. Скриншоты live-department.png и
live-password.png содержат только синтетические поля, без открытого пароля.

## Коммиты и файлы

- `3826613771bd14b93b0d0384680dfe3e2ce51e84` —
  `feat(auth): simplify department selection and reveal signup passwords`:
  components/ui/searchable-select.tsx, password-input.tsx, registration-wizard,
  guided-registration tests, requester-registration browser spec и contract.
- `6d0cf7c0c8eed87315e93a693690bcba5d7ad130` —
  `feat(requester): unify catalog search and category browsing`:
  catalog-categories, catalog-search, scenario-entrances и тесты; new-request
  page/panels/workflow и тесты; requester-workspace browser spec; contract/CODEMAP.
- `ecd784075a2d758125ae5568ff2b682aeb57c639` —
  `feat(requester): explain how to obtain a device binding code`:
  device-link-page и тест, две PNG в src/assets/guides, requester-usability
  browser spec, contract/CODEMAP и план реализации.

Точный список файлов доступен через `git show --name-only <SHA>`.
Следующий коммит приёмки включает этот отчёт, завершение плана и только
собственный раздел PLANS.md. Ветка codex/ui-support-001; push/PR не выполнялись.
Чужие dirty/untracked файлы сохранены. Приватные логи/receipt/screenshots:
`tmp/requester-usability-20261105`. Стенд оставлен работающим по указанию пользователя.
