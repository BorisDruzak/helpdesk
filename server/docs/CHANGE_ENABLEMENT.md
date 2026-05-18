# P5 Change Enablement

P5 adds a first-class Change Enablement layer for controlled permanent fixes. A change is not a ticket and does not execute deployment work automatically. It records the governance path from problem or improvement action to risk, plan, approval, maintenance window, implementation checklist, rollback and PIR.

## Model

- `changes`: change request with `CHG-*` key, type `standard|normal|emergency`, lifecycle status, risk/impact/urgency, source links, service/offering fields, planned/actual windows and summaries.
- `change_risk_assessments`: versioned risk and impact assessment with explainable risk factors and override reason.
- `change_plans`: versioned implementation, rollback, validation and communication steps. Rollback steps are required for normal/emergency approval.
- `change_approvals`: auditable CAB-lite approval records by actor, role or group.
- `change_windows`: standard, maintenance, blackout and emergency-allowed windows. Windows may be one-off or recurring with simple RRULEs such as `FREQ=WEEKLY;BYDAY=MO;COUNT=8`.
- `change_affected_objects`: catalog, registry, asset, queue, problem or knowledge objects affected by the change.
- `change_tasks`: implementation checklist tasks.
- `change_pir_records`: post-implementation review.
- `change_activity_events`: append-only change timeline.
- `change_policies`: governance policy for risk, plans, rollback, PIR, lead time, emergency retrospective and approval mode.

## Lifecycle Matrix

| Status | Meaning | Allowed Next | Gate |
|---|---|---|---|
| `draft` | Change is being prepared. | `submitted`, `canceled` | Title, description, owner and type should be present before submit. |
| `submitted` | Request is ready for assessment. | `assessing`, `rejected`, `canceled` | No implementation allowed. |
| `assessing` | Risk, impact and plan are being reviewed. | `awaiting_approval`, `rejected`, `canceled` | Normal/emergency require approved risk and plan before approval request. |
| `awaiting_approval` | CAB-lite approval rows exist or are requested. | `approved`, `rejected`, `canceled` | Required approvals must be approved; rejections block approval. |
| `approved` | Authorized but not yet scheduled. | `scheduled`, `implementation_in_progress`, `canceled` | Direct implementation is allowed only for authorized emergency/override flows. |
| `scheduled` | Planned window is set. | `implementation_in_progress`, `canceled` | Blackout conflicts are blocked unless justified; overlapping active changes are blocked for the same service/offering. |
| `implementation_in_progress` | Work is being performed. | `implemented`, `failed`, `rolled_back` | Implementation tasks must be done or explicitly overridden before implemented. |
| `implemented` | Technical work finished. | `pir_required`, `closed` | Normal/emergency usually move to PIR based on policy. |
| `pir_required` | Post-implementation review must be approved. | `closed`, `failed` | Approved PIR required before closure. |
| `closed` | Complete and accepted. | none | Closure summary required. |
| `failed` | Implementation failed. | none | Creates improvement follow-up. |
| `rolled_back` | Rollback was used. | none | Rollback summary required and creates improvement follow-up. |
| `rejected` / `canceled` | Governance stop. | none | Audit event records the decision. |

## Change Types

### Standard

Standard changes are low-risk, repeatable and eligible for preapproval only when they match a standard change catalog policy. The catalog is stored in `change_policies.metadata.standard_catalog` for the relevant `change_type=standard` policy.

Example policy payload:

```json
{
  "code": "standard-laptop-agent-update",
  "title": "Preapproved laptop agent update",
  "scope_type": "change_type",
  "change_type": "standard",
  "standard_preapproved": true,
  "approval_mode": "single",
  "require_risk_assessment": false,
  "require_plan": false,
  "require_rollback_plan": false,
  "require_pir": false,
  "metadata": {
    "standard_catalog": [
      {
        "code": "std-agent-update",
        "title": "Agent minor update",
        "allowed_window": "weekly maintenance",
        "rollback": "launcher rollback",
        "evidence_required": "health smoke after rollout"
      }
    ]
  }
}
```

When `standard_preapproved=true`, the effective policy turns approval mode into `none`; `ChangeApprovalService` records a skipped non-required approval row and the lifecycle can proceed after the normal status path. This is not global auto-approval: the policy must be explicit and scoped.

### Normal

Normal changes require risk assessment, implementation plan, rollback plan, approvals and usually PIR. They are the default type for problem permanent fixes and improvement actions.

### Emergency

Emergency changes require `emergency_justification` before approval. They may use justified blackout override when needed, but they still require retrospective review. `change_policies.max_emergency_retro_hours` controls how long an implemented emergency change may remain without approved PIR before analytics flags it as overdue.

## Calendar And Scheduling

`ChangeCalendarService` schedules approved work and blocks unsafe windows. P5 does not trigger technical execution.

Calendar rules:

- Blackout windows block scheduling for matching service/offering unless `blackout_override=true` and `override_justification` is supplied.
- Recurring blackout/maintenance windows use simple RRULE support: `FREQ=DAILY|WEEKLY`, optional `INTERVAL`, `COUNT`, `UNTIL`, and weekly `BYDAY`.
- Overlapping active changes are blocked for the same service/offering when another change is already `approved`, `scheduled` or `implementation_in_progress` with an intersecting planned window.
- Maintenance and standard windows are advisory scheduling structures in P5; blackout is the hard block.

Example recurring blackout:

```json
{
  "title": "Payroll close blackout",
  "window_type": "blackout",
  "service_code": "finance",
  "starts_at": "2026-05-18T22:00:00Z",
  "ends_at": "2026-05-19T02:00:00Z",
  "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO;COUNT=8"
}
```

## Risk, Approval And Policy

`RiskAssessmentService` computes a suggested risk from explicit factors such as service criticality, rollback complexity, security/data impact and testing confidence. Human approval is still required unless the effective policy explicitly preapproves a standard change.

`ChangeApprovalService` creates auditable approval rows from the effective policy:

- `approval_mode=none`: creates a skipped, non-required approval row.
- `single`: one approval is enough when the configured approver actor/role matches.
- `all`: every required approval must be approved.
- `cab`: CAB-lite approval rows are created with stage `cab`.

Admin override is explicit and audited through the change activity timeline. Non-approvers cannot approve.

## Metrics

`ChangeAnalyticsService.summary()` returns aggregate, no-PII metrics:

- `change_count`, `open_change_count`, `emergency_change_count`.
- `failed_change_count` and `failure_rate`: failed changes only.
- `rollback_count` and `rollback_rate`: rolled-back changes.
- `average_lead_time_hours`: submitted to implementation start.
- `average_implementation_duration_hours`: actual implementation start to actual end.
- `pir_completion_rate`: approved PIR records over PIR records.
- `emergency_retrospective_overdue_count`: implemented emergency changes without approved PIR after the effective retrospective window.
- Breakdown maps by type, status, risk and service.

No requester identifiers, raw implementation notes, rollback steps, risk notes or asset internals are included in aggregate metrics.

## Problem And Quality Integration

`ChangeService.create_from_problem()` creates a normal change from a problem permanent-fix candidate, copies service/offering and affected objects, and records a problem activity event. `create_from_improvement_action()` links a P3/P4 continuous-improvement action to a change and stores `continuous_improvement_actions.change_id`.

Failed or rolled-back changes create a `continuous_improvement_actions` follow-up with `source_kind=change`, so quality and problem teams can review the outcome without replacing the existing improvement-action model.

## Operator Guide

1. Create or open a change in `/app/admin/changes`.
2. For standard changes, verify the title/source matches an explicit standard catalog policy before relying on preapproval.
3. For normal/emergency changes, create and approve risk assessment.
4. Create and approve implementation/rollback/validation plan.
5. Request approvals and approve with the configured actor/role/group.
6. Schedule inside a suitable window. Resolve blackout/overlap errors by choosing another time or using documented emergency override.
7. Add implementation tasks and complete them during execution.
8. Transition to `implementation_in_progress`, then `implemented`.
9. Complete PIR when policy requires it. Emergency changes should be reviewed before `max_emergency_retro_hours`.
10. Close with closure summary.

Common operator errors:

- `blackout window blocks scheduling`: planned time intersects a blackout window or recurring blackout occurrence.
- `blackout override justification is required`: override was requested without a reason.
- `overlap with scheduled change CHG-*`: another active change already occupies the same service/offering window.
- `approvals are not satisfied`: approval rows are missing, pending or rejected.
- `rollback plan is required before approval`: normal/emergency plan does not include rollback steps.
- `approved PIR is required before closure`: change is in `pir_required` and PIR is not approved.

## APIs

Support/admin/auditor read:

- `GET /api/web/changes`
- `GET /api/web/changes/{change_id_or_key}`
- `GET /api/web/changes/metrics/summary`
- `GET /api/web/change-windows`
- `GET /api/web/change-policies`

Support/admin mutations:

- `POST /api/web/changes`
- `POST /api/web/changes/from-problem/{problem_id}`
- `POST /api/web/changes/from-improvement-action/{action_id}`
- `POST /api/web/changes/{change_id_or_key}/transition`
- risk, plan, approvals, schedule, task and PIR endpoints under `/api/web/changes/{change_id_or_key}/*`
- `POST /api/web/change-windows`

Admin-only governance:

- `POST /api/web/change-policies/save`

Requester/public users have no direct change API in P5.

## UI

- `/app/admin/changes`: change list, create form, summary metrics, risk/plan/approval/window/task/PIR actions, affected-object summary and calendar windows.
- `/app/admin/problems`: selected problem has a "Create change" action for permanent fixes.

Both surfaces use real `/api/web/changes*` and `/api/web/problems*` APIs.

## Security And Privacy

- Requester/public access is denied.
- Auditor is read-only.
- Support can create/update changes and tasks, but approval decisions require matching approver actor/role/group unless admin override is used.
- Internal risk notes, implementation steps, rollback steps, affected asset details and raw activity payloads are not requester-visible.
- Change analytics are aggregate-only and contain no requester PII.

## Rollback

- Disable or hide the change workspace and keep records read-only.
- Keep manual problem/improvement-action workflows available.
- Continue using P4 problem and P3 improvement-action records; no ticket/problem status rollback is required.
- Downgrade migration `092` only if the first-class change schema must be removed before production data depends on it.
