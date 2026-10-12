# Endpoint tools workspace

The device-scoped published Endpoint catalog is consumed through the frozen
module DTOs and the read/execute-only `EndpointModulesPort`. No authoring scopes
or provider runtime imports belong to Helpdesk.

`app/repos/endpoint_tool_runs_repo.py` persists immutable module, safe context
collection and diagnostic intents. `endpoint_tool_runs` marks ownership of the
existing Operation / EndpointOperationLink lifecycle. Marker-less historical
module links are never eligible for the new worker. Browser replay keys are
scoped by actor and ticket; changed inputs or device identity produce a conflict.
Remote keys separate modules and context collections while preserving the
diagnostic prefix. Leases use unique claim tokens and short transactions; HTTP
calls occur outside them. Accepted snapshots remain local after remote expiry.

Migration 148 reuses the module columns already introduced by 142 and only adds
context linkage and the ownership table. It is currently based on local/main146;
before staging release it must follow the accepted Guided Request Studio147.
Do not apply this candidate to the current staging147 or create a second head.

The `web_api/endpoint_tool_handlers.py` BFF provides ticket-scoped catalog, run
history/detail and six-step collection routes under
`/api/web/support/tickets/{ticket_id}/endpoint-tools`. Existing authenticated
ticket/queue access and permissions apply, with read access for auditors and
execution for support/admin. Cookie mutations retain the shared same-origin CSRF
middleware. Responses are no-store and bounded to 1 MiB. Provider auth failures
are 502 errors, preserving the human session. The default-off
`ENDPOINT_TOOLS_WORKSPACE_ENABLED` controls admission, never worker resumption.
Catalog primitives cache for 60 seconds and exact-device pages for 5 seconds;
mutations bypass both caches and validate the exact published version afresh.

POST `.../runs/{run_id}/passport-evidence` accepts only a selected step sequence.
The server validates the closed result and immutable provenance, creates one
deterministic DiagnosticEvidence and copies the safe payload into the passport's
own metadata snapshot. Ticket locks serialize repeated attachments. Queued or
missing results cannot be attached; a negative safe result keeps its failure
status. Neither evidence nor passports depend on Endpoint's result retention.

The support bootstrap advertises `endpoint_tools_workspace` only when enabled.
`webapp/src/features/endpoint-tools` replaces the diagnostic panel composition
for that feature. Its forms consume server-derived input controls; readonly
result types are generated from the accepted public operation schema, including
the closed 21-primitive result union. Unsupported controls are disabled. A named
container switches parameters/result to two columns at640px. Query identity
includes account, ticket, device, exact module/version and selected run; older
responses cannot replace a newer selection. Results display their own collection
time and request parameters. Browser intent keys survive an uncertain response
and must be saved before dispatch; storage failure prevents the launch.
