# Registry Platform API v1

Status: PR-9 read-integration contract. These are Registry Platform endpoints,
not Helpdesk routes. Helpdesk's local Registry data remains authoritative until
the command/auth acceptance cutover.

## Transport and security

- Base URL is `REGISTRY_EXTERNAL_BASE_URL` and must use `https`; all paths
  below are rooted at `https://<registry-platform>/v1/helpdesk`. Helpdesk
  refuses a non-HTTPS URL before constructing a Bearer request.
- Helpdesk sends `Authorization: Bearer <service-token>`, the fixed
  `X-Registry-Service-Scope: registry.helpdesk.read.v1`, and one fresh opaque
  `X-Correlation-ID` per request. The service validates both caller identity
  and scope. Tokens, headers, URLs, query values and response bodies must not
  be logged by either service.
- `REGISTRY_EXTERNAL_TIMEOUT_SECONDS` is bounded to 0.05–10 seconds (default
  2). Transport failure, an undocumented non-200 response, disabled integration
  or timeout map to `registry_unavailable`; they never trigger a direct ORM
  fallback. The correlated on-behalf authorization and observer
  requester-profile-completion `404` envelopes described below are the only
  documented non-200 projection envelopes.
- Every success is exactly `{ "data": { ... }, "correlation_id": "opaque" }`;
  the returned opaque ID must exactly match the one sent by Helpdesk.
  Helpdesk accepts only the redacted DTO fields documented below; unexpected,
  malformed or over-limit data maps to `registry_projection_invalid`.
- References and correlation IDs are opaque. Do not parse, normalize, expose
  them to untrusted clients, or place them in diagnostics.

## Read endpoints

`GET /availability` returns a bounded health projection. The following paths
return only frozen, redacted `RegistryPort` DTOs:

- `GET /requesters/{person_ref}/snapshot`
- `GET /requesters/{person_ref}/ticket-participant`
- `GET /devices/{device_ref}/active-binding`
- `GET /devices/{device_ref}/account-status`
- `GET /requesters/{person_ref}/audience`
- `GET /requesters/{person_ref}/profile`
- `GET /observer/requesters/{person_ref}/profile-completion`
- `GET /directory/people?q={query}&limit={limit}`
- `GET /requesters/{creator_ref}/on-behalf/candidates`
- `GET /requesters/{creator_ref}/on-behalf/{affected_ref}/authorize`
- `GET /devices/{device_ref}/context`
- `GET /inventory-quality`
- `GET /requesters/{person_ref}/history?limit={limit}`

Audience, profile, directory, history and on-behalf reads additionally receive the
verified caller context as `actor_ref`, `actor_role`, and, for requester
actors, `requester_ref`. Registry must authorize that context itself. Result
collections are capped by the Helpdesk contract (directory 50; audience and
history 100). For single-subject requester/device reads, a `404` maps to the
operation's typed `registry_*_not_found`; it is distinct from unavailable or
invalid data. The two-subject on-behalf authorization endpoint instead returns
a correlated exact `404` envelope whose `data` is `{ "status": "not_found",
"code": "registry_on_behalf_creator_not_found"|
"registry_on_behalf_affected_not_found" }`; unknown codes, additional fields
or correlation mismatch are invalid projections.
`GET /inventory-quality` has no not-found state: its `404` and every other
non-200 response map to typed unavailable.

`GET /observer/requesters/{person_ref}/profile-completion` is the one
observer-only profile-gate read. Helpdesk creates its frozen
`RegistryObserverReadContext(source="observer.web_cabinet")` only in trusted
observer composition; browsers cannot supply it. Its success `data` object has
exactly `person`, `complete`, `blocks`, `status` and `missing_field_keys`.
`person.external_id` must match the requested opaque reference exactly;
`missing_field_keys` is bounded and deduplicated. The projection contains no
profile values, labels, identities, sessions, policy internals or ORM metadata.
An archived person remains evaluable for this observer audit; only an absent
person is not-found. The observer requester-profile-completion read returns a
correlated exact `404` envelope whose `data` is exactly `{ "status":
"not_found", "code": "registry_requester_not_found" }`; unknown codes,
additional fields or correlation mismatch are invalid projections. Unavailable
or invalid outcomes are handled as redacted observer integrity degradation,
never as a completed profile gate.

No endpoint except the purpose-bound ticket-participant and on-behalf candidate
reads returns the already exposed contact fields. No endpoint returns identities, sessions, Registry numeric IDs,
asset/serial data, ORM metadata, credentials or policy internals. Helpdesk sets
the response `source=external_authoritative` locally; Registry must not send a
source marker.

The on-behalf endpoints are purpose-bound requester reads; they do not widen
`GET /directory/people`, which remains support/admin-only. Both receive the
server-owned policy snapshot as `policy_allowed=true|false`,
`policy_scope={safe-code}` and `policy_reason_required=true|false`. The
candidate endpoint additionally receives `q` (trimmed, 1–120 characters). Its
success `data` is exactly `{ "items": [...] }`, capped at 10, where each item
has exactly `person`, `display_name`, `full_name`, `email`, `department`,
`department_label`, `location` and `location_label`; refs are opaque and
department/location plus their labels may be null. It never returns phone,
identities, account/session, binding, device, metadata or primary-agent data.

Authorization receives optional `lookup` (trimmed, 1–240 characters) only as
exact-selection evidence for `policy_scope=exact_search_only`. Allowed `data`
is exactly `{ "status": "allowed", "code":
"registry_on_behalf_allowed", "affected": { "external_id": ... } }` and its
affected ref must match the requested path exactly. Denial `data` is exactly
`{ "status": "denied", "code": <safe-code> }`; stable policy codes are
`registry_actor_forbidden`, `registry_on_behalf_not_allowed` and
`registry_on_behalf_scope_denied`. A missing creator/affected row maps to the
typed not-found code for that operation; malformed or additional fields map to
`registry_projection_invalid`. Registry owns creator lifecycle,
same-department/direct-report and exact-search evaluation. Helpdesk constructs
the actor/creator tuple only from verified auth plus its server identity
resolver and the policy only from resolved server form configuration; browser
role, creator and policy values are never forwarded as authority.

`GET /requesters/{person_ref}/ticket-participant` exists only to preserve the
already persisted `ticket_context_v1` participant snapshot. Its `data` object
has exactly `person`, `display_name`, `full_name`, `email`, `department` and
`location`; the latter two are nullable opaque-ref objects and the three text
fields are nullable. The returned `person.external_id` must exactly match
`person_ref`. Only an absent person row returns `404`; an existing archived,
disabled, inactive or merged row remains readable for compatibility with the
already persisted ticket snapshot. Malformed, mismatched or additional fields
are `registry_projection_invalid` before Helpdesk injects provenance.

`GET /inventory-quality` returns only
`{ "active_pc_without_location_count": <non-negative 32-bit integer> }`.
It is the aggregate for active `pc` assets whose `location_id` is null; it
contains no asset, person, device, location or other entity identifier. A
malformed count is `registry_projection_invalid`; transport failure remains
typed unavailable.

## Feature flags and shadow operation

`REGISTRY_PORT_MODE=local` remains the default. `external` requires both
`REGISTRY_EXTERNAL_BASE_URL` and `REGISTRY_EXTERNAL_SERVICE_TOKEN`; without
them, or with a non-HTTPS URL, it fails closed as
`registry_external_unconfigured`. In this PR `external` always keeps local
reads authoritative and performs non-blocking external comparisons. Direct
external authority requires a later explicit acceptance change.

Shadow evidence contains only operation name, `mismatch` and changed purpose-bound
DTO field names. It never includes correlation IDs, values, references,
payloads, tokens or authorization decisions. Shadow calls are limited to reads.
On-behalf authorization is a read-only decision comparison: its external
result may report only a redacted mismatch and never replaces the local
authoritative decision. Commands,
registration, pairing, account sessions and login eligibility remain local in
this PR and do not issue shadow calls.
The observer profile-completion read follows the same local-authoritative
shadow rule: comparison evidence contains only the operation and changed
projection field names, never person refs, missing-field values or response
payloads.

Breaking changes require `/v2`; additive platform fields are rejected until the
Helpdesk projection contract is explicitly extended and accepted.

## Command and eligibility boundary

This is a read-only integration contract. The separate
`REGISTRY_PLATFORM_COMMANDS_V1.md` specifies the future command and
eligibility acceptance gate. It does not activate external authority: commands,
registration, pairing, account sessions and UI-login eligibility remain local
until per-operation external acceptance evidence permits a later explicit
cutover.
