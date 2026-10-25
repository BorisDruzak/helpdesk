# Helpdesk architecture boundaries

This document records the post-cutover ownership boundary. It supersedes the
former Helpdesk agent-transport and Protocol V3 descriptions.

Production Readiness v1 has one active Helpdesk server process, one application
worker and one proxy backend. Process-local UI state is an open architectural
limitation (SCALE-036), accepted only within this single-instance scope. HA,
active-active, multiple workers/backends and horizontal scaling are prohibited;
a topology change reopens the release blocker. See the deployment topology
evidence and fail-closed gate in
[the host runbook](../server/docs/RUNBOOK_HELPDESK_ENDPOINT_HOST.md).

| Area | Owner | Helpdesk responsibility | Forbidden in Helpdesk |
|---|---|---|---|
| Agent enrollment, gateway, command delivery and execution | Endpoint Platform | Consume versioned HTTP contracts only | `/ws` agent endpoint, device outbox, command sender, agent tokens |
| Ticket diagnostics | Endpoint Platform + Helpdesk | Authorize ticket access, create operation facade, reconcile safe evidence | Local `run_tool` dispatch or fallback execution |
| Operation cancellation | Endpoint Platform | Forward a facade-owned cancel request and reflect the result | Reopening or completing an Endpoint operation locally |
| Browser notifications | Helpdesk | Retain `/ws_ui` for authenticated UI events | Agent WebSocket multiplexing |
| Helpdesk deployment | Helpdesk | Independent systemd, PostgreSQL, Unix user and Nginx resources | Sharing Endpoint runtime directories, database or service account |

The canonical diagnostic and cancellation contract is
[server/docs/ENDPOINT_OPERATION_CONTRACT.md](../server/docs/ENDPOINT_OPERATION_CONTRACT.md).

## Diagnostic UI availability

For an Endpoint-backed diagnostic, Helpdesk must not use the legacy inventory
`device.online` snapshot as an availability gate. The Endpoint operation
boundary remains the authority for readiness, authorization, and execution;
legacy tools may continue to use the legacy device state.

## Support device presence and requester refresh

For a ticket with `endpoint_device_ref`, support reads current presence through
`EndpointPort.read_device_presence`, backed by the published
`GET /api/v1/devices/{device_id}/context` contract (`context.read`). The exact
device reference must match. Connection state and last-seen time come from
Endpoint, never from Helpdesk's retired connection map or local agent cache.
Provider errors produce `unknown`, without an offline signal or a fallback
version/timestamp. The published presence contract does not supply agent version.
This read never collects context or dispatches an agent operation. Unlike the
Operations API, the Context API does not require a correlation response header.

Requester bootstrap, ticket list/detail and pending-consent queries refresh
every 10 seconds in a visible tab and immediately on focus/reconnect. Hidden
tabs do not poll. Own actions continue to invalidate the same scoped query keys;
background reads do not replace form drafts or require page reloads.

## Required change checks

The default support workspace is a compact presentation of the existing support
API, not an alternate workflow engine. Public replies require started work and
the assigned operator (or an authorized administrator), checked under the same
ticket lock as status transitions. The UI's action projection never replaces
server permission, ownership, SLA or closure checks. Technical panels remain
reachable from additional actions. See [support workflow](SUPPORT_WORKSPACE.md).

- A Helpdesk diagnostic change must preserve the Endpoint HTTP contract lock
  and the endpoint-only boundary tests.
- A change affecting Endpoint and Helpdesk together must verify both sides of
  the contract, including owner-scoped cancellation.
- Legacy Helpdesk agent routes must return `404` or `410`; `/ws_ui` must keep
  working.

## Session, attachments and capacity guards

Existing UI tokens use the current active user's role on verification. Raw
internal WebSocket rooms require an operator role and ticket visibility; delivery
rechecks session validity and ticket scope. Requester refresh continues to use
the scoped HTTP polling described above.

The browser session owns its query client. Identity, role or authorization
changes retire that client and remount its consumers, isolating pending query
and mutation callbacks. Same-session refresh preserves cached data and drafts.
Ticket uploads and message completions also retain their original ticket and
composer generation, so they cannot change a subsequently selected ticket.

Increasing active assignment load is checked under the common operator row
lock. Existing-ticket commands lock ticket before operator, while bulk commands
prelock their complete sorted ticket set. UI availability remains a read-only
projection and does not authorize a command.

Staff attachment reads and writes use canonical ticket visibility. Upload files
are removed on known precommit rejection/failure. A failed or cancelled commit
can have an unknown durable result: retain its file and reconcile the logged
artifact ID instead of deleting potentially committed data.
