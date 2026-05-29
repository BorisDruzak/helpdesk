# Observer Runbook: Governance Integrity

## Meaning

The Observer detected quality/problem/change governance state that violates production workflow invariants, such as duplicate open problem candidates or changes approved without required risk/plan package.

## Immediate Checks

- Open the affected problem/change workspace.
- Verify authorization, status, risk, plan, approval and PIR requirements.
- Check whether the row predates P3-P5 fixes.

## Safe Queries

- Query by exact `candidate_id`, stable signal dimensions, `problem_id`, or `change_id`.
- Review aggregate payload keys for PII before sharing.

## What Not To Do

- Do not expose RCA/problem/change internals to requester/public surfaces.
- Do not approve or close governance rows to clear observer events without following the workflow.

## Escalation

Escalate as critical/error when governance gates were bypassed or requester/public access succeeds against internal APIs.

## Related Bugs

Inspired by P3 quality, P4 problem management and P5 change enablement validation.

## Cleanup and Suppression

Historical P3-P5 rows should be listed and suppressed narrowly. Current duplicates or gate bypasses remain actionable.
