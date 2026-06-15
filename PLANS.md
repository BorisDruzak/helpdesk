# Active Work: Web-first Registration, Profiles and Registry Context Refactor

Status, 2026-06-15: planning document. No implementation is accepted until each phase below has tests and live evidence. The goal is to simplify requester onboarding, move the user-facing workflow into the browser, make the web requester cabinet the primary workspace, and keep the GUI agent as a secondary local helper for device handoff, emergency ticketing, consent and diagnostics.

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

Status: not started.

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

---

## Phase R1 — Product vocabulary, routes and UX contract

Status: not started.

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

---

## Phase R2 — Web account self-registration

Status: not started.

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

---

## Phase R3 — Web profile setup gate

Status: not started.

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

Acceptance:

- Profile is understandable and fully Russian.
- Profile writes to registry-backed structures.
- No arbitrary free-text department/location becomes canonical without policy.

---

## Phase R4 — Web-first device linking

Status: not started.

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

---

## Phase R5 — Remove profile registration from GUI agent

Status: not started.

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
7. Add a kill switch or feature flag if needed: `AGENT_LEGACY_REGISTRATION_ENABLED=false` by default.

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

---

## Phase R6 — Profile schema and controlled registry attributes

Status: not started.

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

---

## Phase R7 — Registry extension for production context

Status: not started.

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

---

## Phase R8 — Request forms consume profile and registry context

Status: not started.

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

---

## Phase R9 — Knowledge access and recommendations from registry context

Status: not started.

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

---

## Phase R10 — Admin registry and moderation workflow

Status: not started.

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

---

## Phase R11 — Russian localization and user guidance

Status: not started.

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

---

## Phase R12 — Compatibility, migration and cleanup

Status: not started.

Tasks:

1. Keep backend legacy endpoints temporarily if existing tests/clients depend on them.
2. Add feature flags for transition:
   - `AGENT_LEGACY_REGISTRATION_ENABLED=false` default.
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
- Legacy agent registration hidden by default but can be temporarily re-enabled for emergency rollout if feature flag exists.

Live evidence:

- Use seeded old-style state and confirm new UI handles it.

Acceptance:

- Migration does not strand current users/devices.

---

## Phase R13 — Automated test matrix

Status: not started.

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

- Account gate hides legacy registration.
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

---

## Phase R14 — Live validation checklist

Status: not started.

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

---

## Release gate

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

---

## Open decisions before implementation

1. Should self-registration be always enabled or controlled by `WEB_SELF_REGISTRATION_ENABLED`?
2. Should profile completion block all requester pages or only create-ticket/knowledge/actions?
3. Should device link claims require admin approval by default, or auto-approve first device for a new profile?
4. Should department/location creation by users become pending suggestions or be disallowed entirely?
5. Should old `/app/device/register` remain as a compatibility route or redirect into `/app/requester/devices/link`?
6. Should emergency ticket without completed profile be allowed, and what minimum context is required?
7. Which profile fields are mandatory for the first production rollout?
8. Which registry entities are required immediately: printers/MFU/services/access groups, or only people/departments/locations/devices?

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
