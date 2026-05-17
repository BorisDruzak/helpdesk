# P3 Quality Loop

P3 adds a structured experience and quality loop around ticket resolution without changing canonical ticket statuses or Protocol V3.

## Model

- `ticket_feedback`: requester/public/support-entered CSAT rows for resolved or closed tickets. Rating is 1..5, subratings are optional, reason codes are structured, and one latest row per ticket/requester is maintained by the service layer.
- `ticket_reopen_events`: mandatory structured reopen reason taxonomy for reopening resolved/closed tickets.
- `ticket_quality_reviews` and `ticket_quality_review_comments`: internal QA review queue for low CSAT, reopen, SLA breach, missing evidence, high-priority and manager/audit triggers.
- `continuous_improvement_actions`: process improvement work items linked to CSAT, reopen, QA review, knowledge gap, SLA breach or manual source.
- `service_quality_snapshots`: aggregate service/offering/period metrics without requester PII.
- `quality_policies`: effective thresholds and trigger flags for global/service/offering/queue scopes.

## APIs

Requester/public:

- `POST /api/tickets/{ticket_id}/feedback`
- `POST /api/tickets/{ticket_id}/reopen`
- `POST /public_api/tickets/{ticket_id}/feedback`
- `POST /public_api/tickets/{ticket_id}/reopen`

Support/admin/auditor:

- `GET /api/web/quality/reviews`
- `POST /api/web/quality/reviews/{review_id}/assign|start|complete|dismiss`
- `GET|POST /api/web/quality/improvement-actions`
- `PATCH /api/web/quality/improvement-actions/{action_id}`
- `POST /api/web/quality/improvement-actions/{action_id}/close`
- `GET /api/web/quality/summary`
- `GET /api/web/quality/service-quality`
- `POST /api/web/quality/snapshots/recompute`
- `GET /api/web/quality/policies`
- `POST /api/web/quality/policies/save`

## Workflow

- Feedback is accepted only for `resolved` or `closed` tickets within the default 14-day window.
- Low CSAT is deterministic: rating at or below the effective `low_csat_threshold`, or `problem_resolved=false`.
- Low CSAT creates a QA review. Knowledge failure reasons can create an improvement action for KB updates.
- Reopen requires a reason code; `other` requires a comment. Reopen uses the existing workflow service and records a first-class reopen event.
- Improvement actions are not tickets. They require source, action type, status, priority and audit fields; moving into assigned/in-progress requires an owner and closing requires outcome notes.

## Surfaces

- Requester ticket page shows CSAT and reopen controls for resolved/closed tickets.
- Support ticket detail includes a Quality section with latest CSAT, reopen count, QA reviews and improvement actions.
- Admin `/app/admin/quality` shows aggregate CSAT/reopen/SLA/KB/QA/action metrics and internal review/action work queues.
- Agent GUI is unchanged in P3; web/public requester surfaces are the canonical CSAT/reopen path and Protocol V3 is not changed.

## Privacy

- Requester/public users cannot read QA reviews, improvement actions, internal findings, queue IDs, actor IDs, support-only comments or raw policy JSON.
- Analytics responses are aggregate only and do not include requester IDs, raw feedback comments or public access tokens.
- Public feedback and reopen require a valid public ticket session token scoped to the ticket.

## Rollback

- Operational rollback: disable feedback prompts and QA triggers through quality policy/UI while keeping data read-only.
- Code rollback: revert P3 code and downgrade Alembic revision `088`; existing ticket status/workflow state does not require rollback.

