# Runtime execution boundary

Endpoint Platform owns endpoint capability execution, delivery, cancellation
and typed results. Helpdesk creates a ticket-facing operation facade and stores
safe references/evidence only. There is no Helpdesk fallback transport,
DeviceOutbox delivery, local `run_tool`, or agent runtime.
