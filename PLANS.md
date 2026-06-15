# Active Work: Web-first Registration, Profiles and Registry Context Refactor

Status, 2026-06-15: completed at candidate `c5be05b90cb991903b08cee7cd88c7ecbe06bf11`. R0-R14 implementation, targeted tests, deploy smoke, browser evidence and local Windows GUI-agent evidence are recorded below. The refactor simplifies requester onboarding, moves the user-facing workflow into the browser, makes the web requester cabinet the primary workspace, and keeps the GUI agent as a secondary local helper for device handoff, emergency ticketing, consent and diagnostics.

Follow-up, 2026-06-16: strict browser-only agent registration is now the active decision. The normal GUI agent no longer builds the legacy full-profile registration page, local registration buttons, or local submit/confirm handlers; backend legacy endpoints remain only as compatibility API surface for older agents. Env feature flags are covered by explicit regression tests, and repeatable live smoke scripts now cover clean account/profile/device/ticket/KB onboarding plus rollout compatibility cases.

Carryover closed before this plan became active: Knowledge K4 focused policy tests were added in `22825944`, and Knowledge K3 binding eligibility preview was implemented and live-checked in `536f749e`; evidence is under `artifacts/browser_live_validation/knowledge-binding-preview-536f749e-20260615/`.

## Product thesis

Аккаунт не равен профилю. Профиль не равен устройству. Устройство не равно пользователю.

- Account: web login credentials and role used to enter `/app`.
- Profile: registry-backed person context: ФИО, подразделение, локация, контакты, должность, devices, access/audience attributes.
- Device link: approved binding between a registry person and a concrete agent device.
- Agent identity: machine identity only: `device_id`, agent token, WebSocket/API authorization and technical health.
- Request forms: ticket/request templates that consume profile and registry context, but do not own the profile lifecycle.
- Knowledge access: audience and registry-based visibility for requester-safe knowledge and RAG retrieval.

Primary UX direction: registration, profile completion, device linking, requester ticket creation and knowledge search happen in the web cabinet. The GUI agent must stop being a profile editor or primary registration surface.

---

## Non-negotiable invariants

1. Registration is browser-first.
   - No active full-profile registration form in the GUI agent.
   - GUI agent may only create/copy/open a browser device-linking flow and show status.

2. Account creation is separate from profile completion.
   - Initial account form: login, password, repeat password.
   - Optional device pairing code may be entered during account registration, but profile fields must not be mixed into account creation.

3. Profile is web-first and registry-backed.
   - Profile completion is required before normal requester work.
   - Profile data writes to registry entities and stable registry relationships, not only to arbitrary JSON.

4. Web requester cabinet is the main user workspace.
   - Tickets, devices, profile, knowledge, consents and device linking live in `/app/requester`.
   - Agent GUI is secondary: open web cabinet, link this device, show status, emergency ticket, consent/remote assist.

5. Request forms and knowledge must use registry context.
   - Forms prefill from profile/device/service context.
   - Knowledge audience rules use person, department, location, access/audience groups, service and role.

6. Full Russian localization is required.
   - User-facing labels, hints, empty states, errors and confirmations must be Russian.
   - Technical identifiers may remain English in code/API only.
   - No mojibake, mixed encodings, placeholder English, raw ids in normal UI, or unexplained backend error text.

---

## Current system map to preserve or refactor

Existing useful foundations:

- `device_user_bindings` is the authoritative device-person link.
- `device_registration_claims` supports pending/admin-reviewed device registration.
- `device_account_sessions` separates machine identity from requester identity.
- `device_browser_pairings` already supports browser login/registration pairing.
- `/app/device/pair`, `/app/device/login`, `/app/device/register` already require a web session.
- `/app/requester` already exists and has profile/devices/tickets/consents APIs.
- Admin registry already has people, identities, bindings, account sessions and transfer-owner actions.
- Ticket form builder already supports picker fields, field roles, process mapping and policy publication.
- Knowledge audience rules already support person, department, department tree, location, access group, audience group, role and service targets.

Main refactor target:

- Stop treating the GUI agent as the main user registration/profile UI.
- Promote web requester workspace to the primary requester product.
- Make profile/schema/registry/form/knowledge context coherent and visible.

---

## Scope

In scope:

- Web account self-registration.
- Web profile setup and profile completion gate.
- Browser-first device linking.
- Removal/hiding of GUI agent profile registration UI.
- Registry-backed profile fields and additional registry context.
- Request form integration with requester profile and registry context.
- Knowledge access/retrieval integration with registry audience context.
- Admin registry/profile/schema controls.
- Russian localization and UX copy.
- Automated and live validation.

Out of scope for this phase:

- Replacing the whole auth system with SSO/AD-only auth.
- Building an unrestricted low-code database/registry constructor.
- Removing existing backend tables before migration evidence exists.
- Redesigning the entire support command center.
- Reworking unrelated knowledge authoring UX, except where knowledge access depends on registry/profile context.

---

## Target user journeys

### Journey A — user creates account without an agent

1. User opens `/app/register`.
2. User enters login, password and repeated password.
3. Server creates a `user` web account.
4. User enters `/app/requester/profile/setup`.
5. User fills required profile fields.
6. Server creates or updates `RegistryPerson` and identities.
7. User reaches requester cabinet.
8. Device list shows an empty state: `Устройства пока не привязаны`.
9. User can create web tickets without an agent if policy allows no-device tickets.

Acceptance:

- Account creation does not ask for ФИО/department/location/device.
- Profile completion is the first in-cabinet task.
- No agent token or device binding is required for a web-only account.

### Journey B — user creates account and links the current agent device

1. GUI agent shows `Привязать это устройство через браузер`.
2. Agent creates browser pairing and shows:
   - `Открыть в браузере`;
   - `Скопировать код привязки`;
   - pairing expiry/status.
3. User opens `/app/register` or `/app/device/pair`.
4. User creates or enters a web account.
5. User enters pairing code if not opened from direct link.
6. User completes profile in web cabinet.
7. Server creates a device registration claim for that profile/device.
8. Admin approves, auto-approves, or rejects according to policy.
9. User sees linked device status in web cabinet and agent sees updated account-state.

Acceptance:

- GUI agent never asks for full profile fields.
- Pairing code can be copied and pasted during account registration.
- Pending/admin review status is visible in both browser and agent.

### Journey C — existing user links a new device

1. User opens `/app/requester/devices`.
2. User clicks `Привязать устройство`.
3. User enters pairing code from the agent or follows the agent-opened link.
4. User confirms device details.
5. Registration claim is created.
6. Admin approval produces active `device_user_bindings`.

Acceptance:

- Device linking is discoverable from the web cabinet.
- User sees device hostname, OS, agent version and status before confirmation.
- If claim is pending, the UI says what happens next.

### Journey D — user uses agent after device was linked

1. Agent starts.
2. Agent account gate fetches account-state.
3. If the web user/device link is approved, agent shows a simple card:
   - owner/person;
   - device link status;
   - buttons: `Открыть кабинет`, `Создать аварийное обращение`, `Обновить статус`.
4. Normal work is directed to web cabinet.

Acceptance:

- Agent no longer exposes full profile registration form.
- Agent can still perform emergency flows and consent/remote assist.

### Journey E — other account on a registered device

1. User is not the registered owner but needs to create a ticket on a registered device.
2. Agent offers `Войти временно как другой пользователь` only as a secondary/advanced action.
3. User enters minimal reason/account data.
4. Admin approves.
5. Tickets from this session are visibly marked as `создано с другого аккаунта на зарегистрированном устройстве`.

Acceptance:

- Other-account flow remains available for operational exceptions.
- It does not transfer ownership and does not alter device binding.

---

## Target information architecture

### `/app/requester`

Recommended sections and Russian names:

- `Главная`
  - profile completion status;
  - open tickets;
  - pending consents;
  - linked devices;
  - recommended knowledge.
- `Мой профиль`
  - ФИО, отдел, должность, локация, контакты;
  - identities and account links;
  - profile quality status.
- `Мои устройства`
  - linked PCs and devices;
  - pending device links;
  - button `Привязать устройство`.
- `Обращения`
  - create/list/detail/message/feedback/reopen.
- `База знаний`
  - requester-safe search, recommendations and AI answer if allowed.
- `Согласования и доступы`
  - user consents, remote assist requests, approval requests.

### GUI agent

Recommended main states:

- `Устройство не привязано`
  - primary: `Привязать через браузер`;
  - secondary: `Скопировать код`;
  - secondary: `Открыть настройки подключения`.
- `Ожидает подтверждения`
  - status text;
  - `Проверить статус`;
  - `Открыть кабинет`.
- `Устройство привязано`
  - owner card;
  - `Открыть кабинет`;
  - `Создать аварийное обращение`;
  - `Обновить статус`.
- `Нет связи с сервером`
  - connection diagnostics;
  - emergency/offline guidance.

Forbidden normal GUI actions:

- Full profile form.
- Local registration form with ФИО/department/location/device type.
- Unexplained local account switching as a primary action.

---

## Data model target

### Account domain

Required:

- `ui_users` remains the web account source.
- Add self-registration flow for role `user`.
- Enforce password policy.
- Add audit event for user self-registration.
- Ensure user account can later link to `RegistryPerson` via `RegistryPersonIdentity`.

Do not:

- Store profile fields directly in `ui_users` except minimal display/account metadata if already needed.
- Treat login as full person profile.

### Profile/person domain

Required profile fields:

- `full_name` / ФИО.
- `display_name` if needed, generated by default from ФИО.
- `department_id`.
- `location_id` or location request if not found.
- `phone` or internal extension.
- `position` / должность — recommended production field.

Recommended additional fields:

- manager/responsible person.
- room/workplace label.
- preferred contact method.
- schedule/availability if needed later.
- used services/systems if useful for forms and KB.

Registry writes:

- Profile updates must update `RegistryPerson` and `RegistryPersonIdentity`.
- Department/location must be selected from registry where policy says existing values are required.
- User-submitted new department/location should become a pending registry suggestion, not an uncontrolled canonical value.

### Device link domain

Continue using:

- `device_browser_pairings` for short-lived browser handoff.
- `device_registration_claims` for requested link.
- `device_user_bindings` for approved active link.

Required states visible to users:

- `Не привязано`.
- `Ожидает заполнения профиля`.
- `Ожидает подтверждения администратора`.
- `Привязано`.
- `Отклонено`.
- `Конфликт: устройство уже привязано`.

### Profile schema domain

Do not build unrestricted registry constructor.

Build controlled profile schema:

- system fields cannot be removed;
- admin may mark optional fields visible/hidden/required;
- admin may add custom fields in a dedicated extra block;
- each custom field must have type, label, help text, validation and data target;
- every field must map to one of:
  - registry person field;
  - identity field;
  - department/location relationship;
  - custom registry metadata;
  - pending change request.

---

## Form builder integration target

Existing request form builder supports useful field types: `user_picker`, `department_picker`, `location_picker`, `device_picker`, `service_picker`, plus standard text/select/date/file/email/phone fields.

Target rule:

- Reuse the form schema engine concepts.
- Do not store profile forms inside the request form pack as if they were ticket forms.
- Introduce separate schema domains:
  - `request_form_schema` for ticket/request templates;
  - `profile_form_schema` for user profile completion;
  - `registry_attribute_schema` for controlled custom attributes;
  - `consent_form_schema` if consent payloads become configurable.

Request forms must consume profile context:

- Prefill requester department, location, phone and device.
- Offer device picker based on active bindings.
- Offer service picker based on service catalog and audience/context.
- Allow profile-context conditions in a safe limited form:
  - requester has no linked device;
  - requester department equals X;
  - selected device type is printer/MFU/PC;
  - selected service/offering equals X.

Field roles must remain the main production mapping:

- `routing_field`.
- `priority_impact`.
- `priority_urgency`.
- `priority_importance`.
- `diagnostic_input`.
- `approval_subject`.
- `closure_evidence`.
- `reporting_dimension`.
- `passport_fact`.
- `visibility_public`.
- `display_only`.

Acceptance:

- Admin can understand which profile/registry values each form uses.
- Request form preview shows resolved requester context.
- Ticket creation stores a stable requester/profile context snapshot.

---

## Knowledge integration target

Knowledge access must be registry-aware and requester-safe.

Rules:

- Knowledge audience rules may target person, department, department tree, location, access group, audience group, role and service.
- Requester search must resolve actor -> person -> department/location/groups/services before filtering.
- RAG retrieval must use the same access decision as normal search.
- Knowledge suggestions in ticket creation must include service/request-template/profile/device context.
- Denials must be safe: no leaking private article titles or inaccessible spaces.

Required UX:

- In profile setup: show why profile completion improves knowledge recommendations.
- In request creation: show recommended articles before ticket submit.
- In support workspace: show what KB was shown/tried by requester.
- In admin knowledge access explain: show audience match in Russian.

Acceptance:

- User from department A cannot see department B restricted content.
- Support/admin can explain why a user sees or does not see an article.
- RAG never returns inaccessible content.

---

## Phase R0 — Baseline inventory and regression lock

Status: completed on 2026-06-15. R0 baseline inventory and regression lock are closed. One R0 corrective contract fix was made before product work: requester/public ticket detail now preserves only requester-safe request-form `custom_fields` while hiding internal policy snapshots. Product implementation remains gated by the R1 decisions below, but the R0 blockers are resolved.

Tasks:

1. Build a current registration map from code and docs.
2. Freeze baseline tests for current behavior before refactor.
3. Identify all GUI strings and components related to registration/profile.
4. Identify all endpoints that submit or mutate registration/profile/account sessions.
5. Identify all requester profile APIs and current read-only limitations.
6. Identify current form builder and knowledge access integration points.

Files/areas to inspect:

- `server/registry/registration_service.py`
- `server/registry/account_session_service.py`
- `server/registry/browser_pairing_service.py`
- `server/registry/account_state_service.py`
- `server/web_api/registry_handlers.py`
- `server/web_api/requester_handlers.py`
- `server/requester/identity_service.py`
- `server/tickets/form_catalog.py`
- `server/tickets/create_flow.py`
- `server/knowledge/access_service.py`
- `server/knowledge/audience_rules_service.py`
- `webapp/src/pages/device-pairing/*`
- `webapp/src/pages/requester/*`
- `webapp/src/features/auth/*`
- `pc_agent/ui_gui/account_gate.py`
- `pc_agent/ui_gui/main_window.py`
- `pc_agent/ui_gui/server_api.py`
- `pc_agent/core/account_session.py`

Tests:

- Run all existing registration/account-session/browser-pairing tests.
- Run existing requester workspace tests.
- Run existing form pack tests.
- Run existing knowledge access/audience tests.
- Record failing tests before changes.

Live evidence:

- Screenshot current agent account gate.
- Screenshot current `/app/device/pair`.
- Screenshot current `/app/device/register`.
- Screenshot current requester profile.
- Screenshot current admin registry registration list.

Acceptance:

- Baseline is documented in this file or linked evidence folder.
- No implementation starts until current behavior is understood.

R0 baseline checkpoint, 2026-06-15:

- Scope classification: cross-cutting baseline only. No behavior/code implementation started.
- Context commands run: `python scripts/task_intake.py --task "PLANS R0 web-first registration baseline inventory and regression lock"`, `python scripts/diff_context.py`, `python scripts/build_context_index.py --force`, `python scripts/build_context_pack.py --topic "web-first registration profile requester device pairing baseline R0"`, and focused `python scripts/search_context_index.py ...` queries for registration, requester, forms and knowledge.
- Current route map: there is no `/app/register` route in `webapp/src/app/router.tsx`; current web device routes are `/app/device/pair`, `/app/device/login` and `/app/device/register`. Requester cabinet routes are `/app/requester` and `/app/requester/:section`, guarded by `WorkspaceAccessGate`.
- Current mutating registration/session endpoints include legacy/agent profile submission through `/api/registry/profile` and `/api/registry/agent/profile`, agent `account-state`, account-session create/validate/logout, browser pairing create/poll, other-account login requests, web pairing lookup/login/registration confirm, and admin registration approve/reject/account-session operations.
- Current requester APIs are mostly read/workspace actions: `GET /api/web/requester/profile`, `GET /devices`, ticket list/detail, ticket create/preview/claim/message/close/feedback/reopen and consents. Profile detail currently exposes `profile_policy.editable=false` in frontend tests; no web-first profile setup/update flow is present yet.
- Current GUI agent still exposes both browser registration and legacy registration: `pc_agent/ui_gui/account_gate.py` has `browser_register_button` and `register_button`; `pc_agent/ui_gui/main_window.py` still builds a full registration form with full name/login/email/phone/department/location/relationship fields and submits through `submit_registration_profile()`.
- Current form integration points: `server/tickets/form_catalog.py` validates/submits legacy packs and request-template computed snapshots; `server/tickets/create_flow.py` stores requester account/profile context, supports authenticated requester create and no-device requester create via the web wrapper.
- Current knowledge integration points: `server/knowledge/access_service.py` and `server/knowledge/audience_rules_service.py` already evaluate person/department/department tree/location/access group/audience group/role/service audience facts; requester search/retrieval/suggestions use those services before projection.

R0 automated baseline results:

- `python -m pytest pc_agent/tests/test_account_gate.py pc_agent/tests/test_account_session_manager.py pc_agent/tests/test_registration_status.py -q` -> 43 passed.
- `pnpm --dir webapp exec vitest run src/pages/device-pairing/device-pairing-page.test.tsx src/pages/requester/index.test.tsx src/features/auth/session-provider.test.tsx src/features/requester/api.test.ts --reporter=dot` -> 4 files / 32 tests passed.
- Registration/account-session/browser-pairing backend split runs all passed sequentially with explicit shared-test-DB fallback (`PC_CLIENT_ALLOW_SHARED_TEST_DB=1`) after isolated DB pytest setup timed out in this Windows environment:
  - `server/tests/test_browser_pairing_service.py` -> 6 passed.
  - `server/tests/test_account_session_service.py` -> 16 passed.
  - `server/tests/test_device_registration_service.py` -> 16 passed.
  - `server/tests/test_registry_registration_policy.py` -> 2 passed.
  - `server/tests/test_registration_api.py` -> 32 passed.
- Combined registration backend run timed out at 5 minutes, but the same files passed when split. Record this as a runtime-size baseline, not a product failure.
- Initial requester/form/service-catalog baseline found one real contract regression: `server/tests/test_ticket_form_packs.py::test_create_ticket_stores_legacy_form_source_and_computed_snapshot` failed because requester-safe `GET /api/tickets/{ticket_id}` no longer included safe request-form `custom_fields` while hiding `request_template`.
- Corrective fix: `server/tickets/visibility_policy.py` now projects only requester-safe request-form `custom_fields` (`request_form`, `request_form_key`, `request_form_title`, `request_form_data`, `request_form_summary` and resolver metadata) and still hides `request_template`, `priority_decision`, `routing_decision`, `public_access` and related internals. Regression coverage was added in `server/tests/test_ticket_visibility_policy.py::test_requester_visibility_keeps_safe_request_form_custom_fields_without_internal_snapshot`.
- Final requester/form/service-catalog sequential baseline with shared-test-DB fallback: `python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_ticket_form_packs.py server/tests/test_ticket_create_service_catalog.py -q` -> 58 passed.
- Visibility-policy focused verification: `python -m pytest server/tests/test_ticket_visibility_policy.py -q` -> 4 passed.
- Knowledge audience/access baseline with shared-test-DB fallback: `python -m pytest server/tests/test_knowledge_access_service.py server/tests/test_knowledge_audience_rules.py server/tests/test_knowledge_suggestions.py server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_rag_policy.py -q` -> 28 passed.
- A parallel shared-DB attempt for requester/form and knowledge tests produced deadlock/connection-closed cleanup errors; do not treat that as application baseline. DB-backed R0 pytest groups must run sequentially.

R0 live evidence:

- Remote stand deployed from `cc22879f` with `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls`; webapp build passed and `/api/health` smoke passed on attempt 2.
- Evidence folder: `artifacts/browser_live_validation/web-first-registration-r0-cc22879f-20260615/`.
- Captured browser evidence:
  - `device-pair.md` / `device-pair.png`: current manual pairing code page.
  - `device-register-no-pairing.md` / `device-register-no-pairing.png`: current `/app/device/register` without pairing id shows a safe error, but message still includes raw `pairing_id`.
  - `requester-profile.md` / `requester-profile.png`: `/app/requester/profile` under current admin web session shows requester shell plus `Insufficient permissions` in English; console recorded failed requester bootstrap/tickets resource loads.
  - `admin-registry.md` / `admin-registry.png`: admin registry overview shows registrations/account-session/data-quality summary.
  - `admin-registry-requests.md` / `admin-registry-requests.png`: admin `requests` tab shows registration diff, current binding, declared identity, pending/approved states and admin override controls.
- Previous packaged-agent UIA screenshot capture timed out, but controlled isolated source-agent evidence is now complete:
  - `agent-account-gate-controlled-noscreenshot.json`: PID-scoped UIA probe found auth/account gate.
  - `agent-account-gate-controlled.json` / `agent-account-gate-controlled.png`: screenshot probe captured the Russian account-gate message asking the user to wait for administrator authorization, with manual-token and cancel actions.
  - The temporary agent instance `web-first-r0-agent-20260615` was stopped after evidence capture. No token was issued; remote `control` status was stopped and `manage_remote_stack.py smoke server` failed, so this is account-gate evidence only.

R0 blockers resolved before implementation:

1. Requester-safe custom-field projection contract fixed and covered by regression test.
2. Fresh controlled agent account-gate screenshot captured under `artifacts/browser_live_validation/web-first-registration-r0-cc22879f-20260615/`.
3. `python scripts/verify_workspace.py` rerun after code/docs updates -> passed.
4. Remaining R0 caveat: isolated DB pytest setup timed out in this environment, so DB-backed R0 baseline evidence used the project-approved shared-test-DB fallback sequentially. This is not a substitute for a later full DB/API gate.

---

## Phase R1 — Product vocabulary, routes and UX contract

Status: completed on 2026-06-15 for the contract slice. The canonical route/copy/error decisions live in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`; the existing device-link route now follows the R1 safe-copy rule for missing device-link ids and backend status values.

Tasks:

1. Define canonical Russian labels:
   - `Аккаунт` = вход в систему;
   - `Профиль` = данные человека;
   - `Устройство` = ПК/agent machine;
   - `Привязка устройства` = связь пользователя и устройства;
   - `Кабинет пользователя` = requester workspace;
   - `Заявка на привязку` = pending device link request.
2. Add UX copy guidelines for registration/profile/device linking.
3. Ensure every flow has clear empty/error/success/pending states.
4. Define target routes:
   - `/app/register`;
   - `/app/requester/profile/setup`;
   - `/app/requester/profile`;
   - `/app/requester/devices`;
   - `/app/device/pair`;
   - `/app/device/login`;
   - `/app/device/register` as transitional route or redirect to device pair flow.
5. Define user-facing error dictionary in Russian.

Acceptance:

- No UI says `pairing`, `binding`, `claim`, `session`, `registry person` to normal users.
- Technical ids are hidden unless in admin/debug surfaces.
- User always knows the next action.

R1 completion checkpoint, 2026-06-15:

- Added `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md` with canonical user terms, target routes, status labels, error dictionary and the eight rollout decisions.
- Updated `docs/QUICK_LOOKUP.md` and `scripts/navigation_catalog.py` so web-first registration/profile/device-link work routes to the new contract.
- Updated `webapp/src/pages/device-pairing/index.tsx` so `/app/device/register` without a device-link id shows `Откройте эту страницу из агента или введите код подключения.` instead of raw `pairing_id`, and registration/device-link statuses render Russian product labels instead of backend enums.
- Added focused frontend coverage in `webapp/src/pages/device-pairing/device-pairing-page.test.tsx` for missing device-link id and `pending_admin_review` status.
- Browser evidence: local Playwright/Chromium validation with stubbed `/api/web/session/me` captured `/app/device/register` missing-link safe error at `artifacts/browser_live_validation/web-first-registration-r1-20260615/device-register-missing-link-safe-error.png` and report JSON at `artifacts/browser_live_validation/web-first-registration-r1-20260615/device-register-missing-link-safe-error.json`. Remote stand was not deployed for R1 because current workspace contains unrelated dirty files; remote `server` and `control` were stopped.
- Verification: `pnpm --dir webapp exec vitest run src/pages/device-pairing/device-pairing-page.test.tsx --reporter=dot` -> 7 passed.

---

## Phase R2 — Web account self-registration

Status: completed on 2026-06-15. R2 account-only self-registration is implemented behind `WEB_SELF_REGISTRATION_ENABLED`, with `/app/register`, `POST /api/web/session/register`, no auto-login/cookie issuance, role `user`, password/repeat/duplicate validation, optional device-link code validation without active binding creation, and login success redirect copy.

Tasks:

1. Add `/app/register` page.
2. Add backend endpoint for user self-registration.
3. Form fields:
   - `Логин`;
   - `Пароль`;
   - `Повторите пароль`;
   - optional `Код привязки устройства`.
4. Enforce password policy.
5. Prevent duplicate login.
6. Auto-login after registration only if secure and consistent with existing session model; otherwise redirect to login with success message.
7. Do not require profile data during account creation.
8. If pairing code is supplied, validate it but do not create active binding before profile completion.

Tests:

- Unit: password validation, duplicate login, invalid repeat password.
- API: create user with role `user`; no admin role escalation.
- API: optional pairing code accepted/rejected correctly.
- Frontend: form validation and Russian errors.

Live evidence:

- Browser: successful account registration.
- Browser: duplicate login error.
- Browser: invalid password/repeat password error.
- DB/API: created user has role `user` and no full profile fields in account row.

Acceptance:

- Account creation is simple and separate from profile.
- Optional device code does not bypass profile/admin policy.

R2 completion checkpoint, 2026-06-15:

- Backend: `server/config.py` defines fail-closed `WEB_SELF_REGISTRATION_ENABLED`; `server/web_api/session_handlers.py` handles `POST /api/web/session/register`; `server/web_api/dto/session.py` defines strict registration DTOs; `server/routes.py` registers the route; `server/auth/middleware.py` whitelists the anonymous route so the feature flag, not auth middleware, controls availability.
- Frontend: `webapp/src/features/auth/register-page.tsx` implements account-only fields (`Логин`, `Пароль`, `Повторите пароль`, optional `Код привязки устройства`); `webapp/src/features/auth/api.ts` posts the typed request; `webapp/src/features/auth/login-page.tsx` shows the `/app/login?registered=1` success notice; `webapp/src/app/router.tsx` exposes `/app/register`.
- Browser evidence: local Vite + Playwright Browser validation captured success, duplicate-login and repeat-password states at `artifacts/browser_live_validation/web-first-registration-r2-20260615/account-registration-success.png`, `account-registration-duplicate.png`, `account-registration-password-repeat.png`, with redacted report `account-registration-browser-report.json`. The browser report confirms optional `device_link_code` is sent on success, repeat-password mismatch sends no registration request, and no forbidden profile fields are rendered.
- Verification: `python -m pytest server/tests/test_web_session_api.py -q` -> 28 passed; `pnpm --dir webapp exec vitest run src/features/auth/register-page.test.tsx src/pages/device-pairing/device-pairing-page.test.tsx --reporter=dot` -> 10 passed; `pnpm --dir webapp run build` -> passed; `python -m pytest scripts/test_navigation_catalog.py scripts/test_docs_drift_check.py -q` -> 14 passed; `python scripts/verify_workspace.py` -> passed.
- Caveat: R2 browser validation used intercepted local API responses rather than remote stand deployment because the workspace still contains unrelated dirty files and remote deployment is reserved for later release/live-gate phases.

---

## Phase R3 — Web profile setup gate

Status: completed on 2026-06-15. R3 profile setup gate is implemented for the web requester cabinet: bootstrap returns `profile_completion`, `/app/requester/profile/setup` and `/app/requester/profile` render the registry-backed setup form, `PUT /api/web/requester/profile` updates only the authenticated caller's `RegistryPerson` and verified `ui_login` identity, department/location values must come from registry pickers, and normal requester ticket preview/create is blocked with `REQUESTER_PROFILE_INCOMPLETE` until the required profile fields are complete. Local browser evidence is under `artifacts/browser_live_validation/web-first-registration-r3-20260615/`; full real-stand admin registry confirmation remains part of R14 live validation.

Tasks:

1. Build profile completion status in requester bootstrap.
2. Redirect or gate normal requester actions when required profile fields are missing.
3. Add `/app/requester/profile/setup`.
4. Add profile edit/update endpoint for the authenticated user.
5. Required fields:
   - ФИО;
   - подразделение;
   - локация;
   - телефон/internal extension.
6. Recommended fields:
   - должность;
   - кабинет/workplace label;
   - preferred contact method.
7. All department/location selection must use registry pickers.
8. If department/location does not exist, submit a pending registry suggestion/change request according to policy.
9. Store profile changes as registry updates or auditable profile change requests.

Tests:

- API: requester can update own profile only.
- API: requester cannot update someone else’s person_id.
- API: required profile fields enforced.
- API: invalid department/location rejected or turned into pending suggestion based on policy.
- Frontend: setup gate blocks create-ticket until profile complete.
- Frontend: profile complete state unlocks requester workspace.

Live evidence:

- New user sees profile setup gate.
- User completes profile with department/location pickers.
- User reaches requester home after completion.
- Admin registry shows created/updated person and identities.

R3 evidence recorded:

- `artifacts/browser_live_validation/web-first-registration-r3-20260615/profile-setup-required.png`
- `artifacts/browser_live_validation/web-first-registration-r3-20260615/profile-setup-saved.png`
- `artifacts/browser_live_validation/web-first-registration-r3-20260615/profile-setup-browser-report.json`
- Backend tests verify registry person and `ui_login` identity writes for the created/updated profile.

Acceptance:

- Profile is understandable and fully Russian.
- Profile writes to registry-backed structures.
- No arbitrary free-text department/location becomes canonical without policy.

---

## Phase R4 — Web-first device linking

Status: implementation completed on 2026-06-15 for the backend/frontend contract slice. Local browser evidence covers manual code entry, direct `pairing_id` preview, safe device facts and pending admin-review state in `/app/requester/devices`; full connected-agent/admin approval evidence remains part of R14 LV2.

Tasks:

1. Add `Мои устройства` section in requester cabinet if missing or incomplete.
2. Add `Привязать устройство` flow.
3. Reuse browser pairing lookup by code.
4. Support direct link from agent and manual code entry.
5. Show device details before confirmation:
   - hostname;
   - OS;
   - agent version;
   - current status;
   - expiry.
6. On confirmation, create registration claim connected to the current profile/person.
7. Show pending/approved/rejected/conflict status in web cabinet.
8. If profile is incomplete, redirect to profile setup before creating claim.

Tests:

- API: code lookup rate limit and expired code.
- API: authenticated user can confirm device pairing only for pending pairing.
- API: profile incomplete blocks final device link claim.
- API: approved claim creates active binding.
- Frontend: direct pairing link and manual code flow.
- Frontend: pending/rejected/conflict UI states.

Live evidence:

- Agent generates pairing code.
- User enters code in web cabinet.
- Pending claim appears in admin registry.
- Admin approves claim.
- User sees linked device in web.
- Agent sees updated account-state.

Acceptance:

- User can link device without typing profile in agent.
- Device linking has clear status and next action.

Implementation notes, 2026-06-15:

- `/app/requester/devices` now supports manual device-link code lookup and direct `pairing_id` preview through the existing browser-pairing APIs.
- `registration/confirm` returns `REQUESTER_PROFILE_INCOMPLETE` before claim creation when the web requester profile is incomplete.
- Successful registration confirmation builds the claim profile snapshot from the resolved `RegistryPerson`, not browser-submitted profile fields.
- `/app/device/register` redirects incomplete-profile confirmation to `/app/requester/profile/setup`.
- R4 evidence is under `artifacts/browser_live_validation/web-first-registration-r4-20260615/`.

Verification, 2026-06-15:

- `python -m pytest server/tests/test_registration_api.py -q --tb=short` -> 33 passed.
- `python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short` -> 20 passed.
- `pnpm --dir webapp exec vitest run src/pages/device-pairing/device-pairing-page.test.tsx src/pages/requester/index.test.tsx --reporter=dot` -> 22 passed.
- `pnpm --dir webapp run build` -> passed with existing Vite chunk-size warning.
- Browser evidence report `device-link-browser-report.json` recorded 0 console errors, 0 page errors and 0 unhandled mocked API routes.

---

## Phase R5 — Remove profile registration from GUI agent

Status: completed on 2026-06-15; tightened on 2026-06-16. Normal GUI agent registration is browser-first only; the legacy full-profile registration/confirm page and local form handlers are removed from the normal agent GUI. Backend legacy endpoints remain as compatibility surface for older deployed agents.

Tasks:

1. Hide/disable legacy `Регистрация` button in agent account gate.
2. Remove normal access to full registration form from agent navigation.
3. Remove profile fields from agent UI:
   - ФИО;
   - login;
   - email;
   - phone;
   - department/location;
   - relationship type.
4. Keep only device handoff actions:
   - `Привязать через браузер`;
   - `Скопировать код привязки`;
   - `Открыть кабинет`;
   - `Проверить статус`.
5. Preserve emergency ticket and consent/remote-assist flows.
6. Ensure old backend endpoints remain temporarily for compatibility but are no longer reachable from normal GUI.
7. Legacy GUI re-enable is not part of the normal rollout. Compatibility stays server/API-side for old agents only.

Tests:

- Unit/UI: account gate no longer exposes full registration button by default.
- Unit/UI: browser linking still works.
- Unit/UI: emergency ticket remains available.
- Regression: account-state pending/approved/rejected rendering still works.
- Static check: no normal GUI label contains old registration form prompts.

Live evidence:

- Screenshot agent unlinked state: only browser link/code/status actions.
- Screenshot agent linked state: owner card + open cabinet + emergency ticket.
- Screenshot no legacy profile form visible.

Acceptance:

- Agent GUI is no longer a profile editor.
- Agent remains useful as local status/handoff tool.

Implementation, 2026-06-15:

- `pc_agent/ui_gui/account_gate.py` no longer exposes local registration or pending-confirm actions, keeps browser device handoff as the only registration action, and exposes a copyable browser pairing code after handoff creation. `pc_agent/ui_gui/main_window.py` no longer builds `default_agent_registration_form()` or the legacy registration entry page.
- `pc_agent/ui_gui/main_window.py` no longer builds or enters the full registration form in the normal path; accidental registration view names redirect to the account gate/browser handoff. There is no disabled legacy registration page in the normal GUI stack.
- Existing backend registration endpoints remain unchanged for compatibility.
- Documentation/catalog routing was updated in `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md` and `scripts/navigation_catalog.py`.
- R5 visual evidence is under `artifacts/browser_live_validation/web-first-registration-r5-20260615-windows/`.

Verification, 2026-06-15:

- `python -m pytest pc_agent/tests/test_account_gate.py pc_agent/tests/test_main_window_runtime_windows.py -q --tb=short` -> 34 passed.
- `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q --tb=short` -> 13 passed.
- `python -m pytest scripts/test_navigation_catalog.py scripts/test_docs_drift_check.py -q` -> 14 passed.
- `python scripts/verify_workspace.py` -> passed.
- Qt Windows-platform screenshots captured unlinked, pending and linked account-gate states; no default legacy full-profile registration button/form is visible.

---

## Phase R6 — Profile schema and controlled registry attributes

Status: completed on 2026-06-15. R6 profile schema is implemented as controlled admin configuration, not as a free-form registry constructor. The requester profile flow now uses the active schema for visible optional fields, required controlled custom fields and completion gating.

Tasks:

1. Add profile schema model or configuration service.
2. Distinguish system fields and configurable fields.
3. System fields cannot be deleted:
   - ФИО;
   - login identity;
   - department;
   - location;
   - phone;
   - active device links.
4. Admin may configure optional fields:
   - visible/hidden;
   - required/optional;
   - help text;
   - validation;
   - registry target.
5. Admin may add custom fields only in a controlled block.
6. Every custom field must have a storage target and audit behavior.
7. Add profile schema preview for admin and requester.

Tests:

- API: cannot delete system fields.
- API: invalid schema rejected.
- API: required custom field enforced.
- Frontend: admin schema editor shows safe explanations.
- Frontend: requester form renders schema correctly.

Live evidence:

- Admin configures a profile field as required.
- New user must fill it.
- Admin disables optional field and it disappears from setup.

Acceptance:

- This is not an unrestricted registry constructor.
- Admins can adapt profile forms without breaking core identity/binding logic.

Implementation, 2026-06-15:

- `server/registry/profile_schema_service.py` adds `RequesterProfileSchemaService` over `registry_admin_policies(policy_key=requester_profile_schema)` and `registry_admin_events`, so no database migration was required.
- Admin APIs expose `GET|PUT /api/web/admin/registry/profile-schema` and `POST /api/web/admin/registry/profile-schema/preview`.
- System fields are protected; optional built-ins can be hidden/required; custom fields are restricted to `registry_people.metadata_json.profile_custom_fields.<key>` with `profile_custom_field_change` audit behavior.
- Requester bootstrap/profile responses return a safe schema projection with no storage targets, raw registry targets or `metadata_json` internals.
- Requester profile update accepts `custom_fields`, stores controlled custom values under `RegistryPerson.metadata_json.profile_custom_fields`, and schema-aware profile completion blocks tickets/device confirmation while required custom values are missing.
- React admin registry adds the profile schema tab; React requester setup renders schema custom fields and hides optional built-ins when the schema marks them invisible.

Verification, 2026-06-15:

- `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot` -> 22 passed.
- `pnpm --dir webapp run build` -> passed with the existing Vite large chunk warning.
- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short` -> 23 passed.
- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registration_api.py -q --tb=short` -> 33 passed.
- Local Playwright browser fallback evidence is in `artifacts/browser_live_validation/web-first-registration-r6-20260615/`: report shows no console/network errors, no horizontal scroll at 1366/1920, hidden `position`, saved `cost_center` custom field, and requester save payload under `custom_fields`.

---

## Phase R7 — Registry extension for production context

Status: completed on 2026-06-15. R7 extends the existing lightweight registry context without a database migration: the admin snapshot now projects production context from existing registry rows and controlled `metadata_json`, the admin person editor can update focused work-context fields, and data quality reports flag missing production context that affects routing/support diagnostics.

Tasks:

1. Review current registry entities and identify missing production context.
2. Add only context that is used by forms, knowledge, routing, reporting or support diagnostics.
3. Recommended production entities/attributes:
   - Person: position, phone, internal extension, manager/responsible.
   - Department: hierarchy, code, status.
   - Location: building, floor, room, office/workplace label.
   - Device/Asset: type, owner/responsible, department, location, peripheral links.
   - Peripheral: printer/MFU/scanner/monitor where needed.
   - Service/System: owner, audience, criticality.
   - Access/Audience groups: controlled membership.
4. Add data quality checks:
   - person without department;
   - person without location;
   - user account without person;
   - device without active owner/responsible;
   - duplicate identities;
   - pending department/location suggestions.

Tests:

- Registry repo/service tests for new attributes.
- Admin API tests for updates and validation.
- Data quality tests.
- Import/export tests if touched.

Live evidence:

- Admin registry shows person + department + location + device context.
- Data quality dashboard flags incomplete profiles/devices.

Acceptance:

- Registry is strong enough for context, not bloated into a generic database builder.

Implementation:

- `server/registry/service.py` projects person `position`, `workplace_label`, `internal_extension`, `manager_person_id`, manager display name and `production_context` from `RegistryPerson.metadata_json`, plus department manager, service owner/criticality/audience and asset responsible-person context from existing registry rows.
- `server/web_api/registry_handlers.py` accepts and audits controlled admin person metadata updates for `position`, `workplace_label`, `internal_extension` and `manager_person_id`.
- Data-quality generation now includes `person_missing_department`, `person_missing_location`, `asset_missing_owner_or_responsible` and `department_pending_confirmation` so incomplete profiles/devices/departments surface in the admin registry quality queue.
- `/app/admin/registry` shows compact person work context in the People tab and edits the controlled production fields through the person edit dialog.

Verification:

- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registry_registration_snapshot.py server/tests/test_registry_quality_remediation.py server/tests/test_registry_web_api.py -q --tb=short` -> 17 passed.
- `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` -> 10 passed.
- `python -m py_compile server\registry\service.py server\web_api\registry_handlers.py` -> passed.
- `pnpm --dir webapp run build` -> passed with the existing Vite large chunk warning.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r7-20260615/`: mocked admin registry payload verified person context rendering, edit-dialog submit payload, R7 quality issue labels, no body horizontal scroll at 1366/1920, and no console/network errors. Full real-stand admin confirmation remains part of R14 live validation.

---

## Phase R8 — Request forms consume profile and registry context

Status: completed on 2026-06-15. R8 connects requester request forms to the resolved registry-backed requester context: preview/create recompute context server-side from the authenticated web session, completed `RegistryPerson` and active binding, forms are prefilled from profile/device facts, registry-backed pickers include department/location/device options, ticket custom fields store a stable `requester_context_snapshot` plus routing aliases, and preview explains the resolved requester/form context.

Tasks:

1. Add requester context resolver for form rendering.
2. Prefill request forms from profile/device context.
3. Add safe profile-context conditions.
4. Add device picker based on active bindings.
5. Add registry-backed pickers for service/device/department/location where relevant.
6. Add ticket create `requester_context_snapshot` or equivalent stable snapshot.
7. Ensure routing/priority/SLA/diagnostic policies can use resolved context.
8. Add preview endpoint output that explains resolved profile and form context.

Tests:

- Form schema validation still passes.
- Ticket create with completed profile stores profile context snapshot.
- Ticket create without profile is blocked or allowed according to policy.
- Routing can use department/location/device context.
- Frontend prefill works and can be edited only where allowed.

Live evidence:

- User opens request form and sees prefilled department/location/device.
- User creates ticket; support detail shows requester context.
- Route preview shows why ticket went to queue.

Acceptance:

- Users do not repeatedly type cabinet/department/phone.
- Support receives accurate context with every ticket.

Implementation:

- `server/requester/identity_service.py` now builds requester context v1 with safe profile, device, form prefill, routing facts, requester-safe preview projection and stable custom-field aliases.
- `server/web_api/requester_handlers.py` uses that resolver for preview/create, ignores client-supplied requester context as authority, stores `requester_context_snapshot`, exposes alias fields such as `requester_department_id`, `requester_location_id`, `requester_device_id`, `requester_asset_id` and lets routing policies match resolved context.
- `webapp/src/pages/requester/index.tsx` merges context prefill into untouched request-form fields, renders registry-backed picker options for department/location/device/service/user picker field types, shows a requester context summary in the form and renders preview context explanation.

Verification:

- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short` -> 23 passed.
- `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx --reporter=dot` -> 14 passed.
- `python -m py_compile server\requester\identity_service.py server\web_api\requester_handlers.py` -> passed.
- `pnpm --dir webapp run build` -> passed with the existing Vite large chunk warning.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r8-20260615/`: mocked requester cabinet verified visible requester context, department/device picker prefill, preview context explanation, preview/create payloads with prefilled department/device ids, no body horizontal scroll at 1366/1920, and no console/network errors.

---

## Phase R9 — Knowledge access and recommendations from registry context

Status: completed on 2026-06-15. R9 uses the existing Registry Visibility Foundation for actor -> person -> effective-audience enforcement across search, suggestions, requester portal, Ask/RAG and support ticket knowledge suggestions, and adds the R8 requester/form/device context as safe pre-submit suggestion signals. Ticket create continues to persist safe `knowledge_attempts` for support visibility.

Tasks:

1. Ensure requester knowledge search resolves actor -> person -> audience.
2. Use department/location/groups/service context in knowledge filtering.
3. Ensure RAG retrieval uses the same audience decision as search.
4. Add pre-submit knowledge recommendations based on request form + profile + device/service context.
5. Store knowledge attempts in ticket context.
6. Add admin explain UI in Russian:
   - why visible;
   - why hidden;
   - which audience rule matched.

Tests:

- Department-restricted article visible only to matching department.
- Location-restricted article visible only to matching location.
- Service-restricted article appears only in matching service context.
- RAG does not retrieve inaccessible content.
- Ticket creation records knowledge attempts.

Live evidence:

- Two users from different departments see different KB results.
- Ask/RAG result respects audience restrictions.
- Ticket detail shows which KB was suggested/tried.

Acceptance:

- Knowledge is personalized by registry context without leaking restricted content.

R9 completion checkpoint, 2026-06-15:

- `server/knowledge/suggestion_service.py` now builds ordered candidate queries from explicit request text plus safe values in `form_payload`, `requester_context` and `device_metadata`, while skipping raw ids, token/secret/session fields, email/phone and other sensitive identifiers. Each candidate search still passes through `KnowledgeSearchService.search(..., effective_audience=...)`, so Registry audience rules remain the enforcement layer before projection.
- `/app/requester` sends the server-owned R8 requester context and selected safe device metadata to `/api/knowledge/suggest`, refreshes suggestions when the selected device changes, and stores viewed/not-helpful knowledge attempts in the ticket create payload.
- Existing `EffectiveIdentityService`, `KnowledgeAccessService`, `KnowledgeAudienceRulesService`, binding-surface aliases and Ask/RAG retrieval tests cover department/location/groups/service audience enforcement and keep `requester_portal` mapped to canonical `requester_pre_submit`.

R9 verification:

- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_suggestions.py -q --tb=short` -> 7 passed.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_api.py::test_public_suggestions_apply_registry_audience_rules_before_projection server/tests/test_knowledge_api.py::test_public_search_applies_registry_audience_rules_before_projection -q --tb=short` -> 2 passed.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short` -> 23 passed.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ask.py::test_public_knowledge_ask_applies_audience_rules_before_vector_retrieval_projection server/tests/test_knowledge_hybrid_retrieval.py::test_hybrid_retrieval_filters_disabled_rag_policy_before_citations server/tests/test_knowledge_hybrid_retrieval.py::test_hybrid_retrieval_requires_ai_rag_binding_surface -q --tb=short` -> 3 passed.
- `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx --reporter=dot` -> 14 passed.
- `python -m py_compile server\knowledge\suggestion_service.py` -> passed.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r9-20260615/`: the mocked requester cabinet verified requester-context/device-metadata suggestion input, feedback recording, persisted `knowledge_attempts`, prefilled department/device ids, no console/network errors and no horizontal overflow at 1366/1920.

---

## Phase R10 — Admin registry and moderation workflow

Status: completed on 2026-06-15. R10 admin moderation is covered by the existing registry management center plus an explicit schema-aware requester profile-completion projection in the admin People tab. Admins can review pending device-link claims, person/UI-account identity links, duplicate people, department/location suggestions, device transfer previews, account-session revoke effects and timeline audit without raw JSON workflows.

Tasks:

1. Improve admin registry pages for:
   - pending device links;
   - profile completion status;
   - people/account/person identity links;
   - duplicate person/identity resolution;
   - department/location suggestions;
   - device ownership transfer.
2. Add clear Russian action labels:
   - `Подтвердить привязку`;
   - `Отклонить`;
   - `Передать устройство другому пользователю`;
   - `Оставить прежнего пользователя как общего`;
   - `Отозвать привязку`.
3. Admin should see destructive action preview before transfer/revoke.
4. Add audit timeline for profile/device/account changes.

Tests:

- Admin approve/reject link claim.
- Admin transfer owner preview/commit.
- Admin rejects conflicting claim with clear reason.
- Admin links ui-user to registry person.
- Audit events are written.

Live evidence:

- Pending link claim approved from admin UI.
- Transfer owner preview shows sessions/bindings affected.
- User/device state changes are visible in requester cabinet.

Acceptance:

- Admin can manage registry state without raw JSON or unsafe hidden side effects.

R10 completion checkpoint, 2026-06-15:

- `server/registry/service.py` now projects `people[].profile_completion` from the active requester profile schema, using the same completion rules as requester bootstrap. Admin rows expose only status and missing field labels, not requester-only storage internals.
- `webapp/src/features/admin/registry/registry-people-tab.tsx` renders the profile-completion state in Russian (`Профиль заполнен`, `Нужно заполнить профиль`) and lists missing profile fields compactly for moderation.
- Existing admin registry workflows already cover pending device-link approval/rejection, transfer-owner preview/commit, UI-user to person links, people merge preview/apply, account-session revoke, policy/quality suggestions and the timeline drawer for `device`, `person`, `binding`, `account_session` and `claim`.
- Dangerous operations keep the preview/apply pattern with required reason and audited events; transfer, merge, bulk and import previews remain read-only and the UI requires preview before apply.

R10 verification:

- Red backend TDD: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_registry_registration_snapshot.py::test_registry_snapshot_projects_requester_profile_completion_status -q --tb=short` initially failed with missing `profile_completion`.
- Red frontend TDD: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` initially failed because the People tab did not render profile-completion status.
- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registry_registration_snapshot.py::test_registry_snapshot_projects_requester_profile_completion_status -q --tb=short` -> 1 passed.
- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registry_registration_snapshot.py server/tests/test_registry_web_api.py server/tests/test_registry_people_admin.py server/tests/test_registry_admin_previews.py server/tests/test_registry_timeline_admin.py server/tests/test_registration_api.py::test_admin_approve_and_reject_registration_claim server/tests/test_registration_api.py::test_other_account_login_request_and_admin_approval_endpoints server/tests/test_registration_api.py::test_admin_lists_and_revokes_device_account_sessions -q --tb=short` -> 23 passed.
- `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` -> 11 passed.
- `python -m py_compile server\registry\service.py` -> passed.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r10-20260615/`: mocked `/app/admin/registry` verified People tab profile status/missing fields, no body/document horizontal overflow at 1366/1920, no console errors and no unexpected requests.

---

## Phase R11 — Russian localization and user guidance

Status: completed on 2026-06-15. R11 localized the remaining web-first registration/requester/admin moderation strings found in the R0-R10 touched surfaces, added a static mojibake/raw-label guard, repaired a corrupted Windows agent account-session message, and captured clean browser evidence for the major Russian-label flows.

Tasks:

1. Audit all touched UI strings.
2. Replace technical/internal text with Russian user-facing text.
3. Add helper text to forms:
   - account registration;
   - profile setup;
   - device linking;
   - pending approval;
   - rejection/conflict;
   - emergency ticket.
4. Add Russian error mapping for backend error codes.
5. Remove mojibake and encoding corruption in touched files/tests/docs.
6. Add UI labels for all statuses.

Required normal-user wording examples:

- `Привязать устройство` instead of `pair device`.
- `Код привязки` instead of `pairing code`.
- `Ожидает подтверждения администратора` instead of `pending_admin_review`.
- `Устройство уже привязано к другому пользователю` instead of `active_primary_user_exists`.
- `Профиль заполнен не полностью` instead of `profile incomplete`.
- `Открыть кабинет пользователя` instead of `requester workspace`.

Tests:

- Frontend tests for visible Russian labels.
- Snapshot/DOM assertions for no old legacy registration labels in agent.
- Static grep for common mojibake sequences in touched files.
- Static grep for normal UI leaking raw statuses where mapped labels are required.

Live evidence:

- Screenshots of all major flows with Russian labels and hints.

Acceptance:

- A non-technical user understands what to do next on every screen.

R11 completion checkpoint, 2026-06-15:

- `webapp/src/pages/requester/index.tsx` now uses Russian user-facing labels for Knowledge Ask prefill text, requester device agent/version/status/activity strings, requester form/message/feedback/attachment accessible labels, public ticket claim controls and ticket create/preview controls.
- `webapp/src/features/admin/registry/registry-requests-tab.tsx` maps `active_primary_user_exists` to `уже есть активный основной пользователь` in the approval diff instead of rendering the raw backend code.
- `pc_agent/ui_gui/main_window.py` repaired a mojibake account-session error string: `Сессия аккаунта недействительна. Войдите снова.`
- `scripts/test_web_first_registration_localization.py` statically checks touched web-first registration docs/UI/agent files for common mojibake markers and the R11 forbidden normal-UI snippets (`Knowledge Ask`, Latin `agent unknown`, raw `status unknown`, raw blocker code).

R11 verification:

- Red frontend TDD: `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot` initially failed on English Knowledge Ask/device/admin blocker expectations.
- Red static TDD: `python -m pytest scripts/test_web_first_registration_localization.py -q` initially failed on the mojibake agent string and normal-UI forbidden snippets.
- `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot` -> 25 passed.
- `python -m pytest scripts/test_web_first_registration_localization.py -q` -> 2 passed.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r11-20260615/`: profile setup, Knowledge Ask prefill, requester device link, account registration and admin conflict screenshots; report `web-first-registration-r11-localization-report.json` shows no console messages, no unexpected requests, no horizontal overflow and no forbidden raw text.

---

## Phase R12 — Compatibility, migration and cleanup

Status: completed on 2026-06-15; tightened on 2026-06-16. R12 compatibility is implemented: legacy backend endpoints remain covered by existing registration tests for older agents, web self-registration stays controlled by `WEB_SELF_REGISTRATION_ENABLED`, normal agent GUI legacy registration was removed, and requester profile enforcement now has `PROFILE_COMPLETION_REQUIRED=true` by default with policy-aware `profile_completion.blocks` for rollout override.

Tasks:

1. Keep backend legacy endpoints temporarily if existing tests/clients depend on them.
2. Add feature flags for transition:
   - no normal GUI re-enable for legacy agent profile registration.
   - `WEB_SELF_REGISTRATION_ENABLED=true` if deployed.
   - `PROFILE_COMPLETION_REQUIRED=true` with admin override for rollout if needed.
3. Migrate existing pending agent registration claims into web-visible pending profile/device link state.
4. Ensure existing confirmed bindings remain valid.
5. Ensure existing account sessions are not silently broken without user-facing recovery.
6. Add cleanup job/follow-up for expired pairing/session rows if not already done.
7. Document rollback path.

Tests:

- Existing active binding still works.
- Existing pending claim is visible in new requester/admin UI.
- Existing verified other-account session still validates until expiry/revoke.
- Legacy backend registration remains API-compatible for old agents, but the normal GUI no longer exposes the local full-profile registration page or confirm action.

Live evidence:

- Use seeded old-style state and confirm new UI handles it.

Acceptance:

- Migration does not strand current users/devices.

Completion notes:

- `server/config.py` defines `PROFILE_COMPLETION_REQUIRED=true` by default. `server/requester/identity_service.py` keeps incomplete profile `missing_fields` visible but makes `blocks` and requester create feature flags policy-aware. `server/web_api/requester_handlers.py` follows `blocks.ticket_preview` / `blocks.ticket_create`, so disabling the flag makes profile completion advisory without losing setup guidance.
- Existing old-style pending agent profile claims are visible through both `GET /api/web/requester/bootstrap` (`pending_registration_claims`) and `GET /api/web/admin/registry` (`registration_claims`). The requester UI renders them as Russian pending device-link requests without exposing raw `claim` terminology.
- Existing confirmed bindings and verified other-account sessions continue through current `AccountSessionService.validate_session()` rules; expired/revoked/base-binding failures return explicit error codes for GUI recovery.
- `BrowserPairingService.expire_stale_pairings()` and `AccountSessionService.expire_stale_sessions()` add explicit service-level cleanup for expired browser pairings and temporary sessions without deleting audit history.
- Rollback path is documented in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`: disable new web accounts with `WEB_SELF_REGISTRATION_ENABLED=false`, make incomplete profiles advisory with `PROFILE_COMPLETION_REQUIRED=false`, and keep older agents on their existing legacy API compatibility while normal GUI releases stay browser-only.

Evidence and verification:

- Red R12 tests failed before implementation: `test_profile_completion_required_flag_can_disable_no_device_create_gate` saw `blocks.ticket_create=true`; requester UI optional-gate test kept create disabled; cleanup tests initially lacked explicit cleanup service methods.
- Local browser evidence is stored in `artifacts/browser_live_validation/web-first-registration-r12-20260615/`: `requester-r12-pending-claim-rollout-1366x768.png`, `requester-r12-create-override-1366x768.png`, and `web-first-registration-r12-compatibility-report.json`. The report shows the pending request visible, profile setup gate not blocking, create enabled after description, no console messages, no unexpected requests, no horizontal overflow and no forbidden raw normal-UI text.
- `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registration_api.py server/tests/test_account_session_service.py -q --tb=short` -> 76 passed.
- `pnpm --dir webapp exec vitest run src/pages/requester/index.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot` -> 27 passed.
- `python -m pytest pc_agent/tests/test_account_gate.py pc_agent/tests/test_main_window_runtime_windows.py -q --tb=short` -> 34 passed.

---

## Phase R13 — Automated test matrix

Status: completed on 2026-06-15. The automated R13 matrix is covered by focused backend, frontend and agent test groups for all changed contracts.

Required backend tests:

- Account self-registration.
- Profile setup/update/security.
- Device pairing code/direct link.
- Device registration claim creation/approval/reject/conflict.
- Account session validation after binding changes.
- Admin registry moderation.
- Request form context/prefill/snapshot.
- Knowledge audience filtering and RAG eligibility.
- Data quality checks.

Required frontend tests:

- `/app/register`.
- Profile setup gate.
- Requester profile page.
- Requester devices page and device linking flow.
- Device pairing pages.
- Admin registry moderation UI.
- Request form prefill from profile.
- Knowledge recommendations visibility.
- Russian localization labels and error states.

Required agent tests:

- Account gate has no local legacy registration controls.
- Browser linking button still creates pairing.
- Copy code/open browser works.
- Pending/approved/rejected states render correctly.
- Emergency ticket remains accessible.
- Local account session invalidation still works.

Required integration/e2e tests:

- New user -> profile -> create ticket without device.
- New user -> profile -> link agent device -> admin approve -> create ticket with device context.
- Existing user -> link second device.
- Existing registered device -> other account admin approval.
- Knowledge restricted by department/location.

Acceptance:

- No phase is considered done without tests for changed contracts.

Completion notes:

- Backend matrix:
  - R12 compatibility/core path: `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registration_api.py server/tests/test_account_session_service.py -q --tb=short` -> 76 passed.
  - Additional R13 backend coverage: `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_web_session_api.py server/tests/test_registry_registration_snapshot.py server/tests/test_registry_web_api.py server/tests/test_registry_people_admin.py server/tests/test_registry_admin_previews.py server/tests/test_registry_timeline_admin.py server/tests/test_registry_quality_remediation.py server/tests/test_registry_registration_policy.py server/tests/test_knowledge_suggestions.py server/tests/test_knowledge_api.py server/tests/test_knowledge_ask.py server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_ticket_account_access.py server/tests/test_ticket_registration_enrichment.py -q --tb=short` -> 113 passed, 26 existing aiohttp `NotAppKeyWarning` warnings in web-session test setup.
- Frontend matrix: `pnpm --dir webapp exec vitest run src/features/auth/register-page.test.tsx src/pages/requester/index.test.tsx src/pages/device-pairing/device-pairing-page.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot` -> 38 passed.
- Agent matrix: `python -m pytest pc_agent/tests/test_account_gate.py pc_agent/tests/test_main_window_runtime_windows.py pc_agent/tests/test_account_session_manager.py -q --tb=short` -> 47 passed.
- Additional guards from R12/R13: docs/catalog/localization guard `python -m pytest scripts/test_navigation_catalog.py scripts/test_docs_drift_check.py scripts/test_web_first_registration_localization.py -q` -> 16 passed; `pnpm --dir webapp run build` passed with the existing large chunk warning.

---

## Phase R14 — Live validation checklist

Status: completed on 2026-06-15 for commit `c5be05b90cb991903b08cee7cd88c7ecbe06bf11`.

Live validation must run against a real local/dev stand with server, webapp, Postgres and at least one GUI agent.

### LV1 — Web account and profile

1. Start server and webapp.
2. Create user through `/app/register`.
3. Verify login/session.
4. Verify profile setup gate appears.
5. Fill profile with department/location.
6. Verify requester cabinet opens.
7. Verify admin registry person/identity exists.

Evidence:

- Browser screenshots.
- API responses with sensitive data redacted.
- DB/API confirmation of person/profile state.

### LV2 — Agent device linking

1. Start GUI agent with approved machine token.
2. Confirm no full profile registration UI is visible.
3. Click `Привязать через браузер`.
4. Copy/open pairing code.
5. Confirm device in web cabinet.
6. Approve claim in admin UI.
7. Refresh agent and requester cabinet.
8. Verify linked device shown everywhere.

Evidence:

- Agent screenshots.
- Web screenshots.
- Admin screenshots.
- API response for account-state.

### LV3 — Ticket creation with registry context

1. Use completed profile and linked device.
2. Open requester ticket creation.
3. Verify prefilled context.
4. Create ticket.
5. Open support/admin ticket detail.
6. Verify requester profile/device/context snapshot.
7. Verify routing/priority explain if applicable.

Evidence:

- Requester create screenshots.
- Support detail screenshots.
- Ticket JSON excerpt with redacted context.

### LV4 — Knowledge access

1. Create or seed two users in different departments.
2. Create/seed KB article restricted to one department.
3. Search as both users.
4. Verify allowed user sees it and denied user does not.
5. Verify RAG/Ask does not leak restricted content.

Evidence:

- Search screenshots.
- Access explain screenshots.
- RAG/retrieval trace excerpt.

### LV5 — Other-account exception

1. Registered device owned by user A.
2. User B requests temporary other-account login from agent.
3. Admin approves.
4. Agent creates ticket.
5. Support ticket detail shows other-account warning.
6. Binding remains owned by user A.

Evidence:

- Agent screenshots.
- Admin approval screenshots.
- Ticket warning screenshot.
- Binding state confirmation.

### LV6 — Localization pass

1. Walk all new and changed pages.
2. Capture screenshots for normal, empty, error and pending states.
3. Verify no mojibake and no English placeholder copy.
4. Verify no raw backend status leaks in normal user UI.

Acceptance:

- Each LV folder contains screenshots, command outputs and short notes.
- Commit hash and environment details are recorded.

Recommended evidence folder format:

`artifacts/browser_live_validation/web-first-registration-<commit>-<YYYYMMDD>/`

R14 completion checkpoint, 2026-06-15:

- Environment: remote Linux stand `https://192.168.100.17:9443` with server, webapp and PostgreSQL deployed through `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running --smoke-insecure-tls --smoke-base-url https://192.168.100.17:9443`; local Windows GUI agent instance `r14-gui-20260615` was started through `python scripts/manage_local_agent.py start r14-gui-20260615 --gui --ui-port 8794`.
- Candidate: `c5be05b90cb991903b08cee7cd88c7ecbe06bf11`. The final R14 smoke run id is `webfirst-r14-c5be05b-20260615`.
- HTTP/DB live smoke: `artifacts/browser_live_validation/web-first-registration-r14-20260615/registry_visibility_live_smoke.passed.json` -> `status=passed`. It covers confirmed owner binding, verified other-account session, pending registration blocking, revoked-session denial, owner ticket visibility, other-account ticket isolation/warning, support suggestions and registry-aware search/suggest/Ask/RAG slugs.
- Browser live evidence: `artifacts/browser_live_validation/web-first-registration-r14-20260615/r14-live-browser-evidence-report.json` -> `status=passed`; screenshots `01-register-account-only.png` through `08-admin-registry-requests.png` cover account-only registration, requester cabinet/devices, owner/other requester knowledge filtering, support ticket warning, and admin registry overview/requests. Assertions: no forbidden raw status text, no horizontal overflow, no console/page/API failures, owner IT slug visible only to owner, finance slug visible only to other account.
- Direct cookie-auth regression after the optional-auth fix confirmed `/api/knowledge/search` preserves web-session audience context: owner saw only `phase7-it-webfirst-r14-c5be05b-20260615` + public, other account saw only `phase7-finance-webfirst-r14-c5be05b-20260615` + public.
- Local GUI-agent evidence: `artifacts/browser_live_validation/web-first-registration-r14-20260615/agent-gui-evidence-report.json` -> `status=passed`; supporting files are `agent-gui-status.json` and `agent-gui-connected-uia.json`. Assertions: real `Maria Agent v3.1.64` main window seen through pywinauto/UIA, `/ui/agent/status` reports `connection_state=connected`, `has_auth_token=true`, `ui_bridge_running=true`, and the captured UIA tree does not expose legacy full-profile registration controls.
- Evidence limitations: the HTTP/DB smoke report still lists its built-in `real_agent_gui` and `browser_support_ui` fields as `not_collected`; those are superseded by the separate browser and GUI artifacts above. Windows bitmap capture for the local GUI returned invalid/black frames in the Codex desktop session, so GUI pass evidence uses canonical UIA plus `/ui/agent/status` rather than a PNG screenshot.
- Local GUI cleanup: `POST http://127.0.0.1:8794/ui/agent/shutdown` returned `{status: "ok", accepted: true}`, and `python scripts/manage_local_agent.py status r14-gui-20260615` reported the instance stopped.

---

## Release gate

Status: completed on 2026-06-15 at candidate `c5be05b90cb991903b08cee7cd88c7ecbe06bf11`. Each gate item below has implementation, targeted automated tests and R14 live evidence.

Do not mark this refactor complete until all are true:

1. Registration is browser-first.
2. GUI agent full-profile registration is hidden/disabled by default.
3. Web account creation is separate from profile completion.
4. Profile completion is mandatory for normal requester work.
5. Profile writes to registry-backed person/context.
6. Device linking works from web and agent handoff.
7. Request forms consume profile/registry context.
8. Knowledge access and RAG respect registry audience.
9. Admin can approve/reject/transfer device bindings safely.
10. Full Russian localization is present for all touched user/admin/agent surfaces.
11. Automated tests cover backend, frontend and agent behavior.
12. Live evidence exists for account, profile, device linking, ticket context, knowledge access, other-account and localization flows.
13. Existing confirmed bindings and current users are not broken.
14. Rollback/feature-flag behavior is documented.

Release gate completion checkpoint:

- Items 1-6: R2-R5/R12 implement browser-first account/profile/device linking, separate account/profile flows, mandatory profile gate policy and hidden legacy GUI full-profile registration. R14 browser and UIA evidence confirms account-only `/app/register`, requester devices, connected GUI agent and no legacy full-profile controls.
- Items 7-10: R8-R11 implement request-form context, registry-audience knowledge/RAG, admin registry moderation and Russian-localized touched surfaces. R14 smoke/browser evidence confirms ticket context visibility, other-account warning, owner/other knowledge isolation and no forbidden raw status text in captured browser flows.
- Items 11-13: R13 automated matrix passed for backend, frontend and agent; R14 live smoke confirms confirmed bindings, verified other-account sessions, pending registrations and revoked sessions are not broken.
- Item 14: rollback and feature flags are documented in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`; R12 records `WEB_SELF_REGISTRATION_ENABLED`, `PROFILE_COMPLETION_REQUIRED` and the 2026-06-16 decision that normal agent GUI stays browser-only while legacy backend compatibility remains for older agents.
- Release mode note: the remote deploy used the documented quick gate for staging/live validation. A frozen production release would still require the explicit full CI artifact and full release gate before production publication.

---

## Decisions locked in R1 before implementation

1. Self-registration is controlled by `WEB_SELF_REGISTRATION_ENABLED`; production defaults fail-closed.
2. Profile completion blocks normal requester actions, not every page. Setup, profile, device-link status, existing consents, logout and policy-controlled emergency ticket paths stay available.
3. Device-link claims require admin approval by default. First-device auto-approval is a later explicit policy option, not the default.
4. Department/location values must come from registry pickers in the first rollout. Free-text creation is disallowed in normal user UI; pending suggestions are a later audited policy option.
5. `/app/device/register` remains a compatibility route only when a device-link id exists. Missing id shows safe Russian guidance to open the flow from the agent or enter the code at `/app/device/pair`.
6. Emergency ticket without completed profile is allowed only by policy, with authenticated account, problem description, contact, and an explicit incomplete-profile marker.
7. Mandatory first-rollout profile fields: full name, department, location, phone or internal extension.
8. Required first-rollout registry entities: people, UI-login identities, departments, locations, devices and device-user bindings. Services and access/audience groups are consumed when present but are not mandatory for initial profile completion.

---

## Immediate implementation rule for Codex

Work in small vertical slices. For every slice:

1. Update backend contract.
2. Add/adjust tests.
3. Update frontend/agent UI.
4. Add Russian labels and errors.
5. Run targeted tests.
6. Run one live check when the slice affects user-visible flow.
7. Record evidence and status in this file before moving to the next slice.

Do not do broad unrelated cleanup inside this refactor. Do not rename technical database concepts unless the migration and compatibility plan is explicit.
