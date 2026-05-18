# P5 Change Enablement

P5 adds a first-class Change Enablement layer for controlled permanent fixes. A change is not a ticket and does not execute deployment work automatically. It records the governance path from problem or improvement action to risk, plan, approval, maintenance window, implementation checklist, rollback and PIR.

## Model

- `changes`: change request with `CHG-*` key, type `standard|normal|emergency`, lifecycle status, risk/impact/urgency, source links, service/offering fields, planned/actual windows and summaries.
- `change_risk_assessments`: versioned risk and impact assessment with explainable risk factors and override reason.
- `change_plans`: versioned implementation, rollback, validation and communication steps. Rollback steps are required for normal/emergency approval.
- `change_approvals`: auditable CAB-lite approval records by actor, role or group.
- `change_windows`: maintenance, blackout and emergency-allowed windows.
- `change_affected_objects`: catalog, registry, asset, queue, problem or knowledge objects affected by the change.
- `change_tasks`: implementation checklist tasks.
- `change_pir_records`: post-implementation review.
- `change_activity_events`: append-only change timeline.
- `change_policies`: governance policy for risk, plans, rollback, PIR and approval mode.

## Lifecycle

Canonical lifecycle:

`draft -> submitted -> assessing -> awaiting_approval -> approved -> scheduled -> implementation_in_progress -> implemented -> pir_required -> closed`

Terminal outcomes are `rejected`, `canceled`, `failed` and `rolled_back`. Normal and emergency changes require approved risk and plan before approval; emergency changes also require justification. Implementation requires approved/scheduled state. Closing from `pir_required` requires an approved PIR.

## Risk, Approval And Calendar

`RiskAssessmentService` computes a suggested risk from explicit factors such as service criticality, rollback complexity, security/data impact and testing confidence. Human approval is still required.

`ChangeApprovalService` creates auditable approval rows from the effective policy. Non-approvers cannot approve; admin override is explicit and audited through the change activity timeline.

`ChangeCalendarService` schedules approved work and blocks blackout windows unless an override justification is supplied. P5 does not schedule automatic technical execution.

## Problem And Quality Integration

`ChangeService.create_from_problem()` creates a normal change from a problem permanent-fix candidate, copies service/offering and affected objects, and records a problem activity event. `create_from_improvement_action()` links a P3/P4 continuous-improvement action to a change and stores `continuous_improvement_actions.change_id`.

Failed or rolled-back changes create a `continuous_improvement_actions` follow-up with `source_kind=change`, so quality and problem teams can review the outcome without replacing the existing improvement-action model.

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
- Continue using P4 problem and P3 improvement-action records; no ticket/problem status rollback is required.
- Downgrade migration `092` only if the first-class change schema must be removed before production data depends on it.
