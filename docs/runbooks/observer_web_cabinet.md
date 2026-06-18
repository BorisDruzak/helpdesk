# Observer Web Cabinet Runbook

Use this runbook for active `observer.web_cabinet` integrity events.

## Scope

These events cover the web-first requester cabinet Observer overlay. They are diagnostics only; ticket state, routing and customer history remain owned by their domain services.

## Events

- `web_ticket_missing_ticket_context_v1` means a web-created requester ticket does not carry immutable `custom_fields.ticket_context.schema == ticket_context_v1`.
- `diagnostic_target_creator_fallback_on_behalf` means an on-behalf web requester ticket points diagnostics at the creator primary agent instead of the affected person's primary agent, no-primary-agent evidence, or ambiguous-target evidence.
- `forged_target_device_accepted` means requester/browser-supplied `target_device_id` appears to have been accepted into the flat dispatch alias while immutable `ticket_context` has a different server-owned diagnostic target.
- `profile_incomplete_normal_ticket_created` means a normal web requester ticket exists even though profile completion evidence says the profile gate should have blocked creation.
- `knowledge_audience_leak_on_behalf` means a requester-side Knowledge attempt on an on-behalf web ticket was persisted with affected/support audience or non-creator visibility instead of staying scoped to `creator_visible` / `creator`.
- `missing_customer_history_for_ticket` means a web requester ticket cannot be projected through Customer History with a support-safe `ticket_ref`, `ticket_created` event, `ticket` source and redaction report.
- `missing_observer_event_for_web_ticket_create` means a web requester ticket exists without a matching `root_kind=requester_web` trace from `source=requester_ticket_create`.

## Triage

1. Open `/app/admin/observer` and filter by `root_kind=requester_web`, `ticket_id` and the event `source` or `error_code` when present.
2. Open the support ticket detail and check `observer.web_flow` plus `observer.integrity_events`.
3. Check `server/web_api/requester_handlers.py` for the profile gate, preview and create paths.
4. Check `server/tickets/ticket_context.py`, `server/tickets/diagnostic_target.py` and `server/tickets/create_flow.py` when target resolution, forged target rejection or `ticket_context_v1` is wrong.
5. Check `server/knowledge/attempts.py`, `server/knowledge/suggestion_service.py` and `server/customer_history/sources.py` when on-behalf Knowledge audience/visibility evidence looks wrong.
6. Check `server/customer_history/projection_service.py` and `server/customer_history/sources.py` when Customer History projection evidence is missing.
7. Check `server/observer/web_event_writer.py` when traces are missing or payload redaction looks wrong.

## Safety

Do not backfill by manually editing deployed files or ticket rows. Fix the producer path, add focused tests, run the Observer integrity scan again and let the event resolve through the normal `ObserverIntegrityService` flow.
