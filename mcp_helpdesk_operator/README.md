# Helpdesk Operator MCP

The MCP uses stdio from Codex and the Helpdesk support HTTP API over TLS. Its
credential represents an existing active Helpdesk operator. Ticket access follows
the current queue and Helpdesk permissions. Public replies, status changes
after start, device selection, and tool runs also require the current assignee.

## Setup

Install `mcp_helpdesk_operator/requirements.txt` into the Python environment
that Codex starts. Generate a grant as a Helpdesk service administrator for the
operator who authorized this integration. Use private directories outside the
checkout. On Windows use a directory whose ACL is restricted to the Codex user.

```powershell
python -m mcp_helpdesk_operator.credentials --operator OPERATOR_LOGIN --token-file C:/private/helpdesk-operator.token --grant-file C:/private/helpdesk-operator.grant.json --hours 24 --scope tickets.read --scope tickets.reply --scope tickets.transition --scope diagnostics.read --scope diagnostics.run
```

On the Helpdesk host set `HELPDESK_OPERATOR_GRANTS_FILE` to the absolute path
of a service-readable JSON array of grants. Each grant contains the SHA-256
digest, current Helpdesk login, UTC expiration, and the allowed scopes. Keep
the token file on the Codex workstation. Merge the new grant into the array
using the service configuration workflow. Publish grant-file changes atomically.
Helpdesk checks the current file and account on every request. Remove a grant
to revoke it. The service must be restarted when first setting or changing
the environment variable specifying the path.

In the Codex desktop app's `config.toml`:

```toml
[mcp_servers.helpdesk-operator]
command = "C:/path/to/python.exe"
args = ["-m", "mcp_helpdesk_operator.server"]
cwd = "C:/Users/admin-2/CodexProjects/pc_client"

[mcp_servers.helpdesk-operator.env]
HELPDESK_OPERATOR_BASE_URL = "https://helpdesk.sosnadmin.local"
HELPDESK_OPERATOR_TOKEN_FILE = "C:/private/helpdesk-operator.token"
```

Select the origin for the environment that owns the ticket. Python must trust
that Helpdesk origin's TLS certificate. Stdout is reserved for MCP messages.

## Operator workflow

- `ticket_get` resolves an exact number such as `T-000002` or a UUID and returns
  the UUID, assignee, current actions, recent timeline, and confirmed devices.
- `ticket_events` reads persisted messages and ticket changes in event ID order.
  Save `next_cursor` per ticket and use it as `after` on the next call. Continue
  while `has_more` is true. An initial `after: 0` reads the retained event history.
- `ticket_attachment_get` reads an attachment by the ID in the timeline and
  requires its association with the specified ticket. Raster images appear
  inline. Other files are returned as MCP binary resources, up to 8 MiB.
- `ticket_start`, `ticket_reply`, and `ticket_transition` use Helpdesk's normal
  workflow. Use one new UUID per intent and repeat the same UUID and payload if
  the HTTP outcome is unknown. A reply always specifies `public` or `internal`.
  For `ask_user` the message and status commit together. For `resolve` Helpdesk
  enforces the closure policy and reports whether confirmation was requested.
- If a diagnostic target is missing, `ticket_device_select` accepts a confirmed
  requester device from `ticket_get`. An approved inventory assignment with a
  current lease also qualifies. An existing different target requires the normal
  administrative mapping workflow.
- `ticket_tools`, `ticket_tool_run`, and `ticket_tool_result` reuse the published
  Endpoint Tools catalog, admission and result projection through Helpdesk.
  Run with the device reference, module key and version returned by the
  catalog, and poll with the returned run ID. Printer availability depends on
  the published module, Endpoint settings, and the device's agent.

## HTTP contract

Under `/api/web/support/tickets`, `GET /{ticket_id}` accepts the exact number
for lookup, and all other MCP paths use the resolved UUID. The additions are
`GET /{ticket_id}/events?after=0&limit=50`,
`GET /{ticket_id}/attachments/{artifact_id}`, and
`POST /{ticket_id}/diagnostic-device` with `{"device_id": "<registry UUID>"}`.
The paginated event feed projects the staff message and lifecycle fields.

The existing `POST /{ticket_id}/messages` uses `message_id`. The existing
`POST /{ticket_id}/status` accepts `operation_id` and returns the original
response on replay with the same body, ticket and actor. Reusing the UUID
for a different body returns HTTP 409. Receipts and actions commit in one
transaction. Operator credentials are accepted only on the documented
ticket routes and the three Endpoint Tool catalog/create/read routes.

## CUPS maintenance contract

Endpoint Platform provides separate CUPS service paths for queue configuration
(`/api/v1/devices/{device_id}/cups/queue-configurations`) and one test page
(`/api/v1/devices/{device_id}/cups/test-pages`). Read the operation at
`/api/v1/cups-operations/{operation_id}`. These paths require their own
Endpoint scopes and a compatible Linux agent. The Helpdesk MCP's Endpoint
Tools continue to use the diagnostic module catalog.

Queue configuration records the original and resulting state and updates one
local destination in place while keeping spooled and individually held jobs.
[cupsenable](https://openprinting.github.io/cups/doc/man-cupsenable.html)
[cupsaccept](https://openprinting.github.io/cups/doc/man-cupsaccept.html)

The print operation must use a fixed one-page document, one copy, and the
selected destination. Its journal should include the actor, device, queue,
caller key, and CUPS job ID when known. When submission was interrupted and
CUPS acceptance cannot be determined, the operation must return an unknown
outcome for reconciliation before another submission. Verify both actions on
a Linux test queue with jobs already pending.
[lp](https://openprinting.github.io/cups/doc/man-lp.html)
