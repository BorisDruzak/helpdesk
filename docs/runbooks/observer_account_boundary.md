# Observer Runbook: Account Boundary

## Meaning

The Observer detected a successful requester/public mutation or projection anomaly that crossed authenticated web-requester, public-access, or role boundaries.

## Immediate Checks

- Identify `actor_role`, target ticket, authenticated requester state and public token state.
- Confirm whether the event records a successful mutation, not merely a denied attempt.
- Check requester/public response serializers for forbidden internal fields.

## Safe Queries

- Query audit rows by exact `ticket_id`, `actor_role`, and event id.
- Redact tokens, cookies, public access hashes and requester message text.

```sql
SELECT id, device_id, event_type, severity, ticket_id, actor_role,
       details_json, created_at
FROM agent_runtime_audit
WHERE event_type IN (
  'account_boundary_mutation_success',
  'public_boundary_mutation_success',
  'requester_projection_forbidden_field'
)
  AND ticket_id = :ticket_id
ORDER BY created_at DESC
LIMIT 20;
```

## Safe Actions

- Confirm the event is a successful mutation/projection leak, not only a denied attempt.
- Re-run the negative route test with a clean marker after preserving evidence.
- Fix the authorization or serializer boundary before suppressing anything.

## What Not To Do

- Do not paste raw session, cookie, public token or requester message content into observer evidence.
- Do not add automatic product-side mutation to fix the row.
- Do not downgrade wrong-account or revoked-public-access success unless root cause proves the event is an Observer false positive.

## Escalation

Escalate as critical for wrong-account mutation success, public revoked access success, or internal fields visible to requester/public.

## Related Bugs

Inspired by requester/public boundary regressions.

## Cleanup and Suppression

Security boundary events should rarely be suppressed. If suppression is required, make it temporary and exact.
