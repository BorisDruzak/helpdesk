# Registration and requester access after legacy cutover

Helpdesk no longer provides browser pairing, local-agent requester login, or
device account-session runtime. The historical database tables and columns
remain temporarily for rollback and audit only; no current route writes or
authorizes through them.

## Current boundary

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
