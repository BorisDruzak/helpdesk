# P4 Problem Management / RCA

P4 turns repeated quality, ticket, knowledge and SLA signals into first-class Problem Management. A problem is not a ticket type: it has its own lifecycle, ticket links, RCA records, known-error/workaround knowledge links, affected objects and audit timeline.

## Problem Model

- `problems`: first-class problem records with `problem_key`, lifecycle status, severity/priority/impact/urgency, Service Catalog fields, owner/assignee, root-cause/workaround/permanent-fix summaries and audit timestamps.
- `problem_ticket_links`: many-to-many links from problems to incidents/tickets with `link_type`, confidence/evidence summary and soft unlink metadata.
- `problem_candidates`: scanner output before a confirmed problem. Candidates store aggregate evidence counts and redacted samples, not requester PII.
- `problem_detection_rules`: configurable candidate-detection thresholds and scopes.
- `problem_activity_events`: append-only timeline for candidate/problem lifecycle, ticket links, RCA, knowledge links and improvement/change outputs.

## Candidate Detection

`ProblemCandidateService` scans deterministic signals:

- low CSAT clusters from `ticket_feedback`;
- reopen patterns from `ticket_reopen_events`;
- SLA breach, failed QA and failed knowledge signals as the schema/source data matures;
- repeated tickets by service/offering/request type.

Scans are idempotent by fingerprint. Existing open candidates are updated instead of duplicated, and converted/accepted candidates are not recreated for the same pattern.

## Lifecycle

Canonical P4 statuses are:

`new -> investigating -> known_error -> workaround_available -> permanent_fix_planned -> permanent_fix_in_progress -> resolved -> closed`

Any non-terminal state can be canceled with a reason. Resolution requires a root-cause summary and either a permanent-fix summary or an explicit no-permanent-fix reason. Closing requires a closure summary. Closed is terminal unless an admin-level future reopen policy is added.

## RCA

`problem_rca_records` stores versioned RCA records. RCA drafts can be submitted for review and approved/rejected by a human reviewer. P4 does not auto-generate or auto-approve RCA conclusions.

Supported methodologies include `five_whys`, `fishbone`, `timeline`, `fault_tree`, `vendor_rca` and `narrative`.

## Known Errors And Workarounds

Known errors and workarounds are Knowledge Platform items, not duplicated article bodies inside the problem record.

- `ProblemKnownErrorService.create_known_error_draft()` creates a `knowledge_items.item_type=known_error` draft.
- `ProblemKnownErrorService.create_workaround_draft()` creates a `knowledge_items.item_type=workaround` draft.
- Draft visibility defaults to `support_internal`.
- Requester-safe publication must go through Knowledge Platform review/lint/publish flow.

`problem_known_error_links` ties problems to known error, workaround, permanent-fix article, support runbook or requester article items.

## Affected Objects

`problem_affected_objects` links a problem to catalog services, offerings, registry services, assets, devices, queues, vendors, locations, departments or knowledge items. Service/offering fields are copied to the problem for analytics and can be used even when a richer registry object does not exist.

## APIs

Support/admin/auditor read APIs:

- `GET /api/web/problems`
- `GET /api/web/problems?ticket_id={ticket_id}`
- `GET /api/web/problems/{problem_id_or_key}`
- `GET /api/web/problem-candidates`
- `GET /api/web/problems/metrics/summary`

Support/admin mutation APIs:

- `POST /api/web/problems`
- `POST /api/web/problems/{problem_id_or_key}/transition`
- `POST /api/web/problems/{problem_id_or_key}/link-ticket`
- `POST /api/web/problems/{problem_id_or_key}/unlink-ticket/{ticket_id}`
- `POST /api/web/problems/{problem_id_or_key}/affected-objects`
- `POST /api/web/problem-candidates/scan`
- `POST /api/web/problem-candidates/{candidate_id}/convert`
- `POST /api/web/problems/{problem_id_or_key}/rca`
- `POST /api/web/problems/{problem_id_or_key}/rca/{rca_id}/submit-review`
- `POST /api/web/problems/{problem_id_or_key}/rca/{rca_id}/approve`
- `POST /api/web/problems/{problem_id_or_key}/known-error-draft`
- `POST /api/web/problems/{problem_id_or_key}/workaround-draft`

Requester/public users have no direct problem/RCA APIs in P4.

## UI Surfaces

- `/app/admin/problems`: problem metrics, candidate scan/convert, problem list, RCA actions and known-error/workaround draft creation over real APIs.
- `/app/tickets`: support Quality tab shows linked problems for the selected ticket.
- `/app/admin/quality`: quality analytics can use problem metrics as the P4 signal surface expands.

## Security And Privacy

- Requester/public users cannot access problem APIs.
- Admin/support can manage problem records and candidates; auditor is read-only.
- Aggregate analytics never returns requester IDs, requester comments, public tokens or raw feedback comments.
- RCA, internal evidence, queue IDs and internal activity payloads stay support/admin/auditor-only.
- Requester-safe known error/workaround visibility is controlled only by Knowledge Platform ACL, review and publish state.

## Rollback

- Disable detection rules and candidate scan endpoints operationally.
- Keep existing problem records read-only if investigation must pause.
- Revert P4 code and downgrade migration `090` if schema rollback is required.
- No ticket workflow rollback is required because P4 links to tickets without changing canonical ticket statuses.
