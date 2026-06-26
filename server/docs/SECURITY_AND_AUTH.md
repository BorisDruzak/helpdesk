# Безопасность и аутентификация

Документация по безопасности, аутентификации и авторизации сервера PC Agent.

**Дата обновления:** 2026-06-26

Security update 2026-05-23:
- `POST /api/login` is removed from the unauthenticated whitelist and is admin-only. It is retained only as an audited compatibility path for manual agent-token issue.
- Manual `connection_request` polling requires `device_id`, `request_id`, and `poll_secret`; the database stores only `poll_secret_hash`, and approved agent tokens are generated only after a valid poll and delivered once.
- Default query-token auth, config-user fallback, insecure cookies, and legacy `/api/ui_login` bearer-token login are disabled unless explicitly enabled for local development.
- Auth-sensitive rate limits ignore `X-Forwarded-For` by default. Set `TRUST_X_FORWARDED_FOR=true` plus `TRUSTED_PROXY_CIDRS` only when requests arrive through trusted reverse proxies.
- UI roles fail closed: unknown `actor_role` values do not become `admin`; new users without a role default to `user`.
- Account-session validation uses POST/header/body by default. Query-string session tokens are disabled unless explicitly enabled for legacy compatibility.

Security update 2026-05-25:
- `APP_ENV=dev|test|pilot|prod` is the primary environment profile. `APP_ENV=pilot` and `APP_ENV=prod` fail closed; legacy `PILOT_STAND_MODE=true` remains a compatibility strict-mode trigger.
- Pilot/prod startup rejects insecure dev defaults, disabled DB persistence, default UI passwords, query-token auth, UI config fallback, insecure web-session cookies, and disabled HTTPS/WSS policy.
- If database initialization fails in a strict runtime profile, server startup raises the original DB error instead of continuing as an in-memory server.
- Real `server/.env` and `db_config.json` are local files only and must not be tracked by git; `scripts/verify_workspace.py` checks this hygiene rule.

Security update 2026-06-10:
- HttpOnly web-session cookie authentication now has a same-origin guard for unsafe methods on browser bridge paths (`/api/web/*`, `/api/upload`, `/api/artifacts/*`, `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer`, `/api/ticket_forms/*`, `/api/registry/options`, `/api/notifications`). When the request is authenticated by the web-session cookie, unsafe methods require an `Origin` or `Referer` whose origin matches the current host, reverse-proxy public host from `Forwarded` / `X-Forwarded-Proto` + `X-Forwarded-Host`, `SERVER_PUBLIC_BASE_URL`, or `WEB_CSRF_TRUSTED_ORIGINS`; missing or mismatched origin returns 403.
- The guard is controlled by `WEB_CSRF_SAME_ORIGIN_ENABLED=true` by default. `WEB_CSRF_TRUSTED_ORIGINS` is a comma-separated override for explicit public browser origins. Bearer UI tokens, agent tokens and public ticket token paths are not treated as cookie-auth browser requests by this guard.
- Direct browser pairing lookup by `pairing_id` is safe-projected: expired, consumed, superseded, failed, canceled and unknown pairings do not return device facts or raw pairing secrets. The endpoint also rate-limits direct pairing-id probes.

Security update 2026-06-11:
- Public ticket claim from `/api/web/requester/tickets/claim-public` requires the web user to resolve to a `RegistryPerson` through a verified `ui_login` identity; email, Windows login and AD identities are not web-account proof. Unlinked web logins receive `REQUESTER_IDENTITY_REQUIRED` and do not create web-login-only ownership.
- User consent creation is race-safe around the partial unique pending-subject index. Duplicate concurrent creation returns the existing pending `UserConsentRequest` instead of leaking a duplicate-key 500.
- Consent-required operation retry ticket events use the same sensitive-key redaction helper as `UserConsentRequest.requested_action_payload_redacted`; raw `authorization`, `cookie`, `password`, `secret`, `session_token` and token-like params must not be written into `ticket_events`.
- Requester-facing Remote Assist consent list/detail/decision responses are consent-only payloads and must not include ICE servers, SDP offers/answers/candidates, signaling tokens, agent/viewer tokens, session tokens, cookies or authorization material.

Security update 2026-06-15:
- Web self-registration is fail-closed by default through `WEB_SELF_REGISTRATION_ENABLED=false`.
- Requester profile completion is blocking by default through `PROFILE_COMPLETION_REQUIRED=true`. Temporary rollout override may set it to `false`; missing fields still return in `profile_completion`, but requester ticket preview/create uses policy-aware `blocks`.
- `POST /api/web/session/register` creates only a UI account with role `user`, validates the existing password policy and duplicate login constraints, rejects role-escalation fields through strict DTO validation, and does not set `pc_client_web_session`.
- Web login and self-registration normalize UI logins to trimmed lower-case before auth lookup, account creation and token subject creation. `ui_users` enforces unique `lower(trim(user_login))` through migration `131`, and web registration rejects logins longer than the DB column limit of 100 characters before writing.
- Optional registration device-link codes are validated only as registration pairings; account creation does not create an active device binding or bypass the later profile/admin approval policy.
- `PUT /api/web/requester/profile` is web-session protected, writes only the authenticated caller's registry profile and verified `ui_login` identity, rejects foreign `person_id`, and requires active registry department/location ids before normal requester ticket preview/create is allowed.

Security update 2026-06-26:
- Public ticket session verification for public-token `/api/tickets*`, upload/artifact and quality paths now checks the scoped ticket state in addition to session revocation and expiry. Tokens for `closed` or `canceled` tickets are rejected before `last_used_at` is updated, so a failed or delayed close-side session revoke does not keep terminal ticket access alive.

---

## Обзор

- **Агенты:** аутентификация по токену (agent token) при WebSocket handshake и при HTTP API.
- **UI:** legacy shell-страницы используют логин/пароль с выдачей UI токена; новый `webapp` под `/app/*` использует тот же UI token storage на сервере, но выдаёт его клиенту только как httpOnly cookie-session.
- **HTTP API:** все `/api/*` маршруты (кроме whitelist) защищены middleware по токену (Bearer/Token/X-Auth-Token), а cookie `pc_client_web_session` используется не только на `/api/web/*`, но и на canonical React bridges для нового webapp: `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer`, `/api/ticket_forms/*`, `/api/registry/options`, `/api/upload` и `/api/artifacts/*`.
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
- Для UI-токена `AuthService.verify_ui_token()` дополнительно сверяет `ui_users`: отсутствующий или отключенный (`is_active=false`) UI-пользователь делает токен недействительным, а оставшиеся активные UI-токены этого логина отзываются. Для requester-role аккаунтов также проверяется любая verified `ui_login` связь с `registry_people`: `archived` / `inactive` / `deactivated` / `disabled` карточка деактивирует UI-аккаунт, отзывает активные UI-токены и блокирует новый web-login.

### 1.2 Лимиты и сроки

- **Agent token:** максимум **2 активных токена** на один `device_id`. Срок по умолчанию при выдаче: **180 дней** (4320 часов). При превышении лимита — HTTP 429, сообщение «Token limit exceeded».
- **UI token:** срок по умолчанию при выдаче: **24 часа** (в `handle_ui_login`).
- **Public ticket code authorize:** `POST /public_api/tickets/{ticket_id}/authorize` applies the shared auth rate limiter before public access code verification. The key is `client_ip:ticket_id`, the limit is 5 attempts per 300 seconds, and excess attempts return HTTP 429 with `RATE_LIMITED`. This protects the 8-character public access code exchange from online brute-force/cooldown bypass while keeping the public session token scoped to the ticket.
- **Account session delivery:** admin-approved other-account login stores only an encrypted one-time envelope in `device_account_login_requests.metadata_json.session_token_delivery`; `ACCOUNT_SESSION_DELIVERY_SECRET` is required in pilot/prod. Agent polling atomically marks delivery and removes the envelope before returning the session token once.
- **Local no-DB fallback:** если DB-path недоступен, а config-fallback включён, `AuthService.authenticate()` уходит на `state.users`, а `generate_ui_token()` / `verify_ui_token()` / `revoke_ui_token()` используют in-memory fallback store. После первой DB-ошибки web auth включает короткий cooldown на повторные UI token probe, чтобы `/app/*` не подвешивал локальный dev smoke постоянными retry к недоступной PostgreSQL. Это только локальная/degraded схема для dev smoke, не production storage model.

### 1.3 Отзыв токенов

- **Agent token revoke:** `POST /api/devices/{device_id}/tokens/revoke` and web-session alias `POST /api/web/admin/devices/{device_id}/tokens/revoke` are admin-only. The handler accepts `{"token_hash": "..."}` and revokes only when the hash belongs to the same path `device_id`; audit/log output may include only a short hash prefix, never the full hash or raw token.
- **Device token list:** `GET /api/devices/{device_id}/tokens`, web-session alias `GET /api/web/admin/devices/{device_id}/tokens`, and fleet list `GET /api/web/admin/device-tokens` are admin-only. They return stored token records with `token_hash`, `token_prefix`, timestamps and `is_active`; raw tokens are never returned. The fleet list also includes `device_id`, hostname and online state so the inventory UI does not collapse multiple connected agents into the currently selected device.
- **Архивирование устройства:** `DELETE /api/devices/{device_id}` доступен только роли `admin`. Сервер best-effort закрывает live WebSocket-сессию агента, очищает runtime-кэши, отзывает активные agent token, гасит pending connection request / outbox / активные operations и помечает устройство как архивное через `devices.deleted_at/deleted_by/delete_reason`. История аудита, событий, снапшотов и тикетов сохраняется.
- **Восстановление устройства из архива:** web-session alias `POST /api/web/admin/devices/{device_id}/restore` доступен только роли `admin`. Восстановление очищает `deleted_at/deleted_by/delete_reason` и возвращает запись в активный inventory, но не восстанавливает отозванные agent token, account sessions, pending connection requests, outbox rows или отменённые operations; агент должен заново пройти обычное подключение и одобрение.

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
- Для `/api/web/*` middleware сначала читает httpOnly cookie `pc_client_web_session`, затем стандартные схемы `Authorization: Bearer <token>` / `Authorization: Token <token>`, затем заголовок `X-Auth-Token`, затем query-параметр `token` (не рекомендуется: логируется предупреждение о небезопасном использовании). Если query-token передан, middleware увеличивает bounded process-local counter для Tech Panel readiness независимо от того, разрешён канал или отклонён политикой `AUTH_ALLOW_QUERY_TOKEN`; сохраняются только timestamp/path/rejected, само значение token не хранится и не возвращается API.
- Тот же httpOnly cookie bridge разрешён и для canonical React/admin/support endpoints вне `/api/web/*`: `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer`, `/api/ticket_forms/*`, `/api/upload` и `/api/artifacts/*`. Это нужно, чтобы новый `/app/admin/*` и support attachment/download flows работали с реальными backend surfaces без дублирующих proxy-handler'ов, но при этом всё равно оставались под server-authoritative UI session.
- `GET /api/artifacts/{artifact_id}/download?ticket_id=...` не является auth bypass: даже при наличии `ticket_id` запрос должен пройти middleware и получить `AuthContext` через web-session cookie, agent token или public-ticket token before `ArtifactService` checks ticket/artifact visibility. Public-ticket tokens are accepted on `/api/artifacts/*` only for the ticket scope encoded in the token.
- Токен проверяется как agent token, затем как UI token. При первой успешной проверке создаётся `AuthContext` и кладётся в `request['auth_context']`.
- Если токен не передан или невалиден — ответ **401** с телом:
  - `{"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"}`.
- Без «снижения» требований: без валидного токена доступ к защищённым endpoint’ам запрещён.

### 4.2 Whitelist (без токена)

Не требуют аутентификации:

- `POST /api/login` — admin-only audited compatibility endpoint for manual agent-token issue; it is not in the unauthenticated whitelist.
- `POST /api/ui_login` — логин UI (логин/пароль → выдача UI токена).
- `POST /api/web/session/login` — логин нового `webapp` и установка httpOnly cookie-session.
- `POST /api/web/session/register` — feature-flagged account-only self-registration; when disabled it returns 403 and creates nothing, when enabled it creates role `user` without issuing a session cookie.
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
- Browser-pairing web endpoints `POST /api/web/registry/browser-pairings/lookup`, `GET /api/web/registry/browser-pairings/{pairing_id}` and `/login|registration/confirm` accept web-session roles `admin`, `support` and `user`; login confirmation still relies on `BrowserPairingService` to resolve the actor identity and require an active primary/shared/responsible binding for the pairing device. Registration confirmation for a requester-owned device link is separate from requester profile completion; it creates a claim from the resolved `RegistryPerson` when available or from the authenticated web account otherwise, while normal ticket actions remain gated by `REQUESTER_PROFILE_INCOMPLETE`.
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
- Knowledge Platform management endpoints under `/api/web/knowledge/*` are web-session protected. Admin can manage spaces/items/versions/graph/ingestion/content-packs/review tasks/gap findings/rollout policies, including `admin_internal`; `security_restricted` remains admin-accessible until a dedicated security role is introduced. Support can read requester-safe plus `support_internal` knowledge and can mutate only those non-admin/non-security visibilities. Governed metadata writes are stricter: taxonomy/property/item-metadata/applicability/quality-model mutation routes require `knowledge.metadata.manage`, which admin receives by default and support receives only through explicit knowledge-manager access-group delegation. Auditor is read-only and cannot see `admin_internal` or `security_restricted`. Direct item/version, graph node/neighborhood, ingestion, metrics, first-class review tasks, quality score, persisted gap findings and search analytics summaries apply the same actor visibility filter. Requester/agent safe endpoints `POST /api/knowledge/search`, `POST /api/knowledge/suggest` and `POST /api/knowledge/feedback` are intentionally auth-whitelisted for the public `/app/help` deflection flow, default anonymous calls to requester-safe scope, preserve a valid bearer or web-session `AuthContext` for Registry audience resolution without making auth mandatory, enforce same-origin checks for valid cookie-authenticated writes, honor rollout policies for requester/agent surfaces, and apply visibility filtering before results. Rollout policy aliases `GET /api/web/knowledge/rollout`, `POST /api/web/knowledge/rollout/save` and `POST /api/web/knowledge/rollout/effective-preview` use the same web-session boundary as `/api/web/knowledge/rollout-policies`: admin can mutate, auditor/support can read only through allowed management projections, and requester/agent cannot manage policy. Rollout never grants visibility or bypasses ACL; it can only suppress or gate requester/agent suggestion display after ACL filtering. They must not return internal bodies, support/admin/security-restricted items, source ticket/passport ids, requester/device ids, raw custom fields, internal graph edges, queue/policy ids, trace ids, operation ids or restricted chunks. Requester-safe publication and content-pack publication are blocked by lint checks for internal commands/runbooks, queue/device/requester ids, raw custom fields, secrets and security internals. Knowledge search analytics stores query hashes and redacted query text, not raw requester/device identifiers. Passport-to-knowledge creates drafts only; stale passport drafts require explicit stale acknowledgement and review note before publication.
- Knowledge AI settings endpoints under `/api/web/knowledge/ai/*` are admin-only. Provider rows may store secret references such as `env:OPENROUTER_API_KEY`, but API responses expose only configured/masked state and must never return raw secret refs, API keys, prompts, generated outputs or restricted content. Model-profile updates and audit listing stay behind the same admin boundary. Health checks write redacted `ai_request_audit` and Observer-visible runtime audit rows with stable event codes such as `knowledge.ai.provider_health_ok` / `knowledge.ai.provider_health_failed`; audit list responses apply an additional redaction pass before returning stored errors.
- Knowledge article segmentation endpoints under `/api/web/knowledge/items/{item_id_or_slug}/segments*` and `/api/web/knowledge/segments/{segment_id}` are web-session protected. Admin/support can create, update, auto-segment and archive only segment visibilities allowed by `can_mutate_knowledge_visibility`; requester/user cannot mutate segments. Segmentation profiles are readable by admin/support/auditor and mutable only by admin. Segment search contribution still runs through the owning item visibility filter and segment visibility filter before returning results.
- Quality Loop endpoints under `/api/web/quality/*` are web-session protected. Support/admin/auditor may read aggregate quality data and review/action queues according to role, while mutating review/action/policy endpoints require support/admin and policy save requires admin. Requester/public feedback and reopen require either normal requester auth for the ticket or a valid public ticket token scoped to that ticket. Requester/public responses never expose QA reviews, internal findings, queue IDs, actor IDs, support-only notes, improvement actions, raw policies or aggregate rows with requester PII.
- Problem Management endpoints under `/api/web/problems*`, `/api/web/problem-candidates*` and `/api/web/problem-scanner*` are web-session protected. Support/admin can create, link, transition, scan/convert/merge candidates, run or dry-run the scanner, create RCA drafts and create known-error/workaround drafts; auditor is read-only; requester/public users have no direct problem/RCA/scanner API in P4/P4.1. Scanner status and run history are operational metadata only. Problem analytics, scanner runs and candidate list responses are aggregate/redacted and must not include requester IDs, requester comments, public tokens, internal RCA evidence, queue internals or raw policy JSON. Requester-safe known error/workaround publication is controlled only through Knowledge Platform visibility/review/lint.
- Change Enablement endpoints under `/api/web/changes*`, `/api/web/change-windows` and `/api/web/change-policies` are web-session protected. Support/admin can create and update changes, risk assessments, plans, windows, tasks and PIR records according to policy; auditor is read-only; requester/public users have no direct change API in P5. Approval decision endpoints require the current actor to match the configured approver actor/role/group unless admin override is used. Standard preapproval is allowed only through explicit change policy; emergency blackout override requires justification and emergency retrospective remains tracked. Change analytics are aggregate-only and must not include requester IDs, requester comments, raw implementation notes, rollback steps, affected asset internals or raw policy JSON.
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
- Если такой токен потом вводит уже существующий агент, controlled reprovision на handshake может перевести токен на уже известное устройство вместо создания нового дубля только после проверки stored device fingerprint этого target device и только если строка токена всё ещё привязана к исходному provisioning/legacy `device_id`. При fingerprint mismatch handshake отклоняется, а `agent_tokens.device_id` остаётся на исходном provisioning/legacy устройстве.
- При превышении лимита активных токенов (2 на device_id) — **429** и сообщение «Token limit exceeded. Please revoke old tokens first.»

### 5.1.1 Agent provisioning: `POST /api/connection_request`

- Используется no-token bootstrap-потоком агента, когда локального токена ещё нет или он был очищен после `401 / Invalid token`.
- Identity v1: `POST /api/connection_request` должен приходить с каноническим `device_id == machine_id`; в `request_metadata` агент дополнительно передаёт `machine_id`, `install_id` и `machine_id_source` для аудита и UI.
- Политика берётся из `server_config.connection_policy` (`reject_all`, `accept_all`, `manual`). Если политика явно не задана, безопасный default — `manual`; fallback к `accept_all` допустим только для явного insecure dev режима (`ALLOW_INSECURE_DEV_DEFAULTS=true`) или при явной записи `connection_policy=accept_all`.
- При `accept_all` сервер:
  - выпускает новый agent token;
  - возвращает его прямо в ответе `{"status":"approved","token":...}`;
  - обязательно закрывает все существующие `pending` записи в `connection_requests` для этого `device_id`, чтобы не копились ложные stale-request алерты в техпанели.
- При `manual` создаётся или обновляется `pending` запись в `connection_requests`, а admin approve только переводит защищённый запрос в `approved`. Raw agent token не хранится в памяти процесса или БД: сервер генерирует его только при валидном `GET /api/connection_request/status` с `device_id + request_id + poll_secret`, сохраняет в БД только hash в `agent_tokens` и помечает approval delivered. Pending-запросы без `request_id` или `poll_secret_hash` не approve-ятся и получают `409 POLL_SECRET_MISSING`; агент должен создать свежую заявку. Heartbeat `POST /api/connection_request`, пришедший после approve, но до `GET /api/connection_request/status`, считается уже ожидающим доставки токена и не создаёт второй `pending`-запрос.
- Если manual no-token `POST /api/connection_request` приходит для `device_id`, у которого уже есть активный неистёкший agent token, сервер считает устройство уже авторизованным, закрывает pending-строки для этого device, возвращает `{"status":"approved","already_authorized":true}` без raw token и poll-credentials и пишет `connection_request_already_authorized`. Для намеренного reprovision сначала нужно отозвать существующий токен.
- Fresh manual `POST /api/connection_request` без matching `request_id + poll_secret` получает новый `pending` с новым `request_id` и `poll_secret`, даже если старая approval ещё не доставила токен. Ветка post-approval delivery wait действует только для исходного poller.
- При `reject_all` токен не выдаётся, а агент получает `403 CONNECTION_REJECTED`.
- Если pending-запрос отклонён по причине архивированного устройства, status API должен возвращать `error_code=DEVICE_ARCHIVED`, чтобы агент не сохранял вечный локальный reject-флаг и мог повторить provisioning после административного восстановления устройства.
- Provisioning writes observer-visible `agent_runtime_audit` events for create/approve/reject/token delivery/token limit/fingerprint mismatch/post-approval delivery wait. Operation-less records are projected as `root_kind=device_provisioning` traces; support/Codex can search them with `/api/admin/tech/observer/search?q=connection_request` or collect `/api/admin/tech/diagnostics/bundle?q=connection_request`.

### 5.2 UI token: POST /api/ui_login

- **Тело:** `{"login": "...", "password": "..."}`.
- Опционально поддерживается `expected_role` (`admin`, `support`, `auditor`, `user`). Если фактическая роль аккаунта не совпадает, сервер возвращает **403** и не выдаёт UI token. Это используется общей страницей `/login` для разведения admin shell и support shell.
- **Stage 10:** при `AUTH_UI_DB_USERS_ENABLED=true` аутентификация сначала по БД (таблица **ui_users**): проверка пароля через PBKDF2-SHA256, атомарный DB increment для `failed_attempts` и установка `locked_until`. Роль при успехе берётся из **ui_users.actor_role**. Если пользователя нет в БД и `AUTH_UI_CONFIG_FALLBACK_ENABLED=true`, используется fallback на **state.users** (USERS) и роль из **UI_USER_ROLES_JSON** (Stage 9).
- Без DB-режима: проверка по `state.users` (конфиг логин/пароль), роль из **UI_USER_ROLES_JSON** или **admin**.
- При неверных данных или блокировке — 401 «Invalid login or password». При успехе создаётся запись в `ui_tokens`, клиенту возвращается сырой токен, `user_login` и `actor_role`. Валидные роли: `admin`, `support`, `auditor`, `user`.

### 5.3 UI session: GET /api/ui_session

- Требует Bearer UI token и проходит через обычный auth middleware.
- Возвращает текущий `AuthContext` для UI: `status`, `user_login`, `actor_role`, `auth_type`.
- Используется shell-страницами `/admin`, `/support` и `/login` для проверки, что пользователь действительно вошёл под нужной ролью до показа рабочего интерфейса.

### 5.4 Web session: `/api/web/session/*`

- `POST /api/web/session/login` принимает `{"login": "...", "password": "..."}` и при успехе выставляет httpOnly cookie `pc_client_web_session` с `SameSite=Lax`.
- `POST /api/web/session/register` is controlled by `WEB_SELF_REGISTRATION_ENABLED`. It accepts only `login`, `password`, `password_repeat` and optional `device_link_code`, creates a DB UI user with `actor_role=user`, returns `next_path=/app/login?registered=1`, and must not issue a cookie or auto-login. Optional `device_link_code` only validates a live registration pairing and returns accepted metadata; active registry binding/profile completion remains a separate policy-controlled flow.
- `POST /api/web/session/password-reset-requests` is anonymous and always returns a generic accepted response for a syntactically valid login. It rate-limits by client/login, stores pending requests in `ui_password_reset_requests`, and must not reveal whether the UI user exists or expose reset tokens/password material.
- `GET /api/web/session/me` требует валидную cookie-session и возвращает typed payload `{"status":"success","data":{"user_login", "actor_role", "auth_type", "default_workspace", "available_workspaces", "permissions", "permissions_version"}}`.
- `PUT /api/web/requester/profile` requires the same authenticated web session, accepts only controlled requester profile fields, validates registry picker ids, and must not trust client role/account/person context beyond `AuthContext`.
- `default_workspace`, `available_workspaces`, `permissions` и `permissions_version` формируются сервером по effective access и считаются каноничным источником истины для redirect/access-gate и element-visibility логики нового `/app/*`; React-клиент не должен заново вычислять эти права из произвольных role-switch веток.
- `POST /api/web/session/logout` отзывает текущий UI token server-side и очищает cookie.
- Новый React `webapp` под `/app/*` не хранит bearer token в `localStorage`; сервер остаётся источником истины для web session через cookie и `AuthContext`.
- React `SessionProvider` treats `/api/web/session/me` bootstrap, manual refresh, login and logout as ordered session transitions: stale earlier responses must not overwrite a newer account state after login/logout.
- `GET /api/web/realtime/bootstrap` возвращает typed transport contract для нового `webapp` (`transport`, `auth_mode`, `socket_url`, `hello_message_type`, channel contracts). Реальное websocket-подключение идёт в `/ws_ui` и использует ту же cookie-session без раскрытия raw token в JS.

### 5.5 Web access-control catalog: `/api/web/admin/access/*`

- Доступ к access-control endpoints требует роли `admin`; UI-видимость не является security boundary.
- `server/access_control/catalog.py` содержит серверный каталог permission codes, русские operator labels, risk labels, role defaults и `permissions_version`.
- Access-control API:
  - `GET /api/web/admin/access/catalog` — роли и grouped permission catalog;
  - `GET /api/web/admin/access/summary` — пользователи из `ui_users`, очереди, access groups и membership counts;
  - `POST /api/web/admin/access/users/{user_login}/password` — admin-only смена пароля существующего UI-пользователя; request body принимает только новый `password`, политика пароля проверяется сервером, пароль хешируется, текущий пароль не читается и не возвращается;
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
- **Stage 10 — UI users из БД:** `AUTH_UI_DB_USERS_ENABLED`, `AUTH_UI_CONFIG_FALLBACK_ENABLED`, `AUTH_UI_MAX_FAILED_ATTEMPTS`, `AUTH_UI_LOCK_MINUTES`. Пароли в ui_users хранятся в виде хеша (pbkdf2_sha256), а неверные попытки логина обновляются одним атомарным SQL update, чтобы параллельные ошибки не теряли increments. Admin API: GET/POST/PATCH /api/admin/users, смена пароля, деактивация; self-service: POST /api/users/me/password. См. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-10-usersroles-из-бд).
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
