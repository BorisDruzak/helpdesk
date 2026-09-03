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
