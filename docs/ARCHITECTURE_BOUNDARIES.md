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

## Required change checks

- A Helpdesk diagnostic change must preserve the Endpoint HTTP contract lock
  and the endpoint-only boundary tests.
- A change affecting Endpoint and Helpdesk together must verify both sides of
  the contract, including owner-scoped cancellation.
- Legacy Helpdesk agent routes must return `404` or `410`; `/ws_ui` must keep
  working.
