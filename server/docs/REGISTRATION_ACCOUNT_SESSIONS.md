# Registration and requester access after legacy cutover

Helpdesk no longer provides browser pairing, local-agent requester login, or
device account-session runtime. The historical database tables and columns
remain temporarily for rollback and audit only; no current route writes or
authorizes through them.

## Current boundary

- Login/password registration creates only a Helpdesk account. Endpoint Agent
  enrollment is independent. See `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`.
- Endpoint device challenges prove possession; the authenticated
  `/api/web/requester/devices/link` flow establishes a Person↔Device relationship
  only through canonical Registry policy. It never writes legacy pairing/session
  tables. Migration `146` persists the unique device mapping, and conflicting
  ownership is retained for administrator review.

- Browser requester actions use the authenticated web identity.
- Agent-originated requester actions use the authenticated device's active
  Registry binding and only access tickets in that binding's requester scope.
- Manual agent ticket attachments use the same active-binding check. Runtime
  operation artifacts remain scoped by their Endpoint operation and device.
- Staff and support access remains governed by normal Helpdesk RBAC.

## Removed surfaces

The following Helpdesk routes and flows are retired and must return `404` or
`410`: account-session creation, validation, logout and revocation; other
account login requests; browser pairing create, lookup, confirmation and
pickup; and admin account-session lists, timelines and bulk actions.

## Verification

Use `server/tests/test_no_legacy_endpoint_routes.py` together with the
binding-access tests before a release. Do not restore the old session service
or pairing repository as a compatibility fallback; preserved history is not
runtime authority.
