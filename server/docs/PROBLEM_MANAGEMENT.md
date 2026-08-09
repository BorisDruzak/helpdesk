# P4 Problem Management / RCA

P4 turns repeated quality, ticket, SLA and operational signals into first-class Problem Management. A problem is not a ticket type: it has its own lifecycle, ticket links, RCA records, affected objects and audit timeline.

## Problem Model

- `problems`: first-class problem records with `problem_key`, lifecycle status, severity/priority/impact/urgency, Service Catalog fields, owner/assignee, root-cause/workaround/permanent-fix summaries and audit timestamps.
- `problem_ticket_links`: many-to-many links from problems to incidents/tickets with `link_type`, confidence/evidence summary and soft unlink metadata.
- `problem_candidates`: scanner output before a confirmed problem. Candidates store aggregate evidence counts and redacted samples, not requester PII.
- `problem_detection_rules`: configurable candidate-detection thresholds and scopes.
- `problem_scanner_runs`: audit rows for scheduled, manual and API scanner runs.
- `problem_slo_policies`: operational milestone policy overrides for investigation, known-error, workaround, RCA, resolution and closure due dates.
- `problem_activity_events`: append-only timeline for candidate/problem lifecycle, ticket links, RCA, knowledge links and improvement/change outputs.

## Candidate Detection

`ProblemCandidateService` scans deterministic signals:

- low CSAT clusters from `ticket_feedback`;
- reopen patterns from `ticket_reopen_events`;
- SLA breach patterns from ticket first-response/resolution breach timestamps;
- failed QA review patterns from failed/action-required `ticket_quality_reviews`;
- repeated tickets by service/offering/request type.

Scans are idempotent by fingerprint. Existing open candidates are updated instead of duplicated, `duplicate_count`/`first_seen_at`/`last_seen_at` are maintained, dismissed candidates respect `dismissed_until`, and converted/accepted/merged candidates are not recreated for the same pattern.

## Scheduled Scanner

`server/app/services/problem_candidate_scheduler.py` runs candidate scans when explicitly enabled. `PROBLEM_SCANNER_ENABLED` defaults to `false`; interval, initial delay, lookback, max candidates and dry-run are controlled by `PROBLEM_SCANNER_INTERVAL_SEC`, `PROBLEM_SCANNER_INITIAL_DELAY_SEC`, `PROBLEM_SCANNER_LOOKBACK_HOURS`, `PROBLEM_SCANNER_MAX_CANDIDATES_PER_RUN` and `PROBLEM_SCANNER_DRY_RUN`.

The scheduler prevents overlapping scans, writes `problem_scanner_runs`, records failures without crashing the server and stops cleanly during app cleanup. Operational APIs are `GET /api/web/problem-scanner/status`, `GET /api/web/problem-scanner/runs` and `POST /api/web/problem-scanner/run`.

## Dedup, Merge And Cooldown

Candidate fingerprints are deterministic over signal type, rule code, service/offering, signal key and window bucket. Support/admin can merge candidates through `POST /api/web/problem-candidates/{candidate_id}/merge`; the source moves to `merged`, points at the target, combined redacted evidence is stored on the target and a `candidate_merged` activity event is written.

## Lifecycle

Canonical P4 statuses are:

`new -> investigating -> known_error -> workaround_available -> permanent_fix_planned -> permanent_fix_in_progress -> resolved -> closed`

Any non-terminal state can be canceled with a reason. Resolution requires a root-cause summary and either a permanent-fix summary or an explicit no-permanent-fix reason. Closing requires a closure summary. Closed is terminal unless an admin-level future reopen policy is added.

## Problem SLO And Aging

P4.1 materializes `investigation_due_at`, `known_error_due_at`, `workaround_due_at`, `rca_due_at`, `resolution_due_at`, `closure_due_at` and `breached_milestones` on problems. Effective policy precedence is offering > service > severity > global. If no `problem_slo_policies` row matches, severity-based defaults are used. Analytics report overdue milestone counts, average time to known error/workaround/RCA approval/resolution, problems without RCA and problems without workaround.

## RCA

`problem_rca_records` stores versioned RCA records. RCA drafts can be submitted for review and approved/rejected by a human reviewer. P4 does not auto-generate or auto-approve RCA conclusions.

Supported methodologies include `five_whys`, `fishbone`, `timeline`, `fault_tree`, `vendor_rca` and `narrative`.

## Known Errors And Workarounds

Helpdesk keeps the problem lifecycle and its local root-cause/workaround/permanent-fix summaries, but it no longer creates, queries or links local Knowledge items. `ProblemKnownErrorService.create_known_error_draft()` and `create_workaround_draft()` currently return the explicit unavailable result with nullable `external_reference=None`; they do not change problem status or insert `problem_known_error_links` rows.

The existing `problem_known_error_links` table is retained only for migration/history safety and is not an active source of truth. A future external Knowledge integration may store an opaque external reference through the versioned boundary; Helpdesk must not infer its format or restore a local draft fallback.

## Affected Objects

`problem_affected_objects` links a problem to catalog services, offerings, registry services, assets, devices, queues, vendors, locations or departments. Service/offering fields are copied to the problem for analytics and can be used even when a richer registry object does not exist. Historical rows may retain opaque legacy object references, but active Problem Management does not resolve local Knowledge items.

## APIs

Support/admin/auditor read APIs:

- `GET /api/web/problems`
- `GET /api/web/problems?ticket_id={ticket_id}`
- `GET /api/web/problems/{problem_id_or_key}`
- `GET /api/web/problem-candidates`
- `GET /api/web/problem-scanner/status`
- `GET /api/web/problem-scanner/runs`
- `GET /api/web/problems/metrics/summary`

Support/admin mutation APIs:

- `POST /api/web/problems`
- `POST /api/web/problems/{problem_id_or_key}/transition`
- `POST /api/web/problems/{problem_id_or_key}/link-ticket`
- `POST /api/web/problems/{problem_id_or_key}/unlink-ticket/{ticket_id}`
- `POST /api/web/problems/{problem_id_or_key}/affected-objects`
- `POST /api/web/problem-candidates/scan`
- `POST /api/web/problem-candidates/{candidate_id}/convert`
- `POST /api/web/problem-candidates/{candidate_id}/merge`
- `POST /api/web/problem-scanner/run`
- `POST /api/web/problems/{problem_id_or_key}/rca`
- `POST /api/web/problems/{problem_id_or_key}/rca/{rca_id}/submit-review`
- `POST /api/web/problems/{problem_id_or_key}/rca/{rca_id}/approve`
- `POST /api/web/problems/{problem_id_or_key}/known-error-draft`
- `POST /api/web/problems/{problem_id_or_key}/workaround-draft`

Requester/public users have no direct problem/RCA APIs in P4.

## UI Surfaces

- `/app/admin/problems`: problem metrics, scanner status/run/dry-run, candidate scan/convert/merge, dedup metadata, problem list, SLO aging, RCA actions and known-error/workaround draft creation over real APIs.
- `/app/tickets`: support Quality tab shows linked problems for the selected ticket.
- `/app/admin/quality`: quality analytics can use problem metrics as the P4 signal surface expands.
- `/app/admin/problems` also exposes the P5 "Create change" action for a selected problem permanent fix. The change record inherits problem service/offering and affected objects, but problem closure remains human/policy controlled.

## Change Enablement Link

P5 owns first-class change requests in `server/change/*`. Problem Management only emits the permanent-fix context and records `change_created` activity; it does not auto-close or auto-resolve a problem when a change is created. Successful, failed or rolled-back change outcomes can be reviewed through Change Enablement and Continuous Improvement actions.

## Security And Privacy

- Requester/public users cannot access problem APIs.
- Admin/support can manage problem records, candidates, scanner runs and candidate merge; auditor is read-only.
- Aggregate analytics never returns requester IDs, requester comments, public tokens or raw feedback comments.
- RCA, internal evidence, queue IDs and internal activity payloads stay support/admin/auditor-only.
- Helpdesk stores no local known-error/workaround content. Any future requester-safe reference belongs to the external Knowledge Platform and must arrive as an opaque, versioned reference.

## Rollback

- Disable `PROBLEM_SCANNER_ENABLED` and keep manual/API scan available.
- Disable detection rules and candidate scan endpoints operationally if needed.
- Keep existing problem records read-only if investigation must pause.
- Downgrade migration `091` to remove scheduler/SLO hardening artifacts while keeping P4 `090` intact, or revert P4 code and downgrade migration `090` if the whole problem domain must be removed.
- No ticket workflow rollback is required because P4 links to tickets without changing canonical ticket statuses.
