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
  2). Transport failure, non-200 response, disabled integration or timeout map
  to `registry_unavailable`; they never trigger a direct ORM fallback.
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
- `GET /devices/{device_ref}/active-binding`
- `GET /devices/{device_ref}/account-status`
- `GET /requesters/{person_ref}/audience`
- `GET /requesters/{person_ref}/profile`
- `GET /directory/people?q={query}&limit={limit}`
- `GET /devices/{device_ref}/context`
- `GET /requesters/{person_ref}/history?limit={limit}`

Audience, profile, directory and history reads additionally receive the
verified caller context as `actor_ref`, `actor_role`, and, for requester
actors, `requester_ref`. Registry must authorize that context itself. Result
collections are capped by the Helpdesk contract (directory 50; audience and
history 100). A `404` maps to the operation's typed `registry_*_not_found`;
it is distinct from unavailable or invalid data.

No endpoint returns contact data, identities, sessions, Registry numeric IDs,
asset/serial data, ORM metadata, credentials or policy internals. Helpdesk sets
the response `source=external_authoritative` locally; Registry need not send a
source marker.

## Feature flags and shadow operation

`REGISTRY_PORT_MODE=local` remains the default. `external` requires both
`REGISTRY_EXTERNAL_BASE_URL` and `REGISTRY_EXTERNAL_SERVICE_TOKEN`; without
them, or with a non-HTTPS URL, it fails closed as
`registry_external_unconfigured`. In this PR `external` always keeps local
reads authoritative and performs non-blocking external comparisons. Direct
external authority requires a later explicit acceptance change.

Shadow evidence contains only operation name, `mismatch` and changed redacted
DTO field names. It never includes correlation IDs, values, references,
payloads, tokens or authorization decisions. Shadow calls are limited to reads. Commands,
registration, pairing, account sessions and login eligibility remain local in
this PR and do not issue shadow calls.

Breaking changes require `/v2`; additive platform fields are rejected until the
Helpdesk projection contract is explicitly extended and accepted.
