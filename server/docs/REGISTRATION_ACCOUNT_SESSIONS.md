# Device registration account sessions

This document fixes the current production boundary for device registration and requester account sessions. It complements the registry CODEMAP and is intentionally focused on security policy and smoke checks.

## Identity layers

- Device identity is the agent machine identity: `device_id`, machine token, websocket handshake and technical health.
- Registration binding is the authoritative device-person link in `device_user_bindings`. `registry_assets.assigned_person_id` is derived from the active binding.
- Account session is the requester identity used by the local agent GUI for ticket actions. Agent machine tokens do not identify the requester.

## Browser pairing

Browser-to-agent account handoff is persisted in `device_browser_pairings` and starts from the agent endpoint `POST /api/registry/agent/browser-pairings`. The agent polls `GET /api/registry/agent/browser-pairings/{pairing_id}` for the result.

- Pairing rows store only `pairing_token_hash` and `pairing_code_hash`; raw pairing tokens/codes are returned only in the create response.
- A new pending pairing for the same `device_id` and purpose supersedes older pending rows.
- Manual code entry is handled by web-authenticated `POST /api/web/registry/browser-pairings/lookup` and `/app/device/pair`. The lookup is rate-limited, accepts the short-lived pairing code in the JSON body, rejects expired/consumed/superseded rows, and returns only `pairing_id`, `purpose`, `expires_at` and `next_url`.
- Browser confirmation is handled by web-authenticated `/api/web/registry/browser-pairings/{pairing_id}` plus `/login/confirm` or `/registration/confirm`; browser pages are `/app/device/pair`, `/app/device/login` and `/app/device/register`.
- Login confirmation resolves the web user to a registry person and requires an active primary/shared/responsible binding for the pairing device. Registration confirmation creates or updates the registration claim for the pairing device through `RegistrationService`.
- When registration policies require existing Registry values, `/app/device/register` uses `/api/registry/options` pickers and sends only selected `department_id` / `location_id` in the `/registration/confirm` JSON body. The server still validates those ids through `RegistrationService`; the browser cannot submit raw account-session tokens or override person/binding fields.
- Browser confirmation marks the pairing as confirmed but does not return an account `session_token` to the browser UI.
- The agent pickup creates/returns the account `session_token` once for login and marks the pairing `consumed`; later pickups return session metadata without the token. Registration pairing pickup consumes the pairing and leaves the agent on the account gate/account-state polling path.
- Agent auth can create or poll pairings only for its own UUID `device_id`.

## Session modes

- `confirmed_binding`: server-issued, verified by an active `device_user_bindings` row for the same device.
- `verified_other_account`: server-issued after admin approval of `device_account_login_requests`. It never creates a registration claim and never changes the active device binding.
- `registration_pending`: server-issued from a non-terminal registration claim. It is invalidated by rejected, expired, superseded or approved claim states. Claim approval also revokes the pending server session so admin session lists do not show an active pending registration next to the new confirmed binding session. The Qt agent GUI uses it to show and poll the pending registration gate; it must not open the normal ticket workspace before the device has a confirmed binding or an approved other-account session.

Agent GUI ticket actions must send the server-issued `session_id` and `session_token`. Client-supplied person, binding or account mode fields are not trusted without server validation.

## Ticket visibility policy

- `confirmed_binding` can see tickets for the same device when one of these matches: `requester_account_session_id`, `requester_binding_id`, or `requester_person_id`. This preserves historical owner tickets created before account sessions existed.
- `verified_other_account` can see only tickets created with that exact `requester_account_session_id`. It cannot see the registered owner's historical tickets.
- `registration_pending` visibility is retained server-side for historical/scoped pending tickets created by older clients. The current Qt GUI does not treat it as a ticket login and keeps the user in the account gate until approval.
- Staff/admin/support visibility remains controlled by staff routes and is not restricted by requester account sessions.

Agent requester actions requiring a valid account session include ticket create, preview, list, detail, snapshot, message, read cursor, upload, artifact download, close/resolution actions and requester-side attachments.

## Artifact and websocket boundaries

- Ticket-bound artifact download by an agent requires a valid account session and `can_view_ticket` access for the ticket.
- Staff UI downloads use staff authorization; public ticket-token downloads must match the token ticket scope.
- The websocket handshake must not expose open ticket ids or ticket details before account login. It may expose a diagnostic count only.

## Other-account warning

Tickets created from `verified_other_account` store:

- `requester_account_session_id`
- `requester_account_mode=verified_other_account`
- `requester_account_warning=ticket_created_from_other_account_on_registered_device`
- `custom_fields.requester_account_context` with declared account, phone, reason, verification method/status, and active registered owner/binding context.

The support ticket detail UI must show a visible warning: "Обращение создано с другого аккаунта на зарегистрированном устройстве."

## Lifecycle and TTL

Current implementation:

- `confirmed_binding` sessions live until logout, admin revoke, binding revoke, or `expires_at` if a deployment policy sets it. The default TTL is currently disabled.
- `verified_other_account` sessions live until logout, admin revoke, base binding revoke, or `expires_at`. The default TTL is 24 hours.
- `registration_pending` sessions are invalidated by terminal claim state and also receive `expires_at`. Approved claims actively revoke matching pending sessions; rejected/expired/superseded claims remain invalid through validation even before cleanup. The default TTL is 72 hours.

Follow-up: add a cleanup job for expired/revoked sessions and old account events.

## Ownership Transfer

Entering a verified other account is not an ownership transfer. It only creates a requester account session for ticketing on a registered device and always keeps the active device binding unchanged.

Planned transfer flow:

- create an explicit transfer claim/request;
- require admin approval;
- revoke or transfer old active binding and dependent sessions;
- activate the new binding;
- sync `registry_assets.assigned_person_id` from the new active binding.

## Live smoke checklist

### Confirmed owner

1. Device has active primary/responsible/shared binding.
2. Agent starts and shows account gate.
3. Login as registered owner.
4. Create ticket A.
5. List shows A, detail opens A, message/read/upload work.
6. Logout.
7. List/create/detail actions are blocked until a new account session is selected.

### Verified other account

1. Owner has ticket A.
2. Agent requests other-account login with login, phone and reason.
3. Admin approves request.
4. Agent polls request and receives session token once.
5. Login as verified other account.
6. Create ticket B.
7. Other account sees B and cannot see/open A.
8. Support UI shows the other-account warning on B with declared account, reason, phone, verification and registered owner.

### Registration pending

1. Device has no active binding.
2. Submit registration form.
3. Server creates a `registration_pending` account session.
4. Agent remains on the account gate, hides the repeat registration button, and polls account-state.
5. Approve/reject the claim and verify the pending session invalidates or the agent shows the confirmed registered account login.

### Revoke

1. Login with a valid account session.
2. Admin revokes the account session or binding.
3. Agent refresh detects invalid session and returns to account gate.
4. Ticket actions are blocked.

### Artifact

1. Upload attachment to own ticket.
2. Download works with valid account session.
3. Wrong other-account session cannot download.
4. No session cannot download.

### Websocket/handshake

1. Start agent without account login.
2. Confirm no ticket ids/details are visible before account gate login.
3. After login, ticket list loads through HTTP with account session.
