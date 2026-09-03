# Legacy UI removal design

## Goal

Retire the server-rendered Helpdesk web shells and their `legacy`/`_shell`
fallback mechanism.  Historic entry URLs remain stable only as redirects to
their React `/app/*` replacements.

## Scope

The removal covers the legacy login, admin, support, requester help and
public ticket shells; their CSS/JavaScript, embedded module/form workbenches,
server handlers, registered asset routes, cutover flags and legacy browser
signoff checks.  It does not remove public queue, technical/debug pages,
database migrations, protocol compatibility, or non-UI uses of the word
"legacy".

## Behaviour

- `/login`, `/admin` and `/support` always redirect to `/app/login`,
  `/app/admin` and `/app/support`.
- `/help`, `/ticket.html` and `/ticket/{ticket_id}` always redirect to their
  existing requester React paths. Safe query parameters survive; `legacy` and
  `_shell` are discarded.
- Old shell assets and standalone legacy-workbench endpoints are not
  registered and therefore return HTTP 404.
- The server no longer uses a Webapp cutover flag or bundle-presence fallback
  to revive the removed UI. The existing `/app` asset handler remains the
  canonical React delivery path.

## Safety

The change preserves user-facing entry URLs and ticket identifiers, leaves
all typed APIs and domain behaviour untouched, and uses route-level tests
plus browser signoff to prove the new contract.  The separate public queue and
technical HTML pages remain explicitly out of scope for this change.
