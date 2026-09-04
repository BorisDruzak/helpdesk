# Observer layer

Helpdesk Observer projects ticket workflow, process evidence and browser-facing
integrity signals. Endpoint Platform owns all live agent transport, enrollment,
command delivery, rollout and device telemetry.

`agent_runtime_audit` and related pre-cutover tables are retained solely as
read-only historical evidence. Helpdesk must not write them or infer live agent
availability from them. Current operation diagnostics are linked through the
Endpoint operation contract in [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md).

The active integrity checks are ticket operation lifecycle, account boundary,
module/toolset governance and browser-cabinet checks. UI realtime is served only
through `/ws_ui`.
