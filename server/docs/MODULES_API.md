# Modules and diagnostics boundary

Helpdesk may render capability metadata and ticket-scoped, safe diagnostic
evidence. It does not install modules, execute agent tools, manage rollouts or
send device commands. Those operations belong exclusively to Endpoint Platform.

Server-side connectors and read-only observer queries remain Helpdesk features
when they do not execute on an endpoint. Endpoint operation references and
redacted result snapshots are defined by [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md).
