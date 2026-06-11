# Browser / Requester / Agent Identity Model

Status:

- Stage 1: complete for browser-link flow and manual `/app/device/pair` pairing-code entry.
- Stage 2A: requester workspace MVP complete and live-verified for owned-device listing and owned-device ticket creation.
- Stage 2B: requester ticket detail/message plus close/reopen/feedback lifecycle are implemented and live-verified; authenticated requester catalog/form create with safe preview is implemented and live-verified; requester knowledge suggestions reuse is implemented and live-verified; requester attachment upload/message/download is implemented and live-verified; public ticket claim-to-account is implemented and live-verified; requester no-device creation is implemented and live-verified; requester device detail is implemented and live-verified; requester profile workflow is implemented and live-verified; shared-device privacy is implemented and live-verified; admin UI user to RegistryPerson linking is implemented.
- Stage 3: unified browser/agent requester consent layer is implemented and renewed-live-verified for `UserConsentRequest`, requester/agent APIs, requester browser prompts, agent account-session decision boundary, operation side effects and Remote Assist browser approve/deny plus agent technical start after approval. Viewer-side WebRTC offer/answer is outside this identity/consent-model scope.
- Support/admin Approval/Consent Center exists as read-only orchestration and does not replace Stage 3.

Audit update, 2026-06-10:

- Browser cookie-auth unsafe requests are same-origin protected in auth middleware for web-session bridge paths. Missing `Origin`/`Referer` returns 403; mismatched origin returns 403; bearer/agent token paths remain outside this cookie-auth guard.
- Direct browser pairing GET now uses pairing service visibility rules, expires stale rows before response, returns no device facts for expired/consumed/superseded/unknown pairings, and is rate-limited.
- Consent-required support tool runs, legacy `/api/tools/run` and operation retries create canonical `UserConsentRequest` rows in the same transaction as `Operation(status='waiting_consent')`; missing requester scope rolls back instead of creating an orphan waiting operation.
- Remote Assist request creation rejects tickets without requester scope before creating a pending remote session or user consent.
- DB uniqueness for one active pending consent per subject is present in migration `20260610_109_user_consent_requests.py` through partial unique index `ux_user_consent_requests_pending_subject`.

Audit update, 2026-06-11:

- Live Remote Assist approve-path on `https://192.168.100.17:9443` found and fixed a proxy-origin CSRF mismatch: browser cookie-auth approve with public origin `https://192.168.100.17:9443` was rejected before `server/auth/middleware.py` trusted reverse-proxy `Forwarded` / `X-Forwarded-Proto` + `X-Forwarded-Host` origins. Regression coverage: `test_web_session_cookie_auth_accepts_forwarded_public_origin`.
- Renewed live Remote Assist browser approval now succeeds through cookie auth: support request creates one canonical `UserConsentRequest`, browser approve returns 200 without agent/session/signaling secrets, consent becomes `approved`, and `remote_assist.request` is delivered to the real online agent `7a3429ec-1c0b-5495-9aad-b284f08ae965`. Evidence: `artifacts/requester-agent-consent-audit-20260611-002201/api/live-remote-assist-http-after-csrf-fix.json` and `artifacts/requester-agent-consent-audit-20260611-002201/api/remote-assist-outbox-after-wait.json`.
- The same live run exposed a remaining runtime gap: the real agent acknowledged and completed the delivered `remote_assist.request`, but the agent GUI/runtime did not call the technical `/api/remote-assist/{session_id}/approve`; `remote_access_sessions.status` stayed `waiting_consent` with `consent_status=approved` and no `agent_token_hash`. Do not mark Remote Assist approve-path fully complete until the agent starts/accepts the technical session.
- DB integrity checks on the stand show no waiting tool consent orphans, no duplicate pending consent subjects, no missing pairing hashes, and no public-claim access-code event leak. One pre-hardening pending Remote Assist consent without `requester_person_id` remains from an older live run (`subject_id=cd96935c-1b37-4b59-a391-855757302565`) and must be expired/cleaned or explained before using global `pending_missing_requester_person=0` as a final gate.
- Follow-up fix: `pc_agent/ui_bridge/event_bus.py` now replays unexpired `remote_assist_request` events by `session_id` for late GUI/SSE subscribers, so an approved Remote Assist command is not lost if it arrives while the GUI reconnects. Regression coverage: `test_event_bus_replays_remote_assist_request_for_late_subscriber` and `test_event_bus_does_not_replay_expired_remote_assist_request`.
- Local GUI live re-run with source agent `codex-ra-gui-0611` verified the full browser approve -> agent technical start path: support request 200, requester cookie approve 200, canonical consent count 1, no requester/browser secret exposure, outbox delivered, operation succeeded, `/api/remote-assist/{session_id}/approve` authenticated as agent, `agent_token_hash_present=true`, and session reached `starting`. Evidence: `artifacts/requester-agent-consent-audit-20260611-002201/api/live-remote-assist-local-gui-after-replay-fix-3.json`, `artifacts/requester-agent-consent-audit-20260611-002201/db/remote-assist-local-gui-final-db-check.json`, `artifacts/requester-agent-consent-audit-20260611-002201/tests/local_agent_logs_after_ra_start.txt`, `artifacts/requester-agent-consent-audit-20260611-002201/tests/remote_server_logs_after_local_gui_ra_start.txt`, `artifacts/requester-agent-consent-audit-20260611-002201/browser/local-agent-uia-remote-assist-window.png`.
- The stale pre-hardening under-scoped pending Remote Assist consent was expired via an audited live cleanup; renewed DB integrity now shows `waiting_tool_consent_orphans=0`, `duplicate_pending_subjects=0`, `pending_missing_requester_person=0`, `pairing_missing_hashes=0`, and `claim_events_with_access_code=0`.
- 2026-06-11 final hardening local pass: consent-required operation retry ticket events now redact replay params with the same helper used for `UserConsentRequest.requested_action_payload_redacted`; `UserConsentService.create_request()` is race-safe around the partial unique pending-subject index; public ticket claim now requires a resolved `RegistryPerson` and returns `REQUESTER_IDENTITY_REQUIRED` for unlinked web users; requester-facing Remote Assist consent list/detail/approve responses have regression coverage proving they do not expose ICE/SDP/signaling/agent/viewer/session secrets. Local evidence is captured in `artifacts/requester-agent-consent-final-audit-20260611-140237/tests/test-summary.txt`.
- 2026-06-11 final renewed full live audit after hardening is complete on `https://192.168.100.17:9443` with evidence in `artifacts/requester-agent-consent-full-live-audit-20260611-183743/`: requester lifecycle/message/close/feedback/reopen, shared-device privacy, public claim strict person policy, browser same-origin CSRF rejection, direct pairing inactive states, operation consent approve/deny/idempotent repeat, Remote Assist browser approve -> agent technical approve -> ended, Remote Assist browser deny, requester Remote Assist secret non-exposure, browser screenshots, console/network, API evidence and DB integrity all passed. Final DB checks show `orphan_waiting_consent=0`, `duplicate_pending_consent=0`, `pending_missing_requester_person=0`, `pairing_missing_hashes=0`, `public_claim_access_code_leak=0`, and `consent_event_sensitive_param_hits=0`.

Current audit coverage matrix:

| Flow | Backend endpoint | Frontend route | Agent path | Tests | Live evidence | Status | Gaps |
|---|---|---|---|---|---|---|---|
| Direct pairing GET inactive states | `GET /api/web/registry/browser-pairings/{pairing_id}` | `/app/device/register`, `/app/device/login` | pairing pickup polling | `test_web_user_direct_pairing_get_rejects_inactive_pairings_without_device_facts` | `artifacts/requester-agent-consent-full-live-audit-20260611-183743/api/api-results-final.json` | complete | Valid lookup succeeded; expired/consumed/superseded/unknown returned safe 404/no device facts. |
| Browser cookie-auth state changes | auth middleware for `/api/web/*`, upload/artifact bridge paths | requester/admin/support webapp | none | `test_web_session_cookie_auth_unsafe_requests_require_same_origin`, `test_web_session_cookie_auth_accepts_forwarded_public_origin`, bearer bypass test | `api/api-results-final.json`, `browser/network-shared-requester.json`, screenshots | complete | Requester message and public claim without Origin returned 403 `CSRF_ORIGIN_REQUIRED`; correct-origin state changes succeeded. |
| Support/legacy operation consent invariant | support/legacy/retry waiting-consent operation paths | `/app/tickets`, legacy/API clients | none until approve | `test_web_support_tool_action_keeps_consent_required_tool_waiting`, `test_legacy_tools_run_creates_user_consent_for_waiting_operation`, `test_retry_consent_required_operation_creates_waiting_consent_without_dispatch` | `db/db-results-final.json` | complete | Global DB orphan/duplicate checks are zero after renewed live run. |
| Retry operation consent | `POST /api/operations/{operation_id}/retry` | `/app/tickets` operation retry | none until approve | `test_retry_consent_required_operation_creates_waiting_consent_without_dispatch` | `api/api-results-final.json`, `db/db-results-final.json` | complete | Browser approve queued/accepted exactly one operation; deny left operation denied and no outbox. |
| Remote Assist approve path | `POST /api/web/support/tickets/{ticket_id}/remote-assist/request`, `POST /api/web/requester/consents/{consent_id}/approve` | `/app/tickets`, requester consent center | `remote_assist.request` delivered to online agent; technical approve creates agent token hash | `test_remote_assist_rejects_ticket_without_requester_scope`, remote assist service tests, UI bridge replay tests | `api/api-results-final.json`, `db/db-results-final.json` | complete | Browser approve exposed no requester-side ICE/SDP/signaling/agent/viewer secrets; agent technical approve succeeded; session ended cleanly. |
| Remote Assist deny path | same request endpoint plus requester consent deny | requester consent center | no technical start after deny | remote assist service tests | `api/api-results-final.json`, `db/db-results-final.json` | complete | Browser deny set session/consent to denied; agent technical approve after deny returned 409 `INVALID_SESSION_STATUS`; `agent_token_hash_present=false`. |
| Viewer-side WebRTC offer/answer | viewer/signaling endpoints | support viewer | WebRTC media/signaling | remote assist no-db/service tests | not collected in this identity-model audit | non-goal | Outside Browser / Requester / Agent identity and consent-model signoff; keep for a viewer/media gate. |

Latest live verification, 2026-06-08/09:

- Empty local agent `codex-live-requester-0608` registered through `/app/device/register`, agent pickup consumed the registration pairing, admin approval created active binding `e3cacd33-ba5e-436d-8930-520d0e66307a`.
- Agent GUI account gate refreshed to `confirmed_binding`; GUI automation created ticket `T-000646`.
- `/app/requester` for `requester-user-20260608-093700` showed one owned device and both live tickets; browser requester creation created ticket `T-000647`.
- Login pairing `/app/device/login` was rechecked after the redirect/pairing UI fixes: `next` returned to the pairing page and device facts stayed visible after confirmation.
- DB verification confirmed registration pairing consumed, login pairing consumed, claim approved, binding active, account sessions verified, and both tickets linked to the same requester person/binding.
- Authenticated requester lifecycle check used isolated requester `requester-lifecycle-20260608-144009@example.test` and ticket `T-000649`: Browser MCP verified owned ticket detail controls, close changed the UI status to `Закрыта`, negative CSAT saved feedback, reopen changed the UI status to `Заявка в работе`, console errors were 0, and DB verification showed status transitions `queued -> closed -> in_progress`, one latest requester feedback row rating 2, one reopen event linked to that feedback, and requester person/binding set. The temporary live user was deactivated after verification.

- Authenticated requester catalog/form create check used isolated requester `requester-catalog-20260608113032@example.test`, owned device `catalog-live-113032` and ticket `e9741d40-73da-4176-8466-3fa3e00325c8`: Browser MCP verified `/app/requester` service catalog selection, dynamic required form fields, safe preview summary, unlocked create button, accepted ticket in the requester list, and 0 console errors. Remote DB verification confirmed the ticket is linked to the expected device/person/binding, has `service_code=workplace`, `offering_code=workplace.laptop_broken`, `request_form_key=breakage`, form data keys persisted, catalog ids present, requester status `accepted`, and 6 ticket events. The temporary live user was deactivated and its binding revoked after verification.
- Authenticated requester preview wrapper check used isolated requester `requester-preview-20260608130244@example.test`, owned device `preview-live-130244` and ticket `0d266a8e-9a9d-40f7-ac3b-4775c8ce998f`: Browser MCP verified `/app/requester` dynamic form fill, authenticated safe preview summary, unlocked create button, accepted ticket in the requester list, and 0 fresh console errors. Remote DB verification confirmed preview did not create an extra ticket (`ticket_count_for_live_person=1` after preview+create), the created ticket is linked to the expected device/person/binding, has `service_code=workplace`, `offering_code=workplace.laptop_broken`, `request_form_key=breakage`, form data persisted, catalog ids present, requester status `accepted`, and 6 ticket events. The temporary live user was deactivated and its binding revoked after verification.
- Authenticated requester knowledge suggestions reuse check used isolated requester `codex_stage2b_knowledge_20260608_2107@example.test`, owned device `codex-stage2b-kb-live` and ticket `80885bf6-38ab-42fa-8cc7-f0d9175216dd`: Browser MCP verified login to `/app/requester`, one owned registered device, requester-safe suggestions, opening the live article snippet, marking it not helpful, safe preview, and accepted ticket creation. Remote DB verification confirmed the ticket is linked to the expected device/person/binding, `knowledge_attempts` contains `viewed` and `not_helpful` attempts for the live knowledge item with `surface=requester_portal`, `/api/knowledge/feedback` stored `viewed`/`not_helpful` feedback rows, and the ticket has `ticket_created_after_view` feedback metadata with both attempts.
- Authenticated requester attachment check used isolated requester `codex_stage2b_attach_20260609083214@example.test`, owned device `stage2b-attach-20260609083214` and ticket `T-000653`: Browser MCP verified `/app/requester` login, exactly one owned device, owned ticket detail, file selection through the requester composer, immediate `/api/upload` result shown as a pending attachment, attachment-only send through `/api/web/requester/tickets/{ticket_id}/message`, rendered download link, browser-authenticated download 200 with matching file contents, and 0 console errors. Remote DB verification confirmed the artifact is bound to the expected ticket/device, the `chat_message` payload stores empty `text`, matching `attachment_refs`, normalized `attachments[0].name/url`, and the ticket requester/person/binding match the live requester. The temporary live user was deactivated and its binding revoked after verification.
- Authenticated requester public-claim check used isolated requester `codex_stage2b_claim-20260609-152039@example.test` and public ticket `T-000654`: Browser MCP verified `/app/requester` login, empty requester list before claim, visible `Привязать обращение` controls, successful claim with the existing public access code, immediate requester list refresh, opened ticket detail, fresh reload persistence and 0 console errors. Remote DB verification confirmed the ticket `requester_id` and `requester_person_id` match the live requester/person, `custom_fields.public_access.unbound=false`, one `requester_ticket_claimed` audit event exists and the event payload does not store the access code. The temporary live user was deactivated after verification.
- Authenticated requester no-device creation check used isolated requester `codex_stage2b_nodev_20260609153139@example.test` with no active bindings/devices and created ticket `T-000655`: Browser MCP/Playwright verified `/app/requester` login, no-device notice, required form completion, preview/submit, created-ticket notice, fresh reload persistence, and 0 console errors. Remote DB verification confirmed `requester_id`/`requester_person_id` match the live requester/person, `requester_binding_id IS NULL`, `requester_registration_status=no_device`, `requester_account_mode=browser_no_device`, `custom_fields.request_context=no_device`, `requester_account_context.account_mode=browser_no_device`, no `devices` row exists for the placeholder device id, and active binding count for the requester person is 0. Temporary no-device live users were deactivated after verification.
- Authenticated requester device detail check used isolated requester `codex_stage2b_device_20260609182934@example.test`, owned device `stage2b-device-detail-20260609182934` and ticket `T-000656`: Browser MCP/Playwright verified `/app/requester` login, owned device list, opening device detail, safe hostname/asset facts, recent requester-owned ticket, 0 console errors, and screenshot `artifacts/requester-stage2b-device-detail/requester-device-detail-live.png`. Direct browser-authenticated API verified `GET /api/web/requester/devices/{device_id}` returns 200 with the expected device id, `open_ticket_count=1`, recent ticket id `84b3404c-7730-4579-9445-6ca11e0b5eaa`, no raw discovery marker leak, and unknown device returns 404. Remote DB verification confirmed user/person/device/asset/binding/ticket links, ticket `requester_account_mode=confirmed_binding`, the raw discovery marker exists only in `registry_assets.discovery_payload`, and cleanup deactivated the temporary UI user plus revoked the live binding.
- Authenticated requester profile check used isolated requester `codex_stage2b_profile_20260609201103@example.test`, owned device `stage2b-profile-20260609201103`, active binding `89061f1c-ad5f-43cd-864e-8ee52b2f2c20` and pending claim `ee3eeb27-b133-49ca-a08e-a514e930c84b`: MCP/Playwright verified `/app/requester` login, opening profile detail, safe full name/phone/identity/device rendering, 0 console errors, and screenshot `artifacts/requester-stage2b-profile/requester-profile-live.png`. Browser-authenticated API verified `GET /api/web/requester/profile` returns 200, expected person id, identity providers `employee_id`/`ui_login`, one owned device, one active binding, one pending claim, `profile_policy.editable=false`, no raw `metadata_json`/`normalized_identifier`/marker leak, and `GET /api/web/requester/devices` count 1. Remote DB verification confirmed the UI user/person/device/binding/claim/identity links and raw marker exists only in `registry_person_identities.metadata_json`; cleanup deactivated the temporary UI user, revoked the binding, expired the pending claim and revoked active UI tokens.
- Authenticated requester shared-device privacy check used isolated requesters `codex_stage2b_shared_fixed_20260610140948_primary@example.test` and `codex_stage2b_shared_fixed_20260610140948_shared@example.test`, one shared device `d687a3bb-1726-4efe-8740-3b8d0e47fa48`, active primary binding `8ea63735-1f3d-49c1-bfc5-e8c089a5d183` and active shared-user binding `2f6a8b00-30c1-4a82-98f8-42feb1249c88`. Browser-authenticated requester API created tickets `T-000659` and `T-000660` through `/api/web/requester/tickets`; MCP/Playwright verified `/app/requester` shows only the current requester's own ticket, `GET /api/web/requester/tickets` returns only the own ticket, `GET /api/web/requester/devices/{device_id}` returns `open_ticket_count=1` and only own recent ticket, and direct foreign `GET /api/web/requester/tickets/{ticket_id}` returns 404. The only console errors were the intentional negative 404 fetches. Screenshot saved as `requester-stage2b-shared-privacy-live.png`. Remote DB verification confirmed both tickets share the device but have distinct `requester_person_id`/`requester_binding_id`, `requester_account_mode=confirmed_binding`, binding relationships `primary_user`/`shared_user`; cleanup deactivated four temporary UI users from the fixed run and pre-fix setup run, revoked live bindings and active UI tokens. Pre-fix setup contamination tickets `T-000657`/`T-000658` remain as live-test artifacts tied to deactivated users.
- Admin UI user/person linking adds `ui_users` to the admin registry snapshot and `POST /api/web/admin/registry/ui-users/{user_login}/link-person`, which creates a verified `RegistryPersonIdentity(provider='ui_login')`, refuses collisions with 409 and writes a registry admin event. `/app/admin/registry` People shows linked UI accounts and exposes a `UI login` action for explicit linking.
- Admin UI user/person linking live check used isolated run `codex_ui_link_20260610144922`: remote API created a temporary UI user/person link through `POST /api/web/admin/registry/ui-users/{user_login}/link-person`, `GET /api/web/admin/registry` returned the linked `ui_users` row, DB verification confirmed the verified `ui_login` identity, requester resolver matched the person, registry admin event stored the link audit, collision against another person returned 409 `IDENTITY_COLLISION`, and cleanup removed temporary UI users/people/identities/events plus revoked the temporary admin token. MCP browser verified `/app/admin/registry` People renders the `UI account` column and `UI login` action; screenshot saved as `admin-registry-ui-user-link-live.png`.

## Remaining Work

Stage 2B follow-up:

- No open Stage 2B admin-linking follow-up.

Stage 3:

- [x] `UserConsentRequest`;
- [x] requester consent APIs;
- [x] agent consent APIs;
- [x] operation consent integration;
- [x] atomic/idempotent consent decisions;
- [x] requester browser consent prompts;
- [x] agent GUI consent prompts;
- [x] Remote Assist canonical browser consent creation/approve dispatch integration.
- [x] Remote Assist technical agent start after browser approval: local GUI live run reached `/api/remote-assist/{session_id}/approve`, `agent_token_hash_present=true`, outbox delivered and WebRTC signaling started as agent.
- [x] Renewed full live audit evidence after 2026-06-11 hardening: browser screenshots, console/network, API and DB checks for pairing, requester lifecycle/privacy, operation consent and Remote Assist approve/deny.
- [x] Clean up or explicitly classify the stale pre-hardening pending Remote Assist consent without `requester_person_id` before final global DB integrity signoff.

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
- Role `user` has requester workspace permissions and implemented requester workspace flows; remaining gaps are tracked explicitly in this plan.
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
- `GET /api/web/requester/profile`

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

- show read-only requester profile facts in `/app/requester`;
- show verified identity aliases without raw `metadata_json` or `normalized_identifier`;
- show owned devices, active bindings and pending registration claims;
- expose an explicit read-only profile policy until profile edits have a governed change workflow.

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

- [x] Stage 3 requester prompts: add `/app/requester` pending consent panel, approve/deny actions and frontend tests.
- [x] Stage 3 agent prompts: add canonical `consent_id` API calls and GUI prompt polling for active account sessions.
- [x] Stage 3 Remote Assist integration: create `UserConsentRequest` for Remote Assist, start agent technical session only after canonical approval, preserve deny/expiry semantics.

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
- [x] Stage 2B lifecycle slice 1: authenticated requester ticket detail and message/chat are implemented through `/api/web/requester/tickets/{ticket_id}` and `/message`, with requester-safe messages/events and owned-ticket checks.
- [x] Stage 2B lifecycle slice 2: authenticated requester close/reopen/feedback are implemented through `/api/web/requester/tickets/{ticket_id}/close|feedback|reopen`, with owned-ticket checks before workflow/quality services and requester workspace controls.
- [x] Stage 2B create slice 3: authenticated requester owned-device create now reuses published Service Catalog selection, `request_forms` dynamic form validation, authenticated safe `POST /api/web/requester/tickets/preview`, request-template custom fields, priority-policy computation and explicit ticket catalog/reporting fields before `create_ticket_with_side_effects()`.
- [x] Stage 2B preview wrapper: authenticated `POST /api/web/requester/tickets/preview` now verifies requester ownership of browser-supplied `device_id`, delegates to the safe Service Catalog runtime without creating tickets/events, and feeds `/app/requester` preview before submit.
- [x] Stage 2B knowledge suggestions reuse: `/app/requester` now calls requester-safe `POST /api/knowledge/suggest`, displays safe suggestions in the authenticated create form, records viewed/helpful/not-helpful/deflected feedback, sends `knowledge_attempts` with ticket creation, and `/api/web/requester/tickets` stores sanitized attempts plus `ticket_created_after_view` knowledge feedback metrics behind the requester ownership boundary.
- [x] Stage 2B create verification: local backend/frontend tests, web build, deploy smoke, Browser MCP `/app/requester` create flow, console check and remote DB verification passed for requester catalog/form create, preview wrapper and requester knowledge suggestions reuse.
- [x] Stage 2B requester attachments: `/app/requester` uploads files through `/api/upload`, sends `attachment_refs` through owned-ticket `POST /api/web/requester/tickets/{ticket_id}/message`, permits attachment-only requester messages, renders returned attachment links, and keeps artifact resolution behind requester ownership/device-ticket checks.
- [x] Stage 2B public ticket claim: authenticated `POST /api/web/requester/tickets/claim-public` verifies an existing public access code, attaches the ticket to the logged-in requester/person, clears the public unbound marker, writes a `requester_ticket_claimed` audit event without storing the code, and `/app/requester` exposes the claim form before opening the claimed ticket.
- [x] Stage 2B no-device creation: authenticated requester create/preview now allows users with a resolved registry person and no registered devices to create a general request without browser-supplied `device_id`; the server assigns a placeholder `device_id`, stores `requester_account_mode=browser_no_device`, `request_context=no_device`, no binding id, and keeps requester visibility through `requester_person_id`; `/app/requester` enables the create form when no devices exist and omits `device_id` from the payload.
- [x] Stage 2B requester device detail: authenticated `GET /api/web/requester/devices/{device_id}` returns owned-only safe device facts, open ticket count, available actions and recent requester-owned tickets; `/app/requester` opens the detail panel from the owned devices list; live browser/API/DB verification passed.
- [x] Stage 2B requester profile: authenticated `GET /api/web/requester/profile` returns read-only safe requester profile detail, identity aliases, owned devices, active bindings, pending claims and profile edit policy; `/app/requester` opens the profile detail panel; live browser/API/DB verification passed.
- [x] Stage 2B shared-device privacy: authenticated requester bootstrap/ticket list/device detail/direct ticket access now has explicit regression coverage for two active users on one device, proving tickets stay scoped by requester person/binding instead of leaking by shared `device_id`; browser requester create now persists non-primary shared-user confirmed bindings only after the requester wrapper validates ownership. Live browser/API/DB verification passed.
- [x] Stage 2B admin: connected UI users to registry persons through explicit admin workflow and live-verified the admin Registry People UI/API/DB path.
- [x] Stage 3 design: confirmed canonical `UserConsentRequest`, requester/agent API ownership model, operation transition side effect boundary and deferred Remote Assist boundary.
- [x] Stage 3 tests: added consent ownership, idempotency, expiry and browser/agent decision coverage in `server/tests/test_user_consent_api.py`; local DB pytest execution currently times out in the existing harness even for older requester tests, while collection passes.
- [x] Stage 3 backend: implemented `UserConsentRequest`, migration `109`, requester/agent consent APIs, active binding/session checks, one pending consent per subject, atomic first-decision-wins transitions and operation approve/deny side effects.
- [x] Stage 3 frontend/agent: implemented requester consent center, agent prompt polling/dialogs and shared API client methods.
- [x] Stage 3 verification and docs: local tests/docs passed; remote Linux stand was deployed at `fec5b78d`; live API/DB checks passed for requester browser consent approve, agent consent approve with requester account-session headers, missing account-session denial, one pending requester UI consent, operation queue/outbox side effects, ticket timeline events and Remote Assist canonical deny. Browser MCP verified `/app/requester` shows the pending consent, approves it through the real UI, removes the panel and displays "Согласие подтверждено".

## Handoff

Stage 3 live verification is complete for the Browser / Requester / Agent identity and consent model. Stage 1, Stage 2A and Stage 2B live verification are complete enough for handoff; do not repeat them as the next item unless a regression needs to be checked.

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
- requester ticket detail/message and close/reopen/feedback lifecycle for owned tickets;
- requester owned-device catalog/form create with authenticated safe preview;
- requester knowledge suggestions reuse in authenticated create flow with sanitized attempts and deflection metrics;
- requester attachment upload/message/download through owned-ticket browser workspace controls;
- public ticket claim-to-account through `/api/web/requester/tickets/claim-public` and `/app/requester`;
- local backend/frontend coverage for owned visibility, shared-device privacy, foreign-device denial and foreign-ticket lifecycle denial.

Deferred / next:

- Stage 2B admin follow-up: explicit admin UI workflow for linking existing UI users to registry persons. Current resolver uses existing person identities.
- Stage 3 follow-up: none for the identity/consent-model scope. Viewer-side WebRTC offer/answer remains a separate media/viewer gate, not a blocker for requester/agent identity signoff.

Immediate next work:

1. Move to the next planned slice after Stage 3; run viewer-side WebRTC offer/answer only when the support viewer/media gate is explicitly in scope.

Before code changes, read the nested instructions for the target area:

- `server/AGENTS.md` for backend/auth/registry/ticket work.
- `pc_agent/AGENTS.md` for agent GUI/runtime work.
- `webapp/AGENTS.md` for requester browser UI work.

Do not stage unrelated existing dirty files or generated artifacts. Current known unrelated dirty surfaces include `.codex/config.toml`, `pc_agent/ui_gui/tickets_list_model.py`, `scripts/live_agent_uia_state_probe.py` and untracked files under `artifacts/` / `audit_artifacts/`.
