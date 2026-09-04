# Endpoint operation contract

Helpdesk does not connect to Endpoint agents or enqueue agent commands. For a ticket-bound diagnostic it exposes the typed route:

`POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`

During this cutover the supported capability is `endpoint.context.diagnostic.collect` and accepts an empty `params` object. The route creates a Helpdesk operation linked to the Endpoint Platform operation; its reconciler owns the remote request, state refresh and terminal result projection.

The browser-facing aliases use the same handler under `/api/web/support/tickets/{ticket_id}/diagnostics/capabilities/*`. Cancellation uses `POST /api/web/support/operations/{operation_id}/cancel`.

Compatibility boundaries: Helpdesk must not restore `/ws`, `device_outbox`, `ToolExecutionService`, `/api/tools/run`, or support `/tools/run` routes. Endpoint Platform remains responsible for agent transport, execution, package lifecycle and remote command delivery.
