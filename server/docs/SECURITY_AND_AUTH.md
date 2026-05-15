# Безопасность и аутентификация

Документация по безопасности, аутентификации и авторизации сервера PC Agent.

**Дата обновления:** 2026-04-20

---

## Обзор

- **Агенты:** аутентификация по токену (agent token) при WebSocket handshake и при HTTP API.
- **UI:** legacy shell-страницы используют логин/пароль с выдачей UI токена; новый `webapp` под `/app/*` использует тот же UI token storage на сервере, но выдаёт его клиенту только как httpOnly cookie-session.
- **HTTP API:** все `/api/*` маршруты (кроме whitelist) защищены middleware по токену (Bearer/Token/X-Auth-Token), а cookie `pc_client_web_session` используется не только на `/api/web/*`, но и на canonical React bridges для нового webapp: `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer` и `/api/ticket_forms/*`.
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

1. Клиент должен первым делом отправить сообщение с `type: "ui_hello"`.
2. Legacy shell и внешние UI-клиенты могут передавать в `ui_hello` поле `token` (сырой UI токен).
3. Новый `webapp` под `/app/*` использует httpOnly cookie-session: websocket `/ws_ui` читает UI token из cookie `pc_client_web_session`, поэтому JS-код не должен вытаскивать сырой токен в browser runtime.
4. Без валидного token/session cookie сервер отправляет `type: "error"` и закрывает соединение с кодом 4003.
5. **Критично:** `actor_role` и `user_login` берутся **только из записи токена в БД**, не из payload. Если в payload указана другая роль — используется роль из токена, в лог пишется предупреждение.
6. После успешной проверки создаётся `AuthContext` и сохраняется в данных соединения; клиенту отправляется `ui_hello_ack` с `connection_id` и `role` (из токена).
7. Все последующие сообщения (subscribe_ticket, subscribe_device, ping и т.д.) обрабатываются только если уже выполнён успешный `ui_hello`; иначе возвращается ошибка «Authentication required. Send ui_hello first.»
8. Новый realtime bridge для `webapp` сначала получает typed bootstrap через `GET /api/web/realtime/bootstrap`, а затем подключается к `/ws_ui` уже с cookie-session; bridge-рекламируемые `support.queue`, `ticket.stream`, `admin.devices` и `tech.feed` подписки остаются transport-detail слоем и не должны протекать в feature-код React.

---

## 4. HTTP API: middleware и whitelist

### 4.1 Middleware

- New React code should prefer typed cookie-session routes under `/api/web/*`. The current React-only bridges include `/api/web/admin/observer/*`, `/api/web/admin/modules/*`, `/api/web/admin/access/*`, `/api/web/notifications*` and `/api/web/admin/tech/alerts`.
- Legacy `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer`, `/api/notifications*` and `/api/ticket_forms/*` remain authenticated compatibility endpoints; do not add new React callers to them unless the endpoint is intentionally public/requester-facing.

- Применяется ко всем запросам с путём, начинающимся с `/api/`.
- Для `/api/web/*` middleware сначала читает httpOnly cookie `pc_client_web_session`, затем стандартные схемы `Authorization: Bearer <token>` / `Authorization: Token <token>`, затем заголовок `X-Auth-Token`, затем query-параметр `token` (не рекомендуется: логируется предупреждение о небезопасном использовании).
- Тот же httpOnly cookie bridge разрешён и для canonical React-admin endpoints вне `/api/web/*`: `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer` и `/api/ticket_forms/*`. Это нужно, чтобы новый `/app/admin/*` работал с реальными backend surfaces без дублирующих proxy-handler'ов, но при этом всё равно оставался под server-authoritative UI session.
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
- Legacy endpoint `POST /api/tools/run` также берёт роль только из `AuthContext`; если запрос пришёл по agent token, `device_id` в body обязан совпадать с `AuthContext.actor_id`, иначе сервер возвращает 403 `DEVICE_CONTEXT_MISMATCH` до metadata/policy/dispatch. Это не даёт agent token запускать diagnostics/tool commands в чужом device context даже при подмене `actor_role` в JSON.

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
- **GET /public_api/queues:** по умолчанию возвращаются только очереди с `open_count > 0`; параметр `include_empty=true` — все активные очереди. Сортировка: open_count desc, queue_code asc. Response exposes `queue_code` and counts only; internal queue names are not public.
- **Только read-only**. Public queue uses a dedicated unauthenticated serializer and exposes only the sanitized public projection: `ticket_code`, `public_position`, `public_status`, `public_status_label`, `queue_code`, `wait_bucket`, `updated_at`, `total`, `limit`, `offset`. It accepts only `queue_code` / `public_queue_code`; numeric `queue_id` is rejected before DB access. It must not expose internal `ticket_id`, `requester_id`, `requester_display_name`, full name, contacts/location, urgency/importance/reasons, internal priority, assignee/queue ids, internal queue names, device/asset refs, raw `custom_fields`, trace ids or operation ids.
- Policy Health endpoints are read-only for `admin` and `auditor`: `GET /api/web/admin/helpdesk/policy-health`, `GET /api/web/admin/helpdesk/policy-health/{template_code}` and `POST /api/web/admin/helpdesk/policy-health/simulate`. `support`, requester and unauthenticated users are denied; simulation is dry-run, creates no tickets, does not leak requester PII, and uses the same runtime resolvers as ticket create/lifecycle for routing, priority, SLA, OLA, approval, closure, visibility and diagnostic policy previews.
- Service Catalog admin mutation endpoints under `/api/web/admin/service-catalog*` require `admin`; auditor may read, validate and simulate, but cannot mutate. The requester/agent projection under `GET /api/service-catalog/*` and requester-safe `POST /api/service-catalog/preview` is intentionally unauthenticated for the public help flow, safe-projected, and does not include queue ids, raw policy JSON, approver internals, requester ids, device ids, raw custom fields, trace ids or operation ids. Preview is dry-run only and must not create tickets/events/approvals/diagnostics/notifications.
- Knowledge Platform management endpoints under `/api/web/knowledge/*` are web-session protected. Admin can manage spaces/items/versions/graph/ingestion/content-packs/review tasks/gap findings/rollout policies, including `admin_internal`; `security_restricted` remains admin-accessible until a dedicated security role is introduced. Support can read requester-safe plus `support_internal` knowledge and can mutate only those non-admin/non-security visibilities. Auditor is read-only and cannot see `admin_internal` or `security_restricted`. Direct item/version, graph node/neighborhood, ingestion, metrics, first-class review tasks, quality score, persisted gap findings and search analytics summaries apply the same actor visibility filter. Requester/agent safe endpoints `POST /api/knowledge/search`, `POST /api/knowledge/suggest` and `POST /api/knowledge/feedback` are intentionally auth-whitelisted for the public `/app/help` deflection flow, default anonymous calls to requester-safe scope, honor rollout policies for requester/agent surfaces, and apply visibility filtering before results. They must not return internal bodies, support/admin/security-restricted items, source ticket/passport ids, requester/device ids, raw custom fields, internal graph edges, queue/policy ids, trace ids, operation ids or restricted chunks. Requester-safe publication and content-pack publication are blocked by lint checks for internal commands/runbooks, queue/device/requester ids, raw custom fields, secrets and security internals. Knowledge search analytics stores query hashes and redacted query text, not raw requester/device identifiers. Passport-to-knowledge creates drafts only; stale passport drafts require explicit stale acknowledgement and review note before publication.
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
- При `manual` создаётся или обновляется `pending` запись в `connection_requests`, а токен выдаётся только после ручного approve оператором. Heartbeat `POST /api/connection_request`, пришедший после approve, но до `GET /api/connection_request/status`, считается уже ожидающим доставки токена и не создаёт второй `pending`-запрос.
- При `reject_all` токен не выдаётся, а агент получает `403 CONNECTION_REJECTED`.
- Если pending-запрос отклонён по причине архивированного устройства, status API должен возвращать `error_code=DEVICE_ARCHIVED`, чтобы агент не сохранял вечный локальный reject-флаг и мог повторить provisioning после административного восстановления устройства.
- Provisioning writes observer-visible `agent_runtime_audit` events for create/approve/reject/token delivery/token limit/fingerprint mismatch/post-approval delivery wait. Operation-less records are projected as `root_kind=device_provisioning` traces; support/Codex can search them with `/api/admin/tech/observer/search?q=connection_request` or collect `/api/admin/tech/diagnostics/bundle?q=connection_request`.

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
- `GET /api/web/session/me` требует валидную cookie-session и возвращает typed payload `{"status":"success","data":{"user_login", "actor_role", "auth_type", "default_workspace", "available_workspaces", "permissions", "permissions_version"}}`.
- `default_workspace`, `available_workspaces`, `permissions` и `permissions_version` формируются сервером по effective access и считаются каноничным источником истины для redirect/access-gate и element-visibility логики нового `/app/*`; React-клиент не должен заново вычислять эти права из произвольных role-switch веток.
- `POST /api/web/session/logout` отзывает текущий UI token server-side и очищает cookie.
- Новый React `webapp` под `/app/*` не хранит bearer token в `localStorage`; сервер остаётся источником истины для web session через cookie и `AuthContext`.
- `GET /api/web/realtime/bootstrap` возвращает typed transport contract для нового `webapp` (`transport`, `auth_mode`, `socket_url`, `hello_message_type`, channel contracts). Реальное websocket-подключение идёт в `/ws_ui` и использует ту же cookie-session без раскрытия raw token в JS.

### 5.5 Web access-control catalog: `/api/web/admin/access/*`

- Доступ к access-control endpoints требует роли `admin`; UI-видимость не является security boundary.
- `server/access_control/catalog.py` содержит серверный каталог permission codes, русские operator labels, risk labels, role defaults и `permissions_version`.
- Access-control API:
  - `GET /api/web/admin/access/catalog` — роли и grouped permission catalog;
  - `GET /api/web/admin/access/summary` — пользователи из `ui_users`, очереди, access groups и membership counts;
  - `GET /api/web/admin/access/effective?actor_id=...&actor_role=...` — effective permissions, workspaces, direct/group queue memberships и источники прав;
  - `POST/PATCH /api/web/admin/access/groups*` — controlled CRUD группы доступа;
  - `PUT /api/web/admin/access/groups/{group_id}/permissions|members|queues` — explicit apply для permission grants, group members и queue grants;
  - `GET /api/web/admin/access/audit` — последние RBAC mutations.
- Текущая модель effective access: built-in role defaults + active access-group permission grants + direct queue memberships + group queue grants. Backend-deny правила и существующие queue checks остаются обязательными.
- Группы хранятся в таблицах `access_groups`, `access_group_members`, `access_group_permissions`, `access_group_queue_members`, аудит — в `access_audit`.
- React `/app/admin/access` использует controlled tables, checkboxes and explicit save buttons; raw JSON authoring для RBAC не допускается.

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
- `/app` теперь считается role-aware точкой входа: после логина или прямого захода индекс выбирает `default_workspace` из session payload и уводит пользователя в допустимую рабочую область.
- Если пользователь без доступа к `/app/admin` идёт туда напрямую, access gate обязан вернуть его в допустимую workspace-зону, а не оставлять на частично загруженном экране.
- Cutover legacy shell управляется флагами `WEBAPP_CUTOVER_LOGIN_ENABLED`, `WEBAPP_CUTOVER_SUPPORT_ENABLED`, `WEBAPP_CUTOVER_ADMIN_ENABLED` в `server/config.py`; после финального переключения эти флаги включены по умолчанию, а старые `/login`, `/support`, `/admin` редиректят в `/app/*`. Requester cutover is separate: `WEBAPP_CUTOVER_HELP_ENABLED` and `WEBAPP_CUTOVER_TICKET_ENABLED` default to false and only redirect `/help` and `/ticket/{id}` to `/app/help` and `/app/ticket/{id}` when explicitly enabled. Явный escape на legacy shell сохраняется через `?legacy=1`, а rollback возможен через `WEBAPP_CUTOVER_*=false` в `server/.env`.
- Operational prerequisite для cutover: redirect в новый shell активируется только если built bundle реально присутствует в `webapp/dist`; для `/support` и `/admin` дополнительно обязателен включённый login cutover, иначе route остаётся на legacy shell.
- Каноничный preflight перед полным переключением: `python scripts/check_webapp_cutover.py --json`; каноничный live signoff после release: `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`, который подтверждает и raw redirects `/login|/admin|/support`, и `?legacy=1` escape.
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
