# Observer Runbook: Account Boundary

## Meaning

The Observer detected a successful requester/public mutation or projection anomaly that crossed account-session, public access, or role boundaries.

## Immediate Checks

- Identify `actor_role`, target ticket, account session and public token state.
- Confirm whether the event records a successful mutation, not merely a denied attempt.
- Check requester/public response serializers for forbidden internal fields.

## Safe Queries

- Query audit rows by exact `ticket_id`, `actor_role`, and event id.
- Redact tokens, cookies, public access hashes and requester message text.

## What Not To Do

- Do not paste raw session, cookie, public token or requester message content into observer evidence.
- Do not add automatic product-side mutation to “fix” the row.

## Escalation

Escalate as critical for wrong-account mutation success, public revoked access success, or internal fields visible to requester/public.

## Related Bugs

Inspired by P2/P3 account-session and requester/public boundary regressions.

## Cleanup and Suppression

Security boundary events should rarely be suppressed. If suppression is required, make it temporary and exact.
