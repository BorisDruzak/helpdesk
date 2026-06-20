# Web-First Registration UX Contract

This is the Phase R1 contract for `PLANS.md`: web account registration, profile setup, requester cabinet entry, and browser-first device linking.

## Decisions

1. Web self-registration is controlled by `WEB_SELF_REGISTRATION_ENABLED`.
   - Default production behavior is fail-closed.
   - Pilot/dev stands may enable it explicitly.
   - Existing admin-created users and existing sessions must keep working when the flag is off.

2. Profile completion blocks normal requester work when `PROFILE_COMPLETION_REQUIRED=true`, not every route.
   - Default production behavior is blocking.
   - Rollout override may set `PROFILE_COMPLETION_REQUIRED=false`; the server still returns `missing_fields`, but `profile_completion.blocks.*` and requester feature flags become non-blocking.
   - Allowed while incomplete: `/app/requester/profile/setup`, profile view/edit, device-link status and confirmation, consents that are already pending, logout, and an explicit emergency ticket path when policy allows it.
   - Blocked while incomplete: normal ticket creation, requester knowledge actions that depend on audience context, ownership changes outside the device-link confirmation flow, feedback/reopen actions, and saved profile-dependent preferences.

3. Device-link confirmation is separate from profile completion.
   - The default registry policy auto-approves the first non-conflicting binding.
   - Administrators can switch device-link claims to manual approval in registry policies.
   - Browser and agent copy must reflect the returned registration status: linked for approved bindings, waiting for administrator only for manual-review statuses.

4. Department and location values must come from registry pickers in the first rollout.
   - Free-text creation is not allowed in normal user UI.
   - Pending suggestions may be added later behind policy, but must be auditable and must not create active registry objects directly.

5. `/app/device/register` remains a compatibility route only when it has an existing pairing id.
   - Missing pairing id shows a Russian product-safe error and directs the user to open the flow from the agent or enter the device-link code at `/app/device/pair`.
   - Future `/app/requester/devices/link` may become the primary cabinet entrypoint, but old direct links must not break.

6. Emergency ticket without completed profile is allowed only by policy.
   - Minimum context: authenticated web account, short problem description, reachable contact, and explicit marker that the profile is incomplete.
   - It must not create a device binding or bypass requester identity checks.
   - The request form must opt in through `availability_policy.available_without_completed_profile` and/or `availability_policy.available_without_agent_binding`.
   - `contact_required=true` requires a reachable contact before create/preview.
   - `requires_manual_triage=true` routes to support triage and must not auto-run device diagnostics unless a valid target device exists.

7. Mandatory first-rollout profile fields:
   - full name;
   - department;
   - location;
   - phone or internal extension.

8. Required registry entities for the first rollout:
   - people;
   - UI-login identities;
   - departments;
   - locations;
   - devices;
   - device-user bindings.
   Services and access/audience groups should be consumed when already present, but they are not mandatory to complete the initial profile.

## User Terms

Normal requester UI must use these terms:

| Concept | Russian label | Notes |
| --- | --- | --- |
| Web login credentials | Аккаунт | Login/password and workspace access only. |
| Registry-backed person details | Профиль | Full name, department, location, contact and work context. |
| Agent machine | Устройство | PC or local agent device. |
| User-device relationship | Привязка устройства | Connection between a profile and a device. |
| Primary diagnostic agent | Основное устройство | Server-resolved primary active agent/PC for diagnostics. |
| Requester workspace | Кабинет пользователя | Primary web workspace. |
| Pending device relationship | Заявка на привязку | User-facing state waiting for administrator action. |

Normal requester UI must not display these technical words: `pairing`, `binding`, `claim`, `session`, `registry person`, `pairing_id`, `binding_id`, `claim_id`, `account_session_id`, `affected_person_id`, `target_device_id`, `diagnostic_target_source`, `trace_id`, `operation_id`, raw `*_id` field names, raw UUIDs, raw backend enum values, raw policy names, or raw server error text.

Admin/debug surfaces may display technical identifiers when needed for operations.

## Primary Agent And Request Semantics

- The web cabinet is the requester's main workspace. It works from any browser and must not assume that the current physical computer is the diagnostic target.
- The primary agent is a server-resolved technical target from Registry device bindings. Normal requester tickets use the creator's primary device for diagnostics.
- The GUI agent is a local connection/status tool and may help with login, device linking and local actions. It must not own the requester profile or silently rebind the device.
- On-behalf tickets are allowed only by request-form policy. They store both creator and affected employee context, and diagnostics target the affected employee's primary device when one exists.
- Missing, offline or ambiguous primary device context is evidence for support and manual triage, not permission to run checks on the creator's current browser computer.
- Device ownership changes are admin-controlled preview/apply actions with reason and audit. A requester can ask for a change, but cannot self-rebind ownership by creating a ticket or logging in from the agent.

## Requester Help Articles

The requester-safe Knowledge seed must include these PA11 articles:

- `Как создать обращение за другого сотрудника`;
- `Что делать, если мой ПК не включается`;
- `Как запросить смену владельца устройства`;
- `Как привязать устройство к аккаунту`;
- `Как заполнить профиль пользователя`.

These articles live in `content_packs/knowledge/primary-agent-requester-guides.yaml`. They must use product terms such as `аккаунт`, `профиль`, `устройство`, `привязка устройства`, `кабинет пользователя`, `обращение` and must not expose raw internal ids such as `affected_person_id`, `target_device_id`, `binding_id` or `claim_id`.

## Route Contract

Target routes:

| Route | Purpose | Allowed roles | Canonical proof surface | Critical API calls | Expected Observer/audit events | Forbidden sensitive data |
| --- | --- | --- | --- | --- | --- | --- |
| `/app/register` | Account self-registration with login/password/repeat password and optional device-link code. | anonymous when `WEB_SELF_REGISTRATION_ENABLED=true`; authenticated users may switch account only through safe `next`. | Browser screenshot/DOM of account-only form and post-register login redirect. | `POST /api/web/session/register`. | UI user/account audit for registration; no device binding event. | Passwords, cookies, session tokens, raw device-link secrets, registry person ids. |
| `/app/login` | Web account login and safe continuation to requester/admin/support workspaces, plus a password-reset request entrypoint. | anonymous. | Browser screenshot/DOM of login success, password-reset request submission or safe Russian error. | `POST /api/web/session/login`, `POST /api/web/session/password-reset-requests`, `GET /api/web/session/me`. | Web session login/logout audit; password-reset request queue row. | Passwords, cookies, auth headers, session ids in visible UI. |
| `/app/requester` | Canonical requester workspace for profile-aware forms, Knowledge suggestions and ticket list/create. | authenticated requester/user. | Browser evidence from `/app/requester` with account/profile state and server-resolved context; API/DB supports but does not replace browser proof. | `GET /api/web/requester/bootstrap`, `POST /api/web/requester/tickets/preview`, `POST /api/web/requester/tickets`, `POST /api/knowledge/suggest`, `POST /api/knowledge/feedback`. | Ticket create, requester knowledge feedback/attempts, redacted web-cabinet Observer events for preview/create, diagnostic target missing/offline/ambiguous, Knowledge, chat, closure, feedback and reopen. | Raw person/device/binding ids, ticket context snapshot, policy JSON, trace ids, cookies, auth headers. |
| `/app/requester/profile/setup` | Required profile completion gate for Registry-backed requester details. | authenticated requester/user. | Browser evidence of required fields, registry pickers and return to `/app/requester`. | `GET /api/web/requester/bootstrap`, `PUT /api/web/requester/profile`. | Registry person/profile update audit. | Raw registry storage paths, metadata JSON, person ids, session tokens. |
| `/app/requester/profile` | Profile view/edit after setup. | authenticated requester/user. | Browser evidence of requester-safe profile projection. | `GET /api/web/requester/profile`, `PUT /api/web/requester/profile`. | Registry person/profile update audit when saved. | Raw metadata JSON, profile schema storage targets, person ids, session tokens. |
| `/app/requester/devices` | Device list and device-link entrypoint from the web cabinet. | authenticated requester/user. | Browser evidence of manual code lookup/direct link preview and pending/admin-approved state. | `GET /api/web/requester/devices`, `POST /api/web/registry/browser-pairings/lookup`, `GET /api/web/registry/browser-pairings/{pairing_id}`, `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm`. | Device-link claim/request audit; later admin approval/rejection audit. | Pairing secrets, pairing hashes, binding ids, claim ids, registry person ids, agent tokens. |
| `/app/device/pair` | Authenticated manual device-link code entry. | authenticated requester/user. | Browser evidence of safe code entry and device preview. | `POST /api/web/registry/browser-pairings/lookup`. | Browser-pairing lookup audit when available. | Raw pairing id/hash, tokens, binding ids, claim ids. |
| `/app/device/register` | Compatibility confirmation route for an existing device-link id. | authenticated requester/user. | Browser evidence of profile gate, safe preview, department/location pickers, confirm payload and return to `/app/requester/devices`. | `GET /api/web/registry/browser-pairings/{pairing_id}`, `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm`. | Device registration claim audit. | Pairing secrets, session tokens, raw person/binding/claim ids in visible UI. |
| `/app/device/login` | Existing authenticated login confirmation for a paired agent/device. | authenticated requester/user. | Browser evidence of device-scoped login confirmation/mismatch state. | `GET /api/web/registry/browser-pairings/{pairing_id}`, account-session confirmation endpoints used by the compatibility flow. | Account-session or login-confirmation audit. | Passwords, account-session tokens, binding ids, claim ids, pairing secrets. |
| `/app/admin/registry` | Admin moderation center for people, devices, bindings, claims, sessions, ownership transfer and password-reset requests. | admin/support with registry permissions. | Browser evidence of registry queues/actions and preview/apply dialogs. | `/api/web/admin/registry*`, `/api/web/admin/registry/profile-schema*`, `/api/web/admin/registry/password-reset-requests*`, account-session and registration admin routes. | Registry admin events for bind/transfer/revoke/merge/import/profile-schema/account-session actions; password-reset queue completion. | Raw tokens, cookies, auth headers, password material, unredacted secrets. |
| `/app/tickets` | Support ticket list/detail workspace, including creator/affected/diagnostic target context. | support/admin/auditor according to ticket permissions. | Browser evidence of support-visible ticket context without requester-only leakage. | `/api/web/support/queue`, `/api/web/support/tickets/{ticket_id}*`, support mutation routes. | Ticket events, workflow/audit events, diagnostic and knowledge attempt events, redacted support chat/status web-cabinet Observer events. | Raw requester-public access codes, cookies, auth headers, hidden Knowledge titles for unauthorized actors, unrestricted raw policy payloads, raw support message/status comment text in Observer payloads. |
| `/app/admin/observer` | Technical Observer workbench for traces, integrity and runtime diagnostics. | admin/auditor or explicit observer permissions. | Browser evidence of observer search/filter/detail state when Observer UI changes. | `/api/web/admin/observer/*`. | Observer trace/runtime/integrity rows and access audit. | Tokens, cookies, auth headers, raw secrets, unredacted operation parameters. |

`/app/device/register` without a device-link id must not show `pairing_id`; it must show: `Откройте эту страницу из агента или введите код подключения.`

## Requester Consent UI Contract

Pending requester consent is rendered through the shared React card in `webapp/src/features/requester/consent-card.tsx` on both `/app/requester` and `/app/requester/tickets/:ticketCode`.

Requester ticket browser routes must prefer the requester-safe `ticket_code` (`/app/requester/tickets/:ticketCode`). The authenticated requester API accepts `{ticket_ref}` and resolves it to a caller-owned ticket by safe code, with legacy raw `ticket_id` accepted only as a compatibility fallback after the same ownership boundary.

The card must:

- show the requester-safe action category: diagnostics, screen view, remote control or administrative access;
- explain action, access scope, reason, related request, requester and expiry/duration;
- use explicit `Разрешить` and `Отклонить` controls and lock the selected card while a decision is in flight;
- call only `/api/web/requester/consents/{consent_id}/approve|deny` and rely on the existing requester ownership, idempotency and audit checks;
- never display or expose through aria text raw consent, subject, session, binding, person, actor or device identifiers, Remote Assist signaling values or full raw UUIDs.

## R2 Account Registration Contract

`POST /api/web/session/register` creates only a web account. It is disabled unless `WEB_SELF_REGISTRATION_ENABLED=true`.

Request fields:

| Field | Required | Notes |
| --- | --- | --- |
| `login` | yes | 3-128 characters: Latin letters, digits, `.`, `_`, `-`, `@`. |
| `password` | yes | Uses the existing server password policy. |
| `password_repeat` | yes | Must match `password`. |
| `device_link_code` | no | Validates an existing registration pairing code, but does not create an active device binding. |

Response on success is `201` with `user_login`, `actor_role=user`, `next_path=/app/login?registered=1`, and optional accepted `device_link` metadata. The endpoint must not set the web-session cookie and must not auto-login.

`/app/register` is account-only. It must not ask for full name, department, location or other profile data. After successful account creation it redirects to `/app/login?registered=1`, where the login page shows `Аккаунт создан. Войдите, чтобы продолжить настройку доступа.`

`POST /api/web/session/password-reset-requests` is anonymous and accepts only `login`. It returns a generic accepted response whether or not the user exists, rate-limits by client/login, stores a pending admin-visible request for operational handling, and never returns account existence, password data, reset tokens or direct login capability. `/app/login?forgot_password=1` opens this request form directly.

## R3 Profile Setup Contract

`GET /api/web/requester/bootstrap` returns `profile_completion` for every authenticated requester. The payload includes:

- `complete`: `true` only when the requester has a resolved `RegistryPerson` with full name, department, location and phone/internal extension.
- `required`: current rollout policy from `PROFILE_COMPLETION_REQUIRED`.
- `setup_path`: `/app/requester/profile/setup`.
- `required_fields` and `missing_fields` with requester-facing Russian labels.
- `blocks`: booleans for normal ticket create/preview and requester knowledge actions while the profile is incomplete and the policy requires completion. Device-link confirmation is a separate lifecycle step and is not blocked by requester profile completion by default.
- `next_actions`: the server-owned ordered action list. Order is profile setup, requester answer, pending consent, solution confirmation, device linking, then new request. React must not rebuild this priority locally except for backward-compatible fallback when the field is absent.

`GET /api/web/requester/profile` returns requester-safe profile data plus `account_summary` (`login`, display name, email and linked-profile flag). It must not expose identity provider names, raw identifiers, `verified`, identity ids, source fields or identity metadata; those remain admin Registry API data.

`PUT /api/web/requester/profile` is the authenticated requester profile update endpoint. It writes to `RegistryPerson`, creates or refreshes the verified `ui_login` `RegistryPersonIdentity`, and accepts only the controlled editable fields: `full_name`, `department_id`, `location_id`, `phone`, `internal_extension`, `position`, `workplace_label`, `preferred_contact_method`, `custom_fields`, plus the caller-owned `person_id` when editing an existing profile.

Department and location values must come from registry picker options. Invalid or inactive `department_id` / `location_id` values return `VALIDATION_ERROR`; attempts to update another person's profile return `REQUESTER_PROFILE_FORBIDDEN`.

Normal requester ticket preview/create returns `403 REQUESTER_PROFILE_INCOMPLETE` while the profile is incomplete and `profile_completion.blocks.ticket_*` is true. The React requester workspace follows `blocks`, not only `complete`, so a temporary rollout override can leave missing-field guidance visible without stranding users. After a successful profile save it returns to `/app/requester`.

The built-in `request_forms` fallback exposes only setup assistance forms when the requester profile is incomplete or no agent binding exists: `profile_completion_help` and `agent_binding_help`. Both opt into `available_without_completed_profile`, `available_without_agent_binding`, `requires_manual_triage` and `contact_required`; normal request forms stay hidden and remain rejected by the requester create/preview APIs until the relevant gates are complete.

Requester dynamic request forms do not support pre-create `file` fields until draft upload exists. The request-form schema rejects `type=file`; post-create attachments remain the ticket chat attachment flow.

`/public_api/ticket_forms/current?pack_key=request_forms` is the requester-facing form contract. It returns the preferred legacy request-form pack plus active standalone Helpdesk Model Registry templates published by Request Studio, projected through the same requester-safe form runtime used by create/preview submission.

## R4 Device Linking Contract

`/app/requester/devices` is the primary web-cabinet entrypoint for linking a new agent device. The user can paste a device-link code from the agent or open a direct link with `pairing_id`; both paths reuse the existing authenticated browser-pairing endpoints:

- `POST /api/web/registry/browser-pairings/lookup` for manual code lookup.
- `GET /api/web/registry/browser-pairings/{pairing_id}` for safe device preview.
- `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm` for final link-request creation.

The device preview may show only requester-safe facts: hostname, OS, agent version, pairing status and expiry. It must not expose tokens, raw pairing code hashes, session tokens, internal binding ids, or registry-person identifiers.

The dedicated React requester devices route renders device cards, safe device detail, code -> preview -> confirm -> result states and the owner-check request path without a diagnostic radio selector or visible pairing/binding/claim/session identifiers. Direct `pairing_id` links remain accepted through the URL but the id itself is never displayed.

Registration confirmation does not require a completed requester profile. If the authenticated web user has no completed registry-backed `RegistryPerson`, the server creates or reuses a minimal account-owned person snapshot from the verified web account, creates the registration claim, and keeps normal requester ticket actions gated by `profile_completion.blocks.ticket_*`.

If the user reached profile setup before creating the correct requester account, the setup form exposes a normal-user CTA to `/app/register?switch_account=1&next=...`. Account registration preserves the same `next` value through the post-registration login screen so the user can return to profile setup or device-link confirmation after creating and signing into the web account.

Confirmation creates the registration claim from the caller-owned registry person profile snapshot when available, or from the authenticated web account when the profile is still incomplete. Browser-submitted person, binding, account-session, token or free-text profile fields are ignored. The selected `department_id` and `location_id` are sent as controlled picker ids and validated server-side; they may influence the registration claim/context but must not replace the authenticated account identity. The default policy automatically approves the first non-conflicting device binding; when admin policy switches to manual approval, the requester UI shows `Ожидает проверки администратора` after a successful link request. After a successful browser confirmation, the page redirects to `/app/requester/devices` and also renders a visible fallback link to the web cabinet before the redirect fires.

## R6 Profile Schema Contract

Requester profile schema is controlled configuration, not an unrestricted registry constructor.

Admin APIs:

- `GET /api/web/admin/registry/profile-schema` returns the effective profile schema, including storage targets for admin review.
- `PUT /api/web/admin/registry/profile-schema` accepts `field_overrides`, controlled `custom_fields` and a `reason`; it persists through `registry_admin_policies(policy_key=requester_profile_schema)` and writes a `registry_admin_events` audit event `profile_schema_updated`.
- `POST /api/web/admin/registry/profile-schema/preview` validates a draft without saving.

System fields cannot be hidden, deleted or made optional when they are required: `full_name`, `login_identity`, `department_id`, `location_id`, `phone`, `active_device_links`. Optional built-in fields such as `internal_extension`, `position`, `workplace_label` and `preferred_contact_method` may be hidden, made required and given helper text.

Custom fields are allowed only in the controlled block:

- key must be a safe Latin identifier;
- storage target must be exactly `registry_people.metadata_json.profile_custom_fields.<key>`;
- audit behavior is `profile_custom_field_change`;
- requester profile writes submit values under `custom_fields`.

Requester APIs return a safe schema projection. They include labels, field types, required/visible flags, helper text, validation and options, but do not expose `metadata_json`, storage targets, raw registry targets or audit internals. Required custom fields participate in `profile_completion.missing_fields` and block normal requester work until filled.

The React admin registry page exposes `Схема профиля · P1` for schema editing. The requester profile/setup route and admin preview reuse the shared requester profile runtime, render visible custom fields from `profile_schema`, hide optional fields whose schema has `visible=false`, and submit only visible editable custom values under `custom_fields`.

## R7 Registry Production Context Contract

R7 extends the existing registry model with focused production context that is useful for request forms, routing, support diagnostics, reporting and Knowledge targeting. It does not introduce a generic database builder and it does not require a schema migration.

Projection rules:

- Person context is projected from `RegistryPerson` and controlled `metadata_json`: `position`, `workplace_label`, `internal_extension`, `manager_person_id`, manager display name and a compact `production_context` object.
- Department context exposes manager display name when `manager_person_id` points to a known registry person.
- Service context exposes owner display name, `criticality`, `audience` and `audience_group_id` from existing service fields/metadata.
- Asset context exposes assigned owner and responsible person ids/display names from existing ownership and metadata fields.

Admin mutation rules:

- Admin person create/update accepts only the focused work-context fields `position`, `workplace_label`, `internal_extension` and `manager_person_id`.
- These values are stored in `RegistryPerson.metadata_json` and appear in the `person_created` / `person_updated` audit before/after payloads.
- Requester profile APIs remain governed by the R6 profile schema and do not expose raw `metadata_json` storage details.

Quality issue kinds:

- `person_missing_department`
- `person_missing_location`
- `asset_missing_owner_or_responsible`
- `department_pending_confirmation`

The React admin registry People tab shows compact work context for operators, and the person edit dialog writes the controlled fields through the typed admin registry API.

## R8 Request Form Context Contract

Request forms consume resolved requester context; they do not own identity or profile lifecycle.

Resolver rules:

- The server recomputes requester context from the authenticated web session, the caller-owned completed `RegistryPerson` and the selected active binding/device when present.
- Client-supplied `requester_context` and `device_metadata` are compatibility hints only. They must not override server-resolved person, department, location, binding, device, asset or account-mode facts.
- The context schema is `requester_context_v1` and includes safe profile, device, form prefill, account and routing facts.
- Ticket create stores `custom_fields.requester_context_snapshot` plus flat routing aliases such as `requester_department_id`, `requester_location_id`, `requester_device_id`, `requester_asset_id`, `requester_binding_id` and `requester_account_mode`.

Form rendering rules:

- The requester cabinet can prefill empty or previously auto-filled request-form fields from `requester_context.form_prefill`.
- Manual requester edits must be preserved when context refreshes.
- Department and location picker options come from Registry options; device picker options come from active requester devices/bindings; service picker options come from Service Catalog.
- Preview output includes a requester-safe context explanation so the user and support can see which profile/device facts influenced the form.

Policy rules:

- Routing, priority, SLA and diagnostic policies may use the flat aliases or the stable snapshot, but they must use server-resolved values from preview/create.
- Incomplete profiles remain governed by the R3 profile-completion gate unless a specific no-device/emergency policy allows the flow.

## R9 Knowledge Context Contract

Knowledge access and recommendations consume Registry context; they do not own identity or profile lifecycle.

Access rules:

- Requester knowledge search, suggestions, portal actions and Ask/RAG resolve the authenticated web actor to a `RegistryPerson` and `EffectiveAudience` before filtering.
- Department, department tree, location, access group, audience group, role, service and person audience rules use the same `KnowledgeAccessService` decision before result projection.
- `requester_portal` remains a compatibility surface alias for canonical `requester_pre_submit`; explicit binding surfaces must include the canonical consumer surface or the article is removed before title/snippet projection.
- Ask/RAG/vector retrieval applies the same audience and binding-surface gates before ordering, rerank, citations and answer prompt construction.
- On-behalf requester flows do not expand the creator's Knowledge audience; requester-side attempts stay scoped to `creator_visible` / `creator`.

Recommendation rules:

- Pre-submit suggestions may use safe request text plus R8 `form_payload`, `requester_context` and selected `device_metadata` as search signals.
- Suggestion query extraction must skip raw ids, token/secret/session/cookie/password fields, email, phone and other sensitive identifiers. These values may be present in server-owned context snapshots but must not become search analytics text.
- Ticket create stores sanitized `knowledge_attempts` so support can see which requester-safe articles were viewed, marked not helpful or followed by ticket creation.
- Ask-to-request transfer may carry only sanitized item/version refs and the user query into `knowledge_attempts`; denied titles, internal denial reasons and raw audit ids stay out of requester UI.

Explainability rules:

- Admin Knowledge audience explain remains the source of truth for why an article is visible or hidden.
- Normal requester UI must not reveal denied article titles, hidden section names, raw audience-rule ids, trace ids or internal diagnostics.
- Web requester create stores server-owned `profile_schema.version` and dynamic `form_schema_version` evidence, and `observer.web_cabinet` flags missing profile/form schema versions, unsafe diagnostic-target evidence, on-behalf Knowledge audience leakage and missing Customer History projection.
- Requester Knowledge, form runtime and chat Observer traces use redacted flags, counts and version markers only; they must not include raw query text, chat message text, submitted form values, emails, tokens or item/version ids.

## R10 Admin Moderation Contract

The admin registry is the moderation surface for web-first registration. It can see enough context to approve, reject, merge, transfer and audit safely, but normal rows must still avoid raw JSON-first workflows.

Visibility rules:

- `GET /api/web/admin/registry` projects pending link claims, people, UI-account identity links, account sessions, duplicate candidates, department/location suggestions and device ownership context through typed fields.
- Person rows include schema-aware `profile_completion` with status and missing field labels from the active requester profile schema.
- Profile completion visibility is for moderation only. It must not expose requester-only storage internals, raw profile custom-field targets, tokens, sessions or secret values.

Moderation rules:

- Pending device-link claims use Russian action labels for approve/reject and must preserve the admin reason in the resulting audit trail.
- Transfer-owner, merge, bulk and import operations require a preview/dry-run before apply; preview endpoints are read-only and must not write events.
- Destructive or ownership-changing apply operations require a reason and return a normalized operation report for the UI.
- The timeline drawer is the canonical admin audit surface for `device`, `person`, `binding`, `account_session` and `claim` changes.

## R11 Localization Contract

Web-first registration surfaces are Russian-first for normal users and admins.

User-facing rules:

- Normal UI and accessible labels must use product terms: `аккаунт`, `профиль`, `устройство`, `привязка устройства`, `кабинет заявителя`, `обращение`, `заявка на привязку`.
- Requester device facts render as `Агент <version>`, `Версия агента не указана`, `Привязка активна`, `Статус привязки уточняется`, `В сети`, `Не в сети` or `Статус сети не указан`; Latin `agent unknown`, `status unknown`, `online` and `offline` are not normal-user labels.
- Knowledge Ask draft context is localized as `Запрос из базы знаний`, `Вопрос в базе знаний`, `Статус ответа` and `Режим поиска`; raw audit ids/slugs are not inserted into requester draft text.
- Admin registration blockers must map backend reason codes to Russian explanations. For example, `active_primary_user_exists` renders as `уже есть активный основной пользователь`.
- Touched files must remain valid UTF-8. Common mojibake and replacement-character markers are defects and are guarded by the localization test.
- Split requester pages and shared runtimes must keep accessible names free of field keys such as `department_id`, `device_id` and `affected_person_id`. Dynamic request/profile controls use the visible Russian field label as the accessible label, while technical keys stay only in internal payloads.
- Required profile/setup and request-form validation must focus the first missing field before calling mutating APIs. User-visible validation summaries and mutation results use `aria-live` regions so keyboard and screen-reader users receive the same status.
- Phase L browser evidence is collected by `webapp/artifacts/requester-phase-l-a11y-responsive-check.mjs`: profile setup, device link, dynamic request form and chat are exercised by keyboard, visible/aria forbidden terms are scanned, and requester routes are checked for horizontal overflow at 390×844, 768×1024, 1366×768, 1440×900 and 1920×1080.

## Status Labels

Requester-facing device-link statuses:

| Backend value | User label |
| --- | --- |
| `pending` | Ожидает подтверждения |
| `confirmed` | Подтверждено |
| `expired` | Срок действия истёк |
| `rejected` | Отклонено |
| `canceled` | Отменено |

Requester-facing registration statuses:

| Backend value | User label |
| --- | --- |
| `pending_admin_review` | Ожидает проверки администратора |
| `pending_user_confirmation` | Ожидает подтверждения |
| `pending_verification` | Ожидает проверки |
| `user_confirmed` | Ожидает проверки администратора |
| `admin_confirmed` / `approved` / `active` | Устройство привязано |
| `conflict` | Требуется проверка администратора |
| `rejected` | Отклонено администратором |
| unknown value | Статус уточняется |

## Error Dictionary

Requester-facing errors must be Russian and action-oriented:

| Condition | User text |
| --- | --- |
| Missing device-link id on `/app/device/register` | Откройте эту страницу из агента или введите код подключения. |
| Manual device-link code not found or expired | Код подключения не найден или истёк. |
| Department id rejected | Выберите подразделение из справочника. |
| Location id rejected | Выберите локацию из справочника. |
| Current web account is not linked to the pairing device | Текущий веб-аккаунт не привязан к этому компьютеру. Выйдите и войдите под привязанным пользователем или привяжите устройство через регистрацию. |
| Generic device-link load failure | Не удалось загрузить привязку устройства. |
| Generic device-link confirmation failure | Не удалось подтвердить устройство. |
| Profile incomplete gate | Заполните профиль, чтобы продолжить работу в кабинете пользователя. |
| Self-registration disabled | Самостоятельная регистрация временно недоступна. Обратитесь к администратору. |
| Password repeat mismatch | Пароли не совпадают. |
| Duplicate login | Пользователь с таким логином уже существует. |
| Password policy failure | Пароль не соответствует политике безопасности. |

## Evidence

R1 first slice:

- `webapp/src/pages/device-pairing/index.tsx` maps requester-visible device-link and registration statuses to Russian labels.
- `webapp/src/pages/device-pairing/device-pairing-page.test.tsx` verifies that missing device-link id and pending admin review do not expose raw technical terms.

R2 account-registration slice:

- `server/web_api/session_handlers.py` exposes feature-flagged `POST /api/web/session/register`, creates role `user`, validates password/repeat/duplicate login and does not set a session cookie.
- `server/web_api/session_handlers.py` exposes anonymous `POST /api/web/session/password-reset-requests`; `webapp/src/features/auth/login-page.tsx` shows the request form and `/app/login?forgot_password=1` opens it directly.
- `webapp/src/features/auth/register-page.tsx` implements `/app/register` with login/password/repeat password and optional device-link code only.
- `webapp/src/features/auth/register-page.test.tsx` verifies account-only fields, post-registration login redirect, repeat-password validation, duplicate-login errors and optional device-link code payload.

R3 profile-setup slice:

- `server/requester/identity_service.py` returns profile completion status and writes the authenticated user's profile to registry-backed person and identity records.
- `server/web_api/requester_handlers.py` exposes `PUT /api/web/requester/profile` and blocks normal requester ticket preview/create with `REQUESTER_PROFILE_INCOMPLETE` until completion.
- `webapp/src/pages/requester/profile-page.tsx` renders the web-first profile setup/profile routes with registry department/location pickers, phone-or-internal-extension completion, admin-published custom fields, unsaved-change protection and a safe `next` return after profile save.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r3-20260615/`.

R4 device-link slice:

- `server/web_api/registry_handlers.py` allows registration confirmation for authenticated requester accounts even when the requester profile is incomplete.
- `server/registry/browser_pairing_service.py` builds the registration claim profile snapshot from the resolved `RegistryPerson` when available, otherwise from the authenticated web account, not browser-supplied profile fields.
- `webapp/src/pages/requester/devices-page.tsx` implements the `/app/requester/devices` and `/app/requester/devices/link` manual-code/direct-link flow, device cards, safe owner-check handoff and Russian result/status labels without exposing pairing/binding/claim/session identifiers.
- `webapp/src/pages/device-pairing/index.tsx` keeps incomplete-profile registration confirmation on the pairing page, sends only controlled department/location picker ids with confirmation, redirects successful registration confirmation to `/app/requester/devices`, and explains `PAIRING_FORBIDDEN` without exposing backend wording.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r4-20260615/`.

R6 profile-schema slice:

- `server/registry/profile_schema_service.py` implements the controlled requester profile schema service over `registry_admin_policies` and `registry_admin_events`.
- `server/requester/identity_service.py` enforces schema-aware profile completion and returns a requester-safe schema projection.
- `server/web_api/registry_handlers.py` and `server/routes.py` expose admin profile-schema get/save/preview routes.
- `webapp/src/features/admin/registry/registry-profile-schema-tab.tsx` adds the admin schema editor under `/app/admin/registry`.
- `webapp/src/features/requester/profile-runtime/index.tsx` renders schema custom fields for requester profile/setup and admin preview, hides optional fields disabled by schema, validates publishable schema drafts and omits hidden custom fields from requester saves.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r6-20260615/`.

R7 production-context slice:

- `server/registry/service.py` projects focused production context for people, departments, services and assets into the admin registry snapshot without adding a generic registry builder.
- `server/web_api/registry_handlers.py` stores controlled admin person work-context metadata and audits before/after values.
- `webapp/src/features/admin/registry/registry-people-tab.tsx` and `registry-person-edit-dialog.tsx` show/edit the focused person context in `/app/admin/registry`.
- R7 quality checks flag missing person department/location, device owner/responsible gaps and pending department confirmation.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r7-20260615/`.

R8 request-form-context slice:

- `server/requester/identity_service.py` builds requester context v1, requester-safe preview projection and stable custom-field aliases.
- `server/web_api/requester_handlers.py` recomputes requester context for preview/create and stores `requester_context_snapshot` with flat aliases on ticket create.
- `webapp/src/pages/requester/new-request-page.tsx` pre-fills request forms from safe context, renders registry-backed picker options and shows preview context explanation.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r8-20260615/`.

R9 knowledge-context slice:

- `server/knowledge/suggestion_service.py` uses safe requester form/profile/device context as pre-submit suggestion search signals while preserving effective-audience filtering.
- `webapp/src/pages/requester/new-request-page.tsx` sends R8 requester context and selected safe device metadata to `/api/knowledge/suggest` and persists requester `knowledge_attempts` on ticket create.
- Existing Knowledge audience/search/suggestion/Ask/RAG tests cover Registry audience enforcement before projection.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r9-20260615/`.

R10 admin-moderation slice:

- `server/registry/service.py` projects schema-aware `people[].profile_completion` into the admin registry snapshot.
- `webapp/src/features/admin/registry/registry-people-tab.tsx` renders Russian profile-completion status and missing field labels for moderators.
- Existing admin registry previews, person/UI-account links, merge, transfer, revoke, approval and timeline flows cover the rest of the R10 moderation workflow.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r10-20260615/`.

R11 localization slice:

- Split requester pages (`new-request-page.tsx`, `devices-page.tsx`, `tickets-page.tsx`) use shared labels from `webapp/src/features/requester/labels.ts` for Knowledge Ask draft context, requester device version/status/activity labels and requester accessible labels.
- `webapp/src/features/admin/registry/registry-requests-tab.tsx` maps conflict blocker reason codes to Russian explanations.
- `pc_agent/ui_gui/main_window.py` has the repaired invalid-account-session Russian error text.
- `scripts/test_web_first_registration_localization.py` guards touched files against mojibake and known raw normal-UI snippets.
- Browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r11-20260615/`.

R12 compatibility, migration and cleanup slice:

- `server/config.py` defines `PROFILE_COMPLETION_REQUIRED=true` by default alongside the fail-closed `WEB_SELF_REGISTRATION_ENABLED` server flag.
- `server/requester/identity_service.py` keeps `profile_completion.missing_fields` accurate while making `blocks` and requester feature flags policy-aware. With the rollout override disabled, normal requester preview/create can proceed without changing the profile setup contract.
- Existing pending `device_registration_claims` remain visible in both `GET /api/web/requester/bootstrap` as user-facing device-link requests and `GET /api/web/admin/registry` as admin moderation rows.
- Existing confirmed bindings and `verified_other_account` sessions keep validating through `AccountSessionService` until logout, revoke, base binding revoke or expiry; validation returns explicit invalidation codes for GUI recovery.

PA10 emergency/no-agent request-form slice:

- `server/tickets/form_catalog.py` normalizes request-form `availability_policy` booleans and exposes compatibility fields for legacy pack consumers.
- `server/web_api/requester_handlers.py` lets only explicitly allowed forms bypass incomplete-profile or missing-agent gates, requires contact data when `contact_required=true`, and stores manual triage plus no-primary-agent diagnostic evidence.
- `server/tickets/routing_service.py` sends `requires_manual_triage` availability-policy tickets to `servicedesk_l1`.
- `webapp/src/pages/requester/new-request-page.tsx` hides normal forms when profile/agent context is incomplete and shows a Russian warning that diagnostics may be unavailable until support clarifies the profile and primary device.
- `BrowserPairingService.expire_stale_pairings()` and `AccountSessionService.expire_stale_sessions()` provide service-level cleanup for expired browser pairings and temporary account sessions without deleting audit history.
- Rollback path: set `WEB_SELF_REGISTRATION_ENABLED=false` to stop new web account creation and set `PROFILE_COMPLETION_REQUIRED=false` to make incomplete profiles advisory during rollout recovery. Normal agent GUI releases remain browser-only; older agents may still use the legacy backend endpoints during compatibility rollout. Do not manually patch deployed files; deploy the rollback through the project release scripts.
