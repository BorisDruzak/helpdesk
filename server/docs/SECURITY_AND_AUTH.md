# Безопасность и аутентификация

Документация по безопасности, аутентификации и авторизации сервера PC Agent.

**Дата обновления:** 2026-04-20

---

## Обзор

- **Агенты:** аутентификация по токену (agent token) при WebSocket handshake и при HTTP API.
- **UI:** legacy shell-страницы используют логин/пароль с выдачей UI токена; новый `webapp` под `/app/*` использует тот же UI token storage на сервере, но выдаёт его клиенту только как httpOnly cookie-session.
- **HTTP API:** все `/api/*` маршруты (кроме whitelist) защищены middleware по токену (Bearer/Token/X-Auth-Token), а `/api/web/*` дополнительно умеют читать cookie `pc_client_web_session`.
- **Control-plane:** отдельный сервис на порту `8667` использует те же Bearer UI/agent токены, но имеет собственный middleware, CORS-ограничение по origin и отдельный RBAC для runtime actions.
- **Роли и контекст:** `AuthContext` — единственный источник истины для `actor_id` и `actor_role`; данные из JSON/WebSocket payload **никогда** не доверяются для роли.

---

## 1. Токены

### 1.1 Хранение токенов (БД)

- В БД сохраняется **только SHA256 hash** токена, **не** сам токен.
- Клиент получает **сырой (raw) токен** один раз при выдаче и обязан хранить его безопасно.
- Для логов используется **префикс токена** (первые 8 символов), не полный токен.

**Таблицы:**

- `agent_tokens` — токены агентов (привязка к `device_id`).
- `ui_tokens` — токены UI пользователей (привязка к `user_login`, `actor_role`).

**Поля (agent_tokens):**

- `token_hash` (PK) — SHA256 в hex (64 символа).
- `token_prefix` — первые 8 символов raw токена (для логов).
- `device_id`, `created_at`, `expires_at`, `revoked_at`, `last_used_at`.
- Поддержка ротации: `replaced_by_token_hash`, `rotated_at` (grace period 5 минут).
- `device_id` в `agent_tokens` связан с `devices.device_id` через FK `ON DELETE CASCADE`, поэтому при выпуске токена сервер должен иметь запись устройства.
- Если токен выдан до первого реального handshake, сервер создаёт лёгкую placeholder-запись устройства (`protocol_version="pending"`), а затем обогащает её при первом успешном подключении агента.

**Проверка токена:**

- Токен валиден только если: запись найдена по hash, не отозван (`revoked_at IS NULL`), не истёк (`expires_at` в будущем или NULL), не заменён (или в пределах grace period после `rotated_at`).
- При успешной проверке обновляется `last_used_at`.

### 1.2 Лимиты и сроки

- **Agent token:** максимум **2 активных токена** на один `device_id`. Срок по умолчанию при выдаче: **180 дней** (4320 часов). При превышении лимита — HTTP 429, сообщение «Token limit exceeded».
- **UI token:** срок по умолчанию при выдаче: **24 часа** (в `handle_ui_login`).
- **Local no-DB fallback:** если DB-path недоступен, а config-fallback включён, `AuthService.authenticate()` уходит на `state.users`, а `generate_ui_token()` / `verify_ui_token()` / `revoke_ui_token()` используют in-memory fallback store. После первой DB-ошибки web auth включает короткий cooldown на повторные UI token probe, чтобы `/app/*` не подвешивал локальный dev smoke постоянными retry к недоступной PostgreSQL. Это только локальная/degraded схема для dev smoke, не production storage model.

### 1.3 Отзыв токенов

- **Agent:** `POST /api/devices/{device_id}/tokens/revoke` с телом `{"token_hash": "..."}`. Отзыв по hash (сырой токен клиентом не передаётся).
- **Список токенов устройства:** `GET /api/devices/{device_id}/tokens` (требует аутентификации). Возвращает список записей с `token_hash`, `token_prefix`, датами, флагом `is_active`.
- **Архивирование устройства:** `DELETE /api/devices/{device_id}` доступен только роли `admin`. Сервер best-effort закрывает live WebSocket-сессию агента, очищает runtime-кэши, отзывает активные agent token, гасит pending connection request / outbox / активные operations и помечает устройство как архивное через `devices.deleted_at/deleted_by/delete_reason`. История аудита, событий, снапшотов и тикетов сохраняется.

---

## 2. Аутентификация агента (WebSocket /ws)

Протокол: **Protocol V3 (ws_ticket_v3)**.

### 2.1 Handshake

1. Агент отправляет первое сообщение с `type: "handshake"`.
2. **Обязательно:**
   - `protocol_version === "ws_ticket_v3"`. Иначе соединение закрывается с кодом 4003 и сообщением «Protocol V3 (ws_ticket_v3) required».
   - В `meta.capabilities` должны быть: `protocol_v3`, `envelope_v3`, `outbox_ack_v3`. Иначе закрытие с кодом 4003.
   - Поле `token` (сырой токен агента). Без токена — закрытие с кодом 4003, «Token required».
3. Сервер проверяет токен через `AuthService.verify_agent_token(token)` (БД).
4. При невалидном токене соединение закрывается с кодом 4003, «Invalid token».
5. **Критично:** `device_id` берётся **только из записи токена в БД**, не из payload.
6. Identity v1: сервер трактует `device_id` как канонический `machine_id`. Поля `payload.machine_id` и `payload.install_id` принимаются как metadata; `payload.machine_id` должен совпадать с top-level `device_id`, а `install_id` не должен использоваться как primary auth identity.
7. **Controlled reprovision / migration:** если токен был выдан на свежий placeholder-`device_id`, но агент пришёл с payload `device_id`, который уже известен серверу как реальное устройство, сервер сначала перепривязывает этот токен к уже существующему `device_id`, а затем продолжает handshake. Тот же контролируемый путь допускается для миграции legacy install-based token binding: когда token-bound `device_id == payload.install_id`, а канонический `payload.device_id` уже равен `machine_id`, сервер может один раз перебиндить токен на canonical `machine_id`, записав это в runtime audit как migration.
8. Если payload `device_id` не подходит под controlled reprovision, используется `device_id` из токена и пишется предупреждение в лог.
9. После успешной проверки создаётся `AuthContext(actor_id=device_id, actor_role="agent", auth_type=AuthType.AGENT_TOKEN)` и сохраняется в метаданных соединения.

Попытки подключения без токена или с невалидным токеном при известном `device_id` записываются в `state.pending_connections` (для отображения в админке).

---

## 3. Аутентификация UI (WebSocket /ws_ui)

### 3.1 ui_hello

1. Клиент должен первым делом отправить сообщение с `type: "ui_hello"` и полем `token` (сырой UI токен).
2. Без токена или с невалидным токеном сервер отправляет `type: "error"` и закрывает соединение с кодом 4003.
3. **Критично:** `actor_role` и `user_login` берутся **только из записи токена в БД**, не из payload. Если в payload указана другая роль — используется роль из токена, в лог пишется предупреждение.
4. После успешной проверки создаётся `AuthContext` и сохраняется в данных соединения; клиенту отправляется `ui_hello_ack` с `connection_id` и `role` (из токена).
5. Все последующие сообщения (subscribe_ticket, subscribe_device, ping и т.д.) обрабатываются только если уже выполнён успешный `ui_hello`; иначе возвращается ошибка «Authentication required. Send ui_hello first.»

---

## 4. HTTP API: middleware и whitelist

### 4.1 Middleware

- Применяется ко всем запросам с путём, начинающимся с `/api/`.
- Для `/api/web/*` middleware сначала читает httpOnly cookie `pc_client_web_session`, затем стандартные схемы `Authorization: Bearer <token>` / `Authorization: Token <token>`, затем заголовок `X-Auth-Token`, затем query-параметр `token` (не рекомендуется: логируется предупреждение о небезопасном использовании).
- Токен проверяется как agent token, затем как UI token. При первой успешной проверке создаётся `AuthContext` и кладётся в `request['auth_context']`.
- Если токен не передан или невалиден — ответ **401** с телом:
  - `{"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"}`.
- Без «снижения» требований: без валидного токена доступ к защищённым endpoint’ам запрещён.

### 4.2 Whitelist (без токена)

Не требуют аутентификации:

- `POST /api/login` — получение токена агента по `device_id` (uuid).
- `POST /api/ui_login` — логин UI (логин/пароль → выдача UI токена).
- `POST /api/web/session/login` — логин нового `webapp` и установка httpOnly cookie-session.
- `GET /api/ui_session` — проверка текущей UI-сессии по Bearer UI token; возвращает `user_login`, `actor_role`, `auth_type`.
- `GET /api/health` — (зарезервировано для проверки здоровья сервиса; endpoint может быть добавлен отдельно).

Все остальные `/api/*` требуют валидный токен (agent или UI).

### 4.2.1 Control-plane runtime API (`:8667`)

- Отдельный `aiohttp`-сервис `server/control_plane.py` слушает порт `8667` и предназначен только для server runtime control.
- Control-plane принимает те же схемы токена, что и основной HTTP middleware: `Authorization: Bearer`, `Authorization: Token`, `X-Auth-Token`.
- Верификация токена выполняется через `AuthService.verify_ui_token()` и `AuthService.verify_agent_token()`, после чего request получает control-plane auth context.
- CORS разрешён только для origin'ов из `runtime_control.controller_allowed_origins()`; штатный origin для техпанели — `http://192.168.100.17:8666`.
- Маршруты:
  - `GET /api/control/server/status` — доступ `admin`, `support`, `auditor`;
  - `GET /api/control/server/logs` — доступ `admin`, `support`, `auditor`;
  - `GET /api/control/server/logs/download` — доступ `admin`, `support`, `auditor`;
  - `POST /api/control/server/actions` (`start`, `stop`, `restart`, `smoke`) — только `admin`.
- Для `stop/restart` UI обязан передавать reason; control-plane пишет это в аудит `ui_user_audit` как `server_runtime_*`.
- Runtime actions идут через внешний слой `server/runtime_control.py`, а не через self-restart основного aiohttp server, поэтому техпанель может пережить `stop/restart`.

### 4.3 Роли и декоратор require_auth

- Роль и идентификатор актора берутся только из `request['auth_context']`.
- Декоратор `require_auth(*allowed_roles)` проверяет наличие `auth_context` и вхождение `actor_role` в `allowed_roles`. При отсутствии контекста — 401, при недопустимой роли — 403 (`error_code: "FORBIDDEN"`).
- Для `DELETE /api/devices/{device_id}` допускается только `admin`: support/user/agent не могут архивировать устройства в реестре.

### 4.4 Тикетная система (Этапы 3–8) — RBAC

- **Источник роли:** только `request['auth_context']` (actor_id, actor_role). Поля `from_role` и `closed_by_role` в body принимаются для совместимости, но **не используются для авторизации**; при наличии возвращаются `deprecation_warnings`.
- **support, admin:** разрешены reroute, classify, queue, любые переходы статусов по FSM, **закрытие тикета** (POST /close), **internal-комментарии**, **создание и просмотр worklogs**; **Stage 5:** links, parent, watchers (любой actor), kb_links, metrics, чтение resolution_codes (см. [TICKET_SYSTEM.md](TICKET_SYSTEM.md)). **Stage 6:** API уведомлений — пользователь видит только свои записи (по actor_id). **Stage 7:** problems, change_links — полный доступ (создание, статусы, привязка тикетов). **Stage 8:** GET/POST `/api/notifications/preferences` — только свои prefs (actor_id). **Stage 9:** admin — полный доступ к Admin Config API (`/api/admin/tickets/queues`, routing_rules, sla_policies, audit); support — read-only.
- **auditor (Stage 9):** read-only доступ к ticket-domain GET endpoint'ам (кросс-очередной) и Admin Config GET при `TICKET_AUDITOR_ROLE_ENABLED=true`. Нет доступа к write-операциям (POST, PATCH, PUT, DELETE).
- **Requester (роль user или иная не admin/support):** видит только свои тикеты (requester_id = actor_id) в list/get/sla; разрешены **только public comments**; **не может закрывать** тикет (только reopen через POST /status); единственный разрешённый переход статуса — Resolved → New (reopen). **Visibility:** requester в GET ticket/snapshot/messages видит только сообщения с visibility=public; internal скрыты. **Worklog:** requester видит только `worklog_total_minutes` (без списка записей и без note). **Stage 5:** requester может только **self-subscribe/self-unsubscribe** watchers **в своих тикетах** (ownership-check); links, parent, kb_links, metrics — недоступны. **Stage 6:** GET/POST `/api/notifications*` — только свои уведомления. **Stage 7:** GET `/api/tickets/{id}/problems` и GET `/api/tickets/{id}/change_links` только для своих тикетов (requester_id = actor_id). **Stage 8:** GET/POST `/api/notifications/preferences` — только свои prefs.
- **Единая точка смены статуса:** POST `/api/tickets/{ticket_id}/status`; закрытие — через workflow (POST /close вызывает тот же workflow). POST /close доступен только support/admin. Stage 5: при переходе в Resolved/Closed применяется политика резолюции (resolution_code, root_cause для P1/P2) в режиме warn или enforce.
- Получатели эскалаций SLA: участники очереди (`ticket_queue_members`) + admins; доставка через `ticket_event_committed`. **Stage 6:** уведомления по событиям тикетов (sla_breached, status_changed и др.) записываются в `ticket_notifications` и доступны через API. **Stage 8:** доставка фильтруется по notification preferences (mute_internal, muted_event_types, suppress_self). Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md).

### 4.5 Публичное API очереди (Stage 10.2, 10.3) — без авторизации

- Маршруты **`/public_api/*`** не начинаются с `/api/`, поэтому **auth middleware к ним не применяется** — доступ без токена.
- Endpoints: `GET /public_api/queues`, `GET /public_api/queue/tickets`, `GET /public_api/queue/stats`.
- **GET /public_api/queues:** по умолчанию возвращаются только очереди с `open_count > 0`; параметр `include_empty=true` — все активные очереди. Сортировка: open_count desc, queue_code asc.
- **Только read-only**. Поля публичной очереди: `ticket_code`, `status`, `priority`, `position`, `wait_seconds`, `queue_code`, `updated_at`, `requester_display_name`, `urgency`, `importance`.
- Лимит выборки: max 200. Рекомендуется rate-limit по IP на уровне reverse-proxy.

### 4.6 Тикеты: смена приоритета (Stage 10.3)

- **POST /api/tickets/{ticket_id}/priority** — смена приоритета (P1..P5) с пересчётом SLA. RBAC: только **admin/support**. Событие `priority_changed`, опциональный WS push.

---

## 5. Получение токенов по HTTP

### 5.1 Agent token: POST /api/login

- **Тело:** `{"uuid": "<device_id>"}` (device_id в формате UUID).
- Логин/пароль **не** используются. Валидация UUID обязательна.
- При успехе сервер при необходимости создаёт placeholder-запись в `devices`, затем пишет запись в `agent_tokens` (hash + prefix), а клиенту возвращает сырой токен и `device_id`. Срок действия по умолчанию — 180 дней. Для архивированного устройства выдача нового agent token запрещена до явного восстановления или выбора нового `device_id`.
- В production identity-модели этот `device_id` должен быть каноническим `machine_id`, а не случайным install-local UUID.
- Если такой токен потом вводит уже существующий агент, controlled reprovision на handshake должен перевести токен на уже известное устройство вместо создания нового дубля.
- При превышении лимита активных токенов (2 на device_id) — **429** и сообщение «Token limit exceeded. Please revoke old tokens first.»

### 5.1.1 Agent provisioning: `POST /api/connection_request`

- Используется no-token bootstrap-потоком агента, когда локального токена ещё нет или он был очищен после `401 / Invalid token`.
- Identity v1: `POST /api/connection_request` должен приходить с каноническим `device_id == machine_id`; в `request_metadata` агент дополнительно передаёт `machine_id`, `install_id` и `machine_id_source` для аудита и UI.
- Политика берётся из `server_config.connection_policy` (`reject_all`, `accept_all`, `manual`). Если политика явно не задана, P0-режимом по умолчанию считается `accept_all`.
- При `accept_all` сервер:
  - выпускает новый agent token;
  - возвращает его прямо в ответе `{"status":"approved","token":...}`;
  - обязательно закрывает все существующие `pending` записи в `connection_requests` для этого `device_id`, чтобы не копились ложные stale-request алерты в техпанели.
- При `manual` создаётся или обновляется `pending` запись в `connection_requests`, а токен выдаётся только после ручного approve оператором.
- При `reject_all` токен не выдаётся, а агент получает `403 CONNECTION_REJECTED`.
- Если pending-запрос отклонён по причине архивированного устройства, status API должен возвращать `error_code=DEVICE_ARCHIVED`, чтобы агент не сохранял вечный локальный reject-флаг и мог повторить provisioning после административного восстановления устройства.

### 5.2 UI token: POST /api/ui_login

- **Тело:** `{"login": "...", "password": "..."}`.
- Опционально поддерживается `expected_role` (`admin`, `support`, `auditor`, `user`). Если фактическая роль аккаунта не совпадает, сервер возвращает **403** и не выдаёт UI token. Это используется общей страницей `/login` для разведения admin shell и support shell.
- **Stage 10:** при `AUTH_UI_DB_USERS_ENABLED=true` аутентификация сначала по БД (таблица **ui_users**): проверка пароля через PBKDF2-SHA256, учёт failed_attempts и locked_until. Роль при успехе берётся из **ui_users.actor_role**. Если пользователя нет в БД и `AUTH_UI_CONFIG_FALLBACK_ENABLED=true`, используется fallback на **state.users** (USERS) и роль из **UI_USER_ROLES_JSON** (Stage 9).
- Без DB-режима: проверка по `state.users` (конфиг логин/пароль), роль из **UI_USER_ROLES_JSON** или **admin**.
- При неверных данных или блокировке — 401 «Invalid login or password». При успехе создаётся запись в `ui_tokens`, клиенту возвращается сырой токен, `user_login` и `actor_role`. Валидные роли: `admin`, `support`, `auditor`, `user`.

### 5.3 UI session: GET /api/ui_session

- Требует Bearer UI token и проходит через обычный auth middleware.
- Возвращает текущий `AuthContext` для UI: `status`, `user_login`, `actor_role`, `auth_type`.
- Используется shell-страницами `/admin`, `/support` и `/login` для проверки, что пользователь действительно вошёл под нужной ролью до показа рабочего интерфейса.

### 5.4 Web session: `/api/web/session/*`

- `POST /api/web/session/login` принимает `{"login": "...", "password": "..."}` и при успехе выставляет httpOnly cookie `pc_client_web_session` с `SameSite=Lax`.
- `GET /api/web/session/me` требует валидную cookie-session и возвращает typed payload `{"status":"success","data":{"user_login", "actor_role", "auth_type"}}`.
- `POST /api/web/session/logout` отзывает текущий UI token server-side и очищает cookie.
- Новый React `webapp` под `/app/*` не хранит bearer token в `localStorage`; сервер остаётся источником истины для web session через cookie и `AuthContext`.

---

## 6. Конфигурация безопасности

- **USERS** (config): словарь логин → пароль для UI. По умолчанию примеры (`admin`/`user`); в production обязательно сменить и хранить пароли безопасно (например, хеши).
- **UI_USER_ROLES_JSON** (config, Stage 9): JSON-маппинг логин → роль для UI (`{"login": "role"}`). Используется при fallback-логине (config) или когда пользователь не в БД. **Stage 10:** при аутентификации из ui_users роль берётся из БД, не из этого маппинга.
- **Stage 10 — UI users из БД:** `AUTH_UI_DB_USERS_ENABLED`, `AUTH_UI_CONFIG_FALLBACK_ENABLED`, `AUTH_UI_MAX_FAILED_ATTEMPTS`, `AUTH_UI_LOCK_MINUTES`. Пароли в ui_users хранятся в виде хеша (pbkdf2_sha256). Admin API: GET/POST/PATCH /api/admin/users, смена пароля, деактивация; self-service: POST /api/users/me/password. См. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-10-usersroles-из-бд).
- **ALLOW_REMOTE_CODE** (env): разрешение выполнения удалённого кода (инструменты с уровнем риска code_exec). По умолчанию `false`; включать только при осознанном риске.

---

## 7. Интерфейс тикета (Stage 10.4, 10.5)

- Страница тикета (/ticket/{id}) использует тот же UI-токен (admin_auth_token), что и админка; WebSocket /ws_ui — ui_hello с этим токеном, затем subscribe_ticket.
- Отдельная страница `/login` остаётся единым входом для legacy shell-страниц: admin логин ведёт в `/admin`, support логин — в `/support`. Сами shell-страницы проверяют `GET /api/ui_session` и при несоответствии роли перенаправляют обратно на `/login`.
- Новый React `webapp` живёт на `/app/support` и `/app/admin`, использует `/app/login` и проверяет сессию через `/api/web/session/me`.
- Support workspace в work-режиме не дублирует composer/timeline вручную, а встраивает `ticket.html?embed=1`. Это сохраняет RBAC, вложения, reply-to, скриншоты и прочие возможности ticket chat без расхождения поведения между страницами.
- **Видимость сообщений:** в composer переключатель «Внутренняя заметка» (internal); по умолчанию сообщения — public. Только роли support/admin могут отправлять internal; requester не видит внутренние сообщения (фильтрация в snapshot и в API).
- **Stage 10.5 — Action Dock:** управление тикетом через панель кнопок (Статус, Назначить, Очередь, Приоритет, Инструменты ПК, Трудозатраты, Закрыть, Перемаршрутизация) и inline-панели; slash-команды из UI убраны. **RBAC в UI:** snapshot возвращает `actor_role`; для роли **auditor** кнопки Action Dock отображаются в состоянии disabled (read-only); admin/support — полный доступ к действиям. Серверная проверка прав остаётся источником истины. См. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-105-action-dock--inline-panels). Подход со slash-командами (Stage 10.4) deprecated, см. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-104-chat-first-deprecated).

---

## 8. Важные замечания

1. **Никогда не доверять payload для роли/идентификатора:** `device_id`, `actor_role`, `user_login` для авторизации берутся только из проверенного токена (БД) и `AuthContext`.
2. **Токен в логах:** в логах фигурирует только префикс токена (первые 8 символов), не полный токен.
3. **HTTPS:** в production рекомендуется обслуживать API и WebSocket через HTTPS (настройка на уровне reverse proxy или сервера).
4. **Пароли UI:** текущая реализация хранит пароли в открытом виде в `USERS`; для production целесообразен переход на хеширование (например, bcrypt) и вынесение учётных данных в безопасное хранилище.

---

## 9. Связанные документы

- [README.md](README.md) — обзор сервера и API.
- [PROTOCOL_V3.md](PROTOCOL_V3.md) — протокол V3 на стороне сервера.
- Документация агента: `pc_agent/docs/PROTOCOL_V3.md` — полное описание протокола V3.
