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
