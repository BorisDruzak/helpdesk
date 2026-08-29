# Observer known contamination

`quality/observer_known_contamination.json` is the source of truth for historical Observer integrity suppressions.

Rules:

- every active row must have an owner zone, linked issue, exact entity scope, reason, created date, mandatory expiry, review status and evidence path;
- `expires_at` is mandatory for active rows, and expired rows must stop suppressing integrity events;
- broad wildcard scope is not allowed; use exact `device_outbox`, `operation`, `ticket`, `device`, `command` or stable `dedupe_key` matches only;
- review the manifest before extending or renewing a suppression.

The 2026-08-29 staging review found no matching known-contamination rows, outbox `135`, integrity events for the two historical dedupe keys, or suppressed integrity events. The three TD-011 records — `device_outbox.id=135`, `p0:phantom_malformed_rows`, and `p6:historical_non_p6_agent_offline_active` — are therefore retained as historical metadata with status `retired`; they no longer seed a suppression.
