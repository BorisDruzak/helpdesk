# Helpdesk architecture boundaries

This document records the post-cutover ownership boundary. It supersedes the
former Helpdesk agent-transport and Protocol V3 descriptions.

| Area | Owner | Helpdesk responsibility | Forbidden in Helpdesk |
|---|---|---|---|
| Agent enrollment, gateway, command delivery and execution | Endpoint Platform | Consume versioned HTTP contracts only | `/ws` agent endpoint, device outbox, command sender, agent tokens |
| Ticket diagnostics | Endpoint Platform + Helpdesk | Authorize ticket access, create operation facade, reconcile safe evidence | Local `run_tool` dispatch or fallback execution |
| Operation cancellation | Endpoint Platform | Forward a facade-owned cancel request and reflect the result | Reopening or completing an Endpoint operation locally |
| Browser notifications | Helpdesk | Retain `/ws_ui` for authenticated UI events | Agent WebSocket multiplexing |
| Helpdesk deployment | Helpdesk | Independent systemd, PostgreSQL, Unix user and Nginx resources | Sharing Endpoint runtime directories, database or service account |

The canonical diagnostic and cancellation contract is
[server/docs/ENDPOINT_OPERATION_CONTRACT.md](../server/docs/ENDPOINT_OPERATION_CONTRACT.md).

## Required change checks

- A Helpdesk diagnostic change must preserve the Endpoint HTTP contract lock
  and the endpoint-only boundary tests.
- A change affecting Endpoint and Helpdesk together must verify both sides of
  the contract, including owner-scoped cancellation.
- Legacy Helpdesk agent routes must return `404` or `410`; `/ws_ui` must keep
  working.
