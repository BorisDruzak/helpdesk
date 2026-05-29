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

```sql
SELECT candidate_id, status, signal_type, service_code, offering_code,
       request_type, ticket_count, created_at, updated_at
FROM problem_candidates
WHERE status = 'open'
  AND signal_type = :signal_type
ORDER BY updated_at DESC
LIMIT 50;
```

```sql
SELECT c.change_id, c.status, c.risk_level, c.scheduled_start, c.scheduled_end,
       rp.plan_id AS risk_plan_id, cp.plan_id AS change_plan_id
FROM changes c
LEFT JOIN change_risk_assessments rp ON rp.change_id = c.change_id
LEFT JOIN change_plans cp ON cp.change_id = c.change_id
WHERE c.change_id = :change_id;
```

## Safe Actions

- For duplicate candidates, verify whether they are pre-fix historical rows or a current scanner dedupe failure.
- For change gate alerts, return the change to the required workflow state rather than editing package rows manually.
- Re-run the relevant governance serializer/privacy test before closing the incident.

## What Not To Do

- Do not expose RCA/problem/change internals to requester/public surfaces.
- Do not approve or close governance rows to clear observer events without following the workflow.
- Do not suppress current duplicate candidates by broad signal type.

## Escalation

Escalate as critical/error when governance gates were bypassed or requester/public access succeeds against internal APIs.

## Related Bugs

Inspired by P3 quality, P4 problem management and P5 change enablement validation.

## Cleanup and Suppression

Historical P3-P5 rows should be listed and suppressed narrowly. Current duplicates or gate bypasses remain actionable.
