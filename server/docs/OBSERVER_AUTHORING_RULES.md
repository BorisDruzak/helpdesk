# Observer authoring rules

New Helpdesk observer evidence must be ticket-, process- or browser-scoped and
must not implement device transport, enrollment, command dispatch or agent
health. Use the versioned Endpoint contract for current endpoint operations.

Historical agent audit records are read-only. Do not add writers for
`agent_runtime_audit`, agent observer events, local delivery queues, or local WebSocket
state. Redact secrets and preserve UI authorization boundaries in every
observer payload.
