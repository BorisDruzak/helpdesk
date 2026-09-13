# Endpoint diagnostic playbooks

Helpdesk is a ticket and evidence facade. It does not dispatch commands to
agents, maintain a device outbox, or expose the retired `/api/tools/run`
surface.

## Supported ticket diagnostic

The only Helpdesk-projected diagnostic capability is
`endpoint.context.diagnostic.collect`. A support user starts it through:

`POST /api/web/support/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`

with an empty `params` object. Helpdesk validates ticket access, creates the
Endpoint operation facade and reconciles the terminal Endpoint result into
ticket evidence.

## Operational rules

- Endpoint Platform owns agent enrollment, delivery, command execution,
  cancellation and operation lifecycle.
- Helpdesk must fail closed when Endpoint is unavailable; it must not retry via
  a local agent transport.
- Cancel uses the Helpdesk operation facade and Endpoint's owner-scoped cancel
  contract. A terminal operation is never reopened locally.
- `GET /ws_ui` remains the browser/UI notification channel only.

The versioned request, response, evidence and cancellation rules are defined
in [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md).
