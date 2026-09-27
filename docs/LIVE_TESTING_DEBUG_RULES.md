# Live validation and debugging rules

## Scope

Helpdesk validation covers the Helpdesk browser/API facade and its documented
Endpoint operation contract. Agent transport, agent GUI, command WebSockets,
ACK/NACK and local outbox checks belong to Endpoint Platform, not this
repository.

## Evidence before a fix

- Record the exact commit, environment and actor role.
- Keep browser-visible evidence separate from HTTP/API and database evidence.
- Redact tokens, credentials, cookie values and private keys.
- Use a new run identifier after a behavior-changing fix; do not treat prior
  records as proof of the current revision.

## Endpoint operation validation

- Verify the canonical ticket diagnostic route creates an Endpoint-backed
  operation facade and reconciles safe terminal evidence.
- Verify a facade-owned cancellation reaches Endpoint and a terminal result is
  not changed locally.
- Verify retired Helpdesk agent routes return `404` or `410` and `/ws_ui`
  remains available for browser notifications.
- A staging package or canary result is valid only when it identifies the exact
  Endpoint and Helpdesk revisions and the target environment.

## Completion gate

Run `python scripts/verify_workspace.py` and the focused contract/boundary
tests before claiming a Helpdesk cutover change is verified. Production rollout
requires the reviewed release procedure; never patch deployed directories
manually.

## Requester fixture lifecycle

Consent decision conflicts use consent-specific Russian messages. A missing
durable operation delivery (`OPERATION_DELIVERY_UNAVAILABLE`) directs the
requester to support; an operation state conflict asks them to refresh. Neither
error implies ticket closure or a successful consent decision. Unknown consent
conflicts retain a safe refresh message and never display backend details.

Requester fixture tests must follow the server lifecycle policy: a
`waiting_on_user` ticket permits a reply but cannot confirm a solution.
Confirmation requires `resolved` plus a pending confirmation marker; after
successful confirmation the fixture must report `closed` and remove the action.
These checks remain fixture regression evidence, not live backend acceptance.

## Admin shell notifications

The shared shell polls ticket notifications only. Retired Helpdesk agent enrollment
connection-request routes must not be polled or offered by its notification menu.
Agent enrollment remains Endpoint-owned; do not restore legacy routes to avoid 404s.

## Support read failures

Command-center and workspace-summary read failures return HTTP 503 with
`DB_UNAVAILABLE`, never a successful empty summary. Queue and summary reject
malformed `limit` values with `VALIDATION_ERROR`/400 before database access.
The operator UI distinguishes unavailable data from zero tasks and retains
previously loaded tasks with a visible warning on refetch failure.

Build the current web bundle before fixture browser checks: the fixture serves
compiled assets, so an older `dist` cannot verify current React source.
The degraded-read browser regression controls only the two failing reads;
its synthetic notification response covers a missing shared-fixture endpoint.
Expected HTTP 503 resource errors are recorded separately from unexpected
network responses and JavaScript errors. This remains fixture evidence and
does not substitute for exact-SHA staging backend/DB/WSS acceptance.
