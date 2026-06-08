# Browser / Requester / Agent Identity Model

Status:

- Stage 1: complete for browser-link flow and manual `/app/device/pair` pairing-code entry.
- Stage 2A: requester workspace MVP complete and live-verified for owned-device listing and owned-device ticket creation.
- Stage 2B: full requester workspace remains in progress.
- Stage 3: unified browser/agent requester consent layer is not implemented yet.
- Support/admin Approval/Consent Center exists as read-only orchestration and does not replace Stage 3.

Latest live verification, 2026-06-08:

- Empty local agent `codex-live-requester-0608` registered through `/app/device/register`, agent pickup consumed the registration pairing, admin approval created active binding `e3cacd33-ba5e-436d-8930-520d0e66307a`.
- Agent GUI account gate refreshed to `confirmed_binding`; GUI automation created ticket `T-000646`.
- `/app/requester` for `requester-user-20260608-093700` showed one owned device and both live tickets; browser requester creation created ticket `T-000647`.
- Login pairing `/app/device/login` was rechecked after the redirect/pairing UI fixes: `next` returned to the pairing page and device facts stayed visible after confirmation.
- DB verification confirmed registration pairing consumed, login pairing consumed, claim approved, binding active, account sessions verified, and both tickets linked to the same requester person/binding.

## Remaining Work

Stage 2B follow-up:

- requester ticket message/chat;
- requester close/reopen/feedback;
- requester ticket preview;
- service catalog / dynamic form / knowledge suggestions reuse;
- no-device request creation;
- public ticket claim-to-account;
- requester attachments upload/download;
- requester device detail;
- requester profile workflow;
- admin user to registry person linking workflow;
- shared-device privacy coverage.

Stage 3:

- `UserConsentRequest`;
- requester consent APIs;
- agent consent APIs;
- operation consent integration;
- Remote Assist browser consent integration;
- requester/agent UI prompts;
- atomic/idempotent consent decisions.

## Goal

Move helpdesk requester identity to a clear model:

- Browser is the primary identity and requester surface.
- Agent is the local device endpoint for diagnostics, Remote Assist, inventory and command execution.
- Server is the only source of truth for identity, binding, session, ticket access and user consent.

The work should reuse existing registration, account-state, public requester, ticket creation and consent foundations instead of rewriting them from scratch.

## Current State

The project already has the core identity layers needed for this work:

- Agent / device identity: agent registers as a device and has `device_id`, machine token and websocket/HTTP access.
- Registry person / device binding: `RegistryPerson` is linked to a device through `DeviceUserBinding`.
- Requester account session: the agent has account-session states such as `confirmed_binding`, `registration_pending` and `verified_other_account`.

Existing implementation capabilities to preserve and extend:

- Agent account state already includes active bindings, pending registration, server sessions, confirmed binding accounts, verified-other-account sessions and the flags `can_register`, `can_login_confirmed_binding`, `can_login_other_account`.
- Agent profile registration already creates or finds a person, identities and registration claim, then moves the claim into `pending_user_confirmation`, `pending_admin_review` or `conflict`.
- User claim confirmation already checks web user identity against claim/person identities.
- Web login already exists through `/api/web/session/login`, creates a UI token and stores it in an HttpOnly cookie.
- Role `user` already exists as a valid role, but does not yet have a full requester workspace model.
- Public requester flow already partially exists through `/app/help`, `/app/ticket/:ticketId` and public ticket token/code.

Completed Stage 1 backend foundation:

- Migration `108_device_browser_pairings` adds persisted `device_browser_pairings`.
- `BrowserPairingService` creates short-lived login/registration pairings with hashed pairing token/code storage.
- New pending pairing for the same `device_id + purpose` supersedes older pending rows.
- Agent endpoints exist:
  - `POST /api/registry/agent/browser-pairings`
  - `GET /api/registry/agent/browser-pairings/{pairing_id}`
- Web-authenticated manual-code lookup exists:
  - `POST /api/web/registry/browser-pairings/lookup`
  - returns only `pairing_id`, `purpose`, `expires_at` and `next_url`; it does not return `device_id`, device facts, pairing token or raw pairing code.
- Login pairing pickup creates a `confirmed_binding` account session and returns the plaintext `session_token` to the agent exactly once.
- Existing coverage includes pairing secret hashing, supersede, expiry lookup, one-time pickup and wrong-device API rejection.

## Scope

Implement in three stages:

1. Browser-mediated registration/login for the agent.
2. Authenticated requester workspace in the browser.
3. Unified browser/agent consent layer.

Expected ownership zones:

- Auth, sessions and device identity.
- Registry / inventory / CMDB.
- Typed web boundary.
- React webapp UI.
- Agent runtime / GUI.
- Ticket service-desk contract.
- Tool execution and operations.
- Docs / navigation.

Classification: cross-cutting. The implementation will likely add routes, DTOs, DB models/migrations, web UI, agent GUI behavior and security checks.

## Non-Goals

- Do not change Protocol V3 unless a later implementation step proves it is strictly required.
- Do not let browser routes accept arbitrary `device_id` for pairing, login or requester ticket creation.
- Do not store agent account session tokens in browser localStorage/sessionStorage.
- Do not return agent session tokens to the browser.
- Do not make local agent forms the authoritative source for user registration.
- Do not merge public requester access and authenticated requester access into one implicit security model.
- Do not allow support/admin to approve user consent on the user's behalf except through an explicit audited override policy.

## Constraints

- Preserve existing agent technical registration and machine-token authorization.
- Pairing tokens and codes must be short-lived, one-time and auditable.
- Browser state-changing requester actions need CSRF protection because web auth uses HttpOnly cookies.
- Requester ticket/device/consent access must be checked through resolved ownership, not by trusting client-provided ids.
- Shared devices must not leak another user's tickets.
- `verified_other_account` must remain strict: it can see only the exact approved/session-owned scope where applicable.
- Sensitive tokens, auth headers, cookies, raw machine tokens and consent tokens must never be logged.
- Agent machine token is transport/device identity only and must not be treated as requester identity.
- Agent-side user consent decisions require a valid requester account session or an explicitly audited local-user confirmation mechanism.
- Pairing secrets must be one-time, short-lived, stored hashed/protected and never logged.
- Browser-visible changes require screenshots or browser-run evidence from the relevant canonical route: `/app/requester`, `/app/device/pair`, `/app/device/register`, `/app/device/login`, or the changed admin/support route.

## Architecture Decisions

- Browser pairing links must use `pairing_id` or an opaque `pairing_token`, not `device_id`.
- Server maps pairing to `device_id`; browser never chooses the device directly.
- Browser confirms user identity and user decisions.
- Agent polls server for pairing/session/consent results and receives agent-only session tokens.
- Server owns all transitions, ownership checks, audit records and ticket timeline events.
- Authenticated requester endpoints should live under `/api/web/requester/*`.
- Generic `/api/tickets/*` must not be used directly for authenticated requester actions without an explicit requester ownership wrapper.
- Public `/app/help` and `/app/ticket/:ticketId` remain guest/public flows and should be reused carefully, not collapsed into authenticated requester semantics.

## Stage 1: Browser-Mediated Agent Registration/Login

Goal: device registration to a user and agent user login happen through the browser, with the agent participating only as the device endpoint.

### Main Entity

Introduce server entity `DeviceBrowserPairing`.

Recommended fields:

- `pairing_id`
- `device_id`
- `purpose`: `registration | login`
- `status`: `pending | confirmed | consumed | expired | canceled | failed`
- `pairing_code`
- `created_at`
- `expires_at`
- `confirmed_at`
- `consumed_at`
- `canceled_at`
- `confirmed_by_actor_id`
- `confirmed_person_id`
- `resulting_claim_id`
- `resulting_account_session_id`
- `failed_reason`
- `last_polled_at`
- `poll_attempt_count`
- `created_by_agent_version`
- `created_from_ip`
- `created_from_user_agent`
- `metadata_json`

Pairing token/code storage rules:

- raw pairing token/code may be shown only once to the agent/user;
- raw pairing token/code must never be logged;
- pairing token/code must be stored hashed or otherwise protected;
- plaintext agent account `session_token` must not be stored in pairing state.

Creating a new pending pairing for the same `device_id` and `purpose` should cancel or supersede older pending pairings. This prevents multiple open browser tabs from racing stale pairing requests.

### Registration Flow

Agent action: "Зарегистрировать через браузер".

Backend:

- `POST /api/registry/agent/browser-pairings`
- body includes `purpose=registration`
- authenticated by agent machine token.

Server returns:

- `pairing_id`
- `pairing_code`
- `expires_at`
- `browser_url`
- `poll_url`

Browser opens `/app/device/register?pairing_id=...`.

Fallback: if the agent cannot open the system browser automatically, the user can open `/app/device/pair`, sign in, enter the displayed `pairing_code`, and be redirected to `/app/device/login?pairing_id=...` or `/app/device/register?pairing_id=...`. The lookup resolves only pending pairings after web login, expiry checks and rate-limit checks.

If the web user is not logged in, redirect to `/app/login?next=...`.

Browser confirmation page should show safe device facts such as hostname, OS, agent version and safe location/organization details when available.

Server confirmation must:

- validate pairing status and expiry;
- validate web session;
- resolve `RegistryPerson` for the web user;
- create or update `DeviceRegistrationClaim`;
- apply registration policy;
- return user-facing status: `approved`, `pending_admin_review`, `pending_user_confirmation`, `conflict`, `rejected` or `failed`.

### Login Flow

Agent action: "Войти через браузер".

Backend:

- `POST /api/registry/agent/browser-pairings`
- body includes `purpose=login`.

Browser opens `/app/device/login?pairing_id=...`.

If the user is already logged in, the page should still require explicit confirmation:

- show current user;
- show target device;
- ask whether to connect the agent on that device.

Server confirmation must:

- resolve `RegistryPerson` for the web user;
- check active binding between the person and device;
- create `DeviceAccountSession(account_mode=confirmed_binding)` only when an active binding exists;
- offer registration or policy-driven alternative login when binding is absent or belongs to another user;
- refuse session creation on conflict.

Agent polling endpoint:

- `GET /api/registry/agent/browser-pairings/{pairing_id}`
- returns `session` and `session_token` to the agent exactly once after browser confirmation;
- marks pairing `consumed`;
- rejects repeated token retrieval.

Browser pairing result delivery must not rely on process-local memory in production. The confirmation/result state must be backed by DB state and one-time pickup semantics.

Recommended token issuance model:

- browser confirms login;
- server marks pairing `confirmed`;
- agent polls with machine-token authentication;
- server creates or loads the account session at pickup time;
- server returns the plaintext `session_token` to the agent exactly once;
- only `session_token_hash` is stored.

### Agent Fallback

Keep "Войти в агенте" only as a fallback:

- confirmed binding can select an already confirmed user;
- different user creates a `verified_other_account` request;
- unregistered device prompts browser registration;
- local form must not become authoritative registration.

### Stage 1 Acceptance Criteria

- [x] New device creates browser registration pairing, browser confirms, claim appears, agent consumes the registration pairing, admin approves the claim, and the agent sees a `confirmed_binding` account/session candidate. Covered by `test_registration_pairing_approval_surfaces_confirmed_binding_to_agent` and live MCP/API/DB registration-flow smoke.
- [x] Registered device creates browser login pairing, browser confirms under the same user and agent receives a `confirmed_binding` session.
- [x] Already logged-in browser user confirms login without re-entering password.
- [x] Expired pairing is rejected at service lookup/pickup boundaries.
- [x] Consumed pairing cannot be reused for token pickup.
- [x] Browser cannot substitute a foreign `device_id` through the agent pairing create endpoint.
- [x] Browser confirmation cannot create a confirmed-binding session for a different user or an unbound device.
- [x] Device registered to another user does not receive a confirmed-binding session through browser login.
- [x] Logout or revoked binding invalidates the agent session and returns the agent to account gate. Covered by `test_main_window_refresh_clears_revoked_session_and_returns_to_account_gate`.

## Stage 2: Authenticated Requester Workspace

Goal: create `/app/requester` as the authenticated browser workspace for end users.

### Permissions And Routes

Add requester workspace permission:

- `workspace.requester.view`

Add requester permissions:

- `requester.ticket.view`
- `requester.ticket.create`
- `requester.ticket.comment`
- `requester.ticket.close`
- `requester.ticket.reopen`
- `requester.ticket.feedback`
- `requester.ticket.attachment.upload`
- `requester.ticket.attachment.download`
- `requester.device.view`
- `requester.profile.view`
- `requester.consent.decide`

Protected routes:

- `/app/requester`
- `/app/requester/tickets`
- `/app/requester/tickets/:ticketId`
- `/app/requester/new`
- `/app/requester/devices`
- `/app/requester/profile`
- `/app/requester/consents`

Public routes `/app/help` and `/app/ticket/:ticketId` remain unchanged.

### RequesterIdentityResolver

Add backend service `RequesterIdentityResolver`.

Behavior-level functions:

- `resolve_person_for_web_user(actor_id)`
- `list_allowed_devices(person_id)`
- `list_active_bindings(person_id)`
- `can_view_ticket(actor_id, ticket)`
- `can_create_ticket_for_device(actor_id, device_id)`
- `can_decide_consent(actor_id, consent)`

Resolve person through identities such as:

- `ui_login`
- `email`
- `windows_login`
- `ad`

Do not build requester ownership only on `requester_id == user_login`. Ticket visibility must account for:

- `requester_id`
- `requester_person_id`
- `requester_binding_id`
- `requester_account_session_id`

Requester-owned account sessions are sessions where:

- `session.person_id == resolved_person_id`;
- or `session.binding_id IN active/requester bindings`;
- or `verified_other_account` is matched to the resolved person and allowed by strict session scope.

For `verified_other_account`, visibility remains limited to tickets created by the exact approved session unless policy explicitly allows a broader authenticated requester view.

### Requester Bootstrap

Add:

- `GET /api/web/requester/bootstrap`

Return:

- profile/person summary;
- devices;
- active bindings;
- pending registration claims;
- open ticket count;
- tickets requiring user action count;
- pending consent count;
- feature flags and policies.

Behavior:

- if no person is found, open the workspace with onboarding and limited actions;
- if person exists but has no devices, allow general request creation when service policy allows it;
- if devices exist, show devices and quick actions.

### Requester Tickets

Add:

- `GET /api/web/requester/tickets`
- `GET /api/web/requester/tickets/{ticket_id}`
- `POST /api/web/requester/tickets/{ticket_id}/message`
- `POST /api/web/requester/tickets/{ticket_id}/close`
- `POST /api/web/requester/tickets/{ticket_id}/feedback`
- `POST /api/web/requester/tickets/{ticket_id}/reopen`
- `POST /api/web/requester/tickets/claim-public`

Ticket list scope:

- `requester_id == actor_id`
- or `requester_person_id == resolved_person_id`
- or `requester_binding_id IN active_binding_ids`
- or `requester_account_session_id IN requester-owned account sessions`.

Authenticated requester ticket detail should reuse requester-safe serialization and timeline, but should not require public access code for owned tickets.

Public ticket claim flow:

- user enters `ticket_id` and public access code/token;
- server verifies the code/token through existing public-ticket access rules;
- server resolves requester person from web session;
- server attaches requester identity metadata such as `requester_person_id`, `requester_id` or a dedicated link record;
- ticket becomes visible in the authenticated requester cabinet.

### Request Creation

Add:

- `POST /api/web/requester/tickets/preview`
- `POST /api/web/requester/tickets`

Reuse `create_ticket_with_side_effects()` so routing, SLA, OLA, auto-assign, playbooks, initial message and request-template behavior stay consistent.

Frontend should reuse the existing requester form flow from `/app/help`:

- service catalog;
- offering;
- dynamic form;
- safe preview;
- knowledge suggestions;
- urgency/importance.

Authenticated mode adds context selection:

- request linked to one of my devices;
- general service request when allowed.

Server must verify that selected device belongs to requester identity scope.

No-device request strategy:

- Stage 2 may keep a server-owned virtual/placeholder device strategy for compatibility with current ticket assumptions.
- Requester frontend must not invent `device_id`.
- Ticket custom fields must explicitly mark `request_context = "no_device"` or equivalent.
- Later migration may make `device_id` nullable if the ticket/device boundary is refactored.

### Requester Devices And Profile

Add:

- `GET /api/web/requester/devices`
- `GET /api/web/requester/devices/{device_id}`

Show safe device facts:

- hostname;
- OS;
- agent version;
- online/offline;
- relationship type;
- binding status;
- last seen;
- open ticket count;
- available actions.

Add `/app/requester/profile`:

- display name;
- full name;
- email;
- phone;
- department;
- location;
- identities;
- devices.

Profile edits must be policy-controlled. Authoritative registry fields should be read-only or changed through verification/request workflows.

### Admin User/Person Workflow

Unify admin user and registry person management:

- UI login account: `user_login`, role, active/inactive, password reset, lock state.
- Registry person: display/full name, email, phone, department, location, identities, devices, active bindings, tickets.
- Explicit link: `ui_users.user_login` ↔ `RegistryPersonIdentity(provider='ui_login', identifier=user_login, verified=true)` ↔ `RegistryPerson`.

### Stage 2 Acceptance Criteria

- User logs into `/app/requester` through web session.
- If person is found, user sees owned devices.
- If person is not found, requester workspace opens with onboarding and limited actions.
- Tickets created through the agent appear in the user's cabinet through person/binding/session matching.
- Tickets for another user on a shared device are hidden.
- User can create a request without a device when the selected service allows it.
- User can create a request for an owned device.
- User cannot create a request for a foreign `device_id`.
- Public ticket can still be opened by old access code.
- Authenticated cabinet does not require access code for owned tickets.
- User has clear profile and devices pages.

## Stage 3: Unified Browser/Agent Consent Layer

Goal: one consent mechanism works in both requester browser workspace and agent GUI.

Consent prompts should appear:

- in requester cabinet;
- in agent GUI when the agent is online;
- in ticket timeline when applicable.

First decision wins. Other surfaces show the already decided result.

### Main Entity

Introduce `UserConsentRequest`.

Recommended fields:

- `consent_id`
- `subject_type`: `operation | remote_assist | diagnostic | tool_run | file_transfer | clipboard | elevated`
- `subject_id`
- `ticket_id`
- `device_id`
- `requester_person_id`
- `requester_binding_id`
- `requester_account_session_id`
- `requested_by_actor_id`
- `requested_by_role`
- `risk_level`
- `policy_snapshot`
- `risk_explanation`
- `requested_action_payload_redacted`
- `title`
- `description`
- `reason`
- `status`: `pending | approved | denied | expired | superseded | canceled`
- `expires_at`
- `decided_by_actor_id`
- `decided_by_role`
- `decided_from_surface`: `browser | agent_gui | api`
- `decided_at`
- `metadata_json`

### APIs

Requester browser:

- `GET /api/web/requester/consents`
- `GET /api/web/requester/consents/{consent_id}`
- `POST /api/web/requester/consents/{consent_id}/approve`
- `POST /api/web/requester/consents/{consent_id}/deny`

Agent GUI:

- `GET /api/registry/agent/consents`
- `POST /api/registry/agent/consents/{consent_id}/approve`
- `POST /api/registry/agent/consents/{consent_id}/deny`

Agent GUI consent decisions that count as user consent must carry a valid requester account session. Agent machine-token authentication can deliver the transport, but cannot be the identity that approves user consent.

### Idempotency And Uniqueness

There must be at most one active pending consent per `subject_type + subject_id` unless policy explicitly allows multiple consent rounds.

Decision transitions must use an atomic compare-and-set from `pending` to `approved` or `denied`:

- first decision wins;
- second decision returns the current final state;
- repeated approve/deny must not queue a second operation or start a second Remote Assist session.

### Diagnostics And Tool Operations

Flow:

- support starts a diagnostic/tool operation;
- policy requires user consent;
- server creates operation with `status=waiting_consent`;
- server creates `UserConsentRequest(status=pending)`;
- browser requester workspace shows pending consent;
- agent GUI shows prompt if online;
- user approves or denies on any surface;
- server atomically transitions consent;
- approved consent queues the operation;
- denied consent cancels/denies the operation;
- ticket timeline receives an event.

Approve/deny endpoints must check requester ownership:

- web user;
- resolved person;
- bindings;
- consent ticket/device scope.

Knowing only `consent_id` is not sufficient.

### Remote Assist

Split Remote Assist into two steps:

1. User consent approved.
2. Agent technically starts or accepts the session.

Browser approval must not receive agent signaling token, ICE, SDP or other technical session secrets. Browser only approves consent. After approval, server sends the agent a command to start approved Remote Assist.

Agent GUI approval remains possible through the same `consent_id`.

### UI Behavior

Requester cabinet should show a block such as "Ожидают вашего подтверждения":

- diagnostic: what will run, why, risk and requester;
- Remote Assist: mode, access, duration and operator;
- file transfer / clipboard / elevated action: clear warning;
- actions: approve, deny, details.

Agent GUI should show a local prompt with the same `consent_id`.

If the user already decided in one surface, the other surface updates to the final result.

Polling is acceptable for the first version, but the UI should be ready for websocket/event stream updates.

### Stage 3 Acceptance Criteria

- Diagnostic requiring consent appears in browser cabinet and agent GUI.
- Browser approval queues the operation.
- Agent GUI approval updates browser cabinet.
- Repeated approve/deny after decision is idempotent and does not create a second run.
- Foreign user cannot approve consent for another user's ticket/device.
- Remote Assist can be approved in browser and then agent receives a start command.
- Remote Assist can be approved in agent and browser sees approved status.
- Expired consent does not start an operation.
- All decisions are written to audit and ticket timeline.
- Revoked binding/session blocks pending consent decisions.

## API Response Guidance

Endpoints should consistently return:

- `status`
- `data`
- `error_code` on failure
- user-facing `message`
- safe technical details only when appropriate
- `next_action`

Pairing `next_action` examples:

- `open_browser`
- `login_required`
- `confirm_registration`
- `wait_admin_review`
- `conflict_contact_support`
- `agent_poll`
- `complete`

## Documentation Plan

Add or update:

- `server/docs/BROWSER_AGENT_PAIRING.md`
- `server/docs/REQUESTER_WORKSPACE.md`
- `server/docs/REQUESTER_IDENTITY_RESOLVER.md`
- `server/docs/USER_CONSENT_MODEL.md`
- `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`
- `server/docs/SECURITY_AND_AUTH.md`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `pc_agent/docs/AUTHENTICATION.md` if agent auth/session behavior changes.
- `docs/QUICK_LOOKUP.md`
- `docs/ARCHITECTURE_BOUNDARIES.md` if ownership/contract map changes.

Each new model doc should cover:

- identity layers;
- lifecycle;
- security boundaries;
- known non-goals;
- smoke checklist;
- migration notes.

## Verification Plan

Each implementation stage needs targeted tests before browser/live checks.

Stage 1:

- [x] browser pairing registration smoke;
- [x] browser pairing login smoke;
- [x] pairing expiry/reuse tests;
- [x] wrong-device substitution tests;
- [x] pairing secret hashing/protected-storage tests;
- [x] active pairing supersede/cancel tests;
- [x] manual pairing-code entry smoke;
- [x] account-state confirmed-binding transition and session tests.

Stage 2:

- requester identity resolver tests;
- requester ticket visibility tests;
- shared-device privacy tests;
- no-device request compatibility tests;
- public ticket claim-to-account tests;
- requester attachment upload/download permission tests;
- requester ticket create preview/create tests;
- public ticket compatibility tests;
- webapp route and build tests.

Stage 3:

- consent browser approve smoke;
- consent agent approve smoke;
- agent consent decision with requester account session tests;
- one-active-pending-consent tests;
- idempotent approve/deny tests;
- foreign-user denial tests;
- expired consent tests;
- Remote Assist browser consent smoke.

Common checks:

- `python scripts/verify_workspace.py`
- focused server pytest for changed domains;
- focused `pc_agent` tests for GUI/session behavior;
- `pnpm --dir webapp run test` for requester/web changes;
- `pnpm --dir webapp run build`;
- browser evidence for visible flows;
- quick deploy/smoke through project scripts when validating on Linux stand;
- stop remote services after checks unless explicitly asked to leave them running.

## Execution Checkpoints

- [x] Stage 1 design: confirm DB model, routes, DTOs, agent GUI states and security boundaries.
- [x] Stage 1 tests: RED coverage covers backend lifecycle, expiry, reuse, wrong-device behavior, web-user login confirmation, web-user registration confirmation, approval-to-confirmed-binding account-state transition, web route behavior, webapp confirm pages, manual pairing-code lookup/rate-limit/inactive rejection and agent polling. Linux stand smoke covered live API/DB behavior.
- [x] Stage 1 backend: `DeviceBrowserPairing`, migration, repo/service, agent create/pickup routes, web-authenticated manual code lookup/confirmation routes, web-user ownership checks and registration pairing confirmation are implemented.
- [x] Stage 1 frontend/agent: `/app/device/pair`, `/app/device/login`, `/app/device/register`, protected routes, account-gate browser actions, agent API client create/poll, main-window polling/session save and invalid-session return-to-gate behavior are implemented.
- [x] Stage 1 verification and docs: docs/CODEMAP/navigation updated; local targeted tests, `verify_workspace.py`, web build, deploy, live MCP route check, registration approval-to-confirmed-binding smoke, invalid-session GUI regression and Linux DB/API invariants passed. Remote server was stopped after checks.
- [x] Stage 2 design: requester resolver, requester permission catalog, `/api/web/requester/*` boundary and authenticated/public separation are confirmed for the first workspace slice.
- [x] Stage 2 tests: resolver-owned visibility and owned/foreign device create coverage are added for the authenticated workspace slice. Shared-device privacy, attachment/comment/close/reopen/feedback and consent tests remain follow-up coverage.
- [x] Stage 2 backend: implemented `/api/web/requester/bootstrap`, `/devices`, `/tickets`, `/tickets/{ticket_id}` and owned-device `POST /tickets`; server resolves person/bindings/sessions and does not trust arbitrary browser `device_id`.
- [x] Stage 2 frontend: implemented `/app/requester` route, workspace navigation/access wiring and first authenticated requester page for profile summary, owned devices, recent tickets and owned-device ticket creation.
- [x] Stage 2A verification and docs: local tests, browser, agent GUI, MCP and DB live checks passed for owned-device listing and owned-device ticket creation.
- [ ] Stage 2B lifecycle: requester message/chat, close/reopen/feedback, ticket detail, attachments, preview/catalog/forms, no-device creation and public ticket claim remain follow-up work.
- [ ] Stage 2B admin: connect UI users to registry persons through explicit admin workflow.
- [ ] Stage 3 design: confirm consent entity, operation integration and Remote Assist boundary.
- [ ] Stage 3 tests: add consent ownership, idempotency, expiry and browser/agent decision coverage.
- [ ] Stage 3 backend: implement `UserConsentRequest`, requester/agent APIs and operation transition integration.
- [ ] Stage 3 frontend/agent: implement requester consent center and agent prompts.
- [ ] Stage 3 verification and docs.

## Handoff

Continue with a Stage 2B requester-workspace slice unless the user explicitly asks for Stage 3 consent work first. Stage 1 and Stage 2A live verification are complete enough for handoff; do not repeat them as the next item unless a regression needs to be checked.

Done in this slice:

- web-authenticated pairing lookup/confirmation endpoints;
- confirmed-binding login requires active binding for the logged-in web user;
- registration pairing creates/updates a registration claim for the pairing device;
- `/app/device/login` and `/app/device/register` pages;
- `/app/device/pair` manual pairing-code page with safe web-authenticated lookup and redirect to confirmation;
- agent account-gate browser-first actions and polling;
- agent account-state refresh clears revoked/invalid local account sessions and returns to account gate;
- one-time account-session token remains agent-only.
- authenticated requester workspace route `/app/requester`;
- requester permission catalog and `user` default workspace access;
- requester identity resolver over web login, person identities, active bindings and server account sessions;
- requester-safe bootstrap/devices/tickets APIs under `/api/web/requester/*`;
- requester ticket creation for server-verified owned devices;
- local backend/frontend coverage for owned visibility and foreign-device denial.

Deferred / next:

- Stage 2B follow-up: requester no-device creation/onboarding, ticket detail, message/chat, close/reopen/feedback, preview/catalog/forms, attachments, device/profile pages, public ticket claim and shared-device privacy coverage.
- Stage 2B admin follow-up: explicit admin UI workflow for linking existing UI users to registry persons. Current resolver uses existing person identities.
- Stage 3 follow-up: canonical `UserConsentRequest`, requester/agent consent APIs, operation/Remote Assist integration, browser requester prompts, agent GUI prompts and atomic/idempotent decisions.

Immediate next work:

1. Start Stage 2B requester lifecycle: ticket detail, message/chat, close/reopen/feedback, preview/catalog/forms or no-device creation.

Before code changes, read the nested instructions for the target area:

- `server/AGENTS.md` for backend/auth/registry/ticket work.
- `pc_agent/AGENTS.md` for agent GUI/runtime work.
- `webapp/AGENTS.md` for requester browser UI work.

Do not stage unrelated existing dirty files or generated artifacts. Current known unrelated dirty surfaces include `.codex/config.toml`, `pc_agent/ui_gui/tickets_list_model.py`, `scripts/live_agent_uia_state_probe.py` and untracked files under `artifacts/` / `audit_artifacts/`.
