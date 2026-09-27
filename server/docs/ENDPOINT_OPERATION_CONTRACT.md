# Endpoint operation contract

Helpdesk does not connect to Endpoint agents or enqueue agent commands. For a ticket-bound diagnostic it exposes the typed route:

`POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`

During this cutover the supported capability is `endpoint.context.diagnostic.collect` and accepts an empty `params` object. The route creates a Helpdesk operation linked to the Endpoint Platform operation; its reconciler owns the remote request, state refresh and terminal result projection.

The browser-facing aliases use the same handler under `/api/web/support/tickets/{ticket_id}/diagnostics/capabilities/*`. Cancellation uses `POST /api/web/support/operations/{operation_id}/cancel`.

Compatibility boundaries: Helpdesk must not restore `/ws`, `device_outbox`, `ToolExecutionService`, `/api/tools/run`, or support `/tools/run` routes. Endpoint Platform remains responsible for agent transport, execution, package lifecycle and remote command delivery.

## Local consent holds

The reconciler does not claim an operation in `waiting_consent`, `denied`, or
an unknown local state. It claims queued/sent/accepted/running operations and
continues monitoring `cancel_requested` operations.

Browser approval can release a local pre-dispatch hold only when the operation
has a persisted pending Endpoint link with its device reference, capability and
create idempotency key, and no remote operation reference. Unsupported legacy
subjects or an already submitted remote operation return
`OPERATION_DELIVERY_UNAVAILABLE`/409; the handler rolls back the consent decision
and ticket event. Denial remains available for historical waiting operations.
This local decision does not approve Endpoint Platform's own remote consent.

After a successful local approval, operation and consent state commit together.
An Endpoint transport failure retains the durable pending link and schedules a
retry. A fresh reconciler uses the same persisted create idempotency key.
