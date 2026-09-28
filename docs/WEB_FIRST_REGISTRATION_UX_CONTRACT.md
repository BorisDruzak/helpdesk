# Requester and device visibility contract

Helpdesk keeps authenticated requester and administrator web workspaces.
Account registration uses login, password and repeated password only. The public
`GET /api/web/session/capabilities` projects the server registration flag; disabled
registration leaves login available and shows a clear state on the register route.
Account registration is separate from device binding and Endpoint Agent enrollment.
Retired Helpdesk browser pairing and account-session issuance remain unavailable.

| Route | Purpose | Authority | Evidence |
| --- | --- | --- | --- |
| `/app/requester/devices` | Read the requester's existing device bindings and open device binding. | Authenticated Helpdesk requester. | Redacted Registry device projection. |
| `/app/requester/devices/link` | Enter an Endpoint one-time device code. | Authenticated requester with a complete RegistryPerson profile; Endpoint verifies possession, Registry decides ownership. | Registry binding/claim and bounded audit, never the code. |
| `/app/requester/new` | Create a Helpdesk ticket. | Authenticated requester and Helpdesk ticket policy. | Ticket/audit record and Endpoint-backed diagnostic facade where applicable. |
| `/app/admin/registry` | Administer people, bindings, registration claims, profiles and password-reset requests. | Helpdesk RBAC. | Registry audit event with a redacted before/after projection. |

Endpoint Platform alone owns agent enrollment, agent connectivity and all
device-control workflows. Helpdesk consumes only the documented Endpoint
operation contract and preserves `/ws_ui` browser notifications.

Requesters and administrators must never receive raw credentials, tokens,
internal identifiers, endpoint operation secrets, or database metadata. A
retired Helpdesk legacy endpoint must return `404` or `410`.

## Device binding

The existing Windows Endpoint tray offers copy, new-code and open-Helpdesk actions.
Six ASCII digits (`123456` or `123-456`) expire after ten minutes and redeem once.
Browser links put the code only in a fragment. The application captures and removes
that fragment before auth routing, retains the code only in memory across login or
profile completion, and submits it only on the user's explicit action. Reloading
the application loses the code; no storage, cookie, query parameter or browser log
retains it. Logout and successful redemption clear it.

`POST /api/web/requester/devices/link` uses existing session, same-origin/CSRF and
HTTPS Endpoint adapter policies. It resolves a complete RegistryPerson before the
S2S redemption. The exact provider SHA and canonical OpenAPI hash are pinned in
`integration/endpoint_contract.lock.json`; the dedicated service scope is
`device-binding.redeem`. Endpoint does not assign a Helpdesk owner.

Registry migration `146` owns an exact, unique Endpoint-to-local-device mapping.
A new verified device receives a marked Registry projection. Existing legacy IDs,
hostnames and diagnostic ticket targets never establish this mapping. An ID
collision fails closed for administrator review. The person and device rows are
locked for activation; person status is refreshed after the provider call.
Free ownership activates through canonical Registry policy, same-owner primary
binding is idempotent, and existing/shared/ambiguous ownership creates an audited
claim for administrator review without replacing owners. The source and
verification marker are `endpoint_possession_proof`.

## Tickets

Normal forms allow tickets without a computer by default. The historical policy
key `available_without_agent_binding` remains compatible; explicit `false` still
requires a selected device. Device-picker fields are optional for forms allowing
no-device submission. The requester selector preselects an available primary computer. Choosing
“Без компьютера” sends `device_scope: "none"` through preview, create and diagnostic context,
preventing automatic primary-device fallback. A selected device must pass existing
requester ownership authorization. An exact Registry mapping plus a fresh,
non-retired Endpoint projection is required before retaining a diagnostic reference.
Routing, SLA/OLA, chat, consent, resolution and requester-confirmed closure keep
their canonical workflows.

Live First Wave acceptance uses the isolated staging host and Windows test VM.
ALT Linux Agent binding acceptance is intentionally excluded. Unit and fixture
browser checks do not replace real tray, WSS, consent or lifecycle acceptance.
