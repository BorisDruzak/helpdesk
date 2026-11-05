# Everyday support workspace

The `/app/support` entry redirects to `/app/tickets`. The existing
`/app/tickets` and `/app/tickets/:ticketId` routes open the simple
operational layout by default. `TicketListPage` retains its query cache,
realtime subscriptions, attachment upload and typed mutations. Components in
`webapp/src/pages/tickets/components/simple-support-*` provide the queue,
three-area ticket and conversation. The former command center remains at
`/app/support/advanced`. `simple-resolution-form.tsx` presents the public result,
remaining policy fields and optional internal information.

## Requester acceptance of a solution

Ordinary support completion is `in_progress → resolved → closed`: support writes
the public result and resolves the ticket; the requester sees **Проверьте решение**
with **Подтвердить решение** and **Проблема не решена**. Only the owner's acceptance
closes it. A rejection uses the existing canonical reopen service. It is separate
from optional rating and internal approval processes. Resolution SLA stops when
the result is prepared; the ticket stays available for acceptance.

`actions.requester_confirmation_required` explains this in the support card and
resolution form. When required, staff status options omit `closed`, the direct
status API returns409 `REQUESTER_CONFIRMATION_REQUIRED`, and the workflow service
rechecks under the ticket lock before effects. An administrator uses the same
guard; confirming their own request uses the owner-scoped requester endpoint.
Explicit opt-out policies still support atomic resolve-and-close where authorized.

On staging, `scripts/helpdesk_requester_confirmation.py` plans/publishes ordinary
closure `guided_studio_20261011_closure`1.0.2→1.0.3 through the audited registry.
It enables confirmation, disables automatic expiry closure, and preserves summary,
evidence, classification and special-policy requirements. Host/release/private
backup gates belong to the approved staging transport. Apply rechecks a fingerprint
and locks policy/ticket writes. Previously resolved tickets newly affected by the
policy receive canonical pending-confirmation state and an audit event, preserving
status/history; existing requester decisions require review rather than replacement.
Existing pending ordinary confirmations also lose their stored automatic expiry;
their request ID and decision state stay intact. Explicit special-policy expiries
are preserved. A pending acceptance may still be rejected after the optional
feedback window expires, including after a previous positive rating.
The requester action panel becomes visible on the next normal refresh. The plan
is read-only and a fresh repeated apply is idempotent. Already closed tickets are
not reopened. Do not replay the older phase-one catalog publication against the
new active policy; its historical version guard intentionally rejects that state.

Ticket attachments can be uploaded without a computer. Revision154 allows a
ticket-bound artifact with no device while requiring at least ticket/device scope;
ownership/download checks remain authoritative. See
[artifact contract](../server/docs/ARTIFACTS_API.md).

## Queue partitioning and layout

Queue definitions, members and OLA settings live in `/app/settings`, tab
**Очереди**. `TICKET_QUEUE_MODE=partitioned` retains the original behavior (default).
`TICKET_QUEUE_MODE=unified` exposes one logical queue to active support/admin
operators. Queue rows expose additive `queue_mode`; settings show the current
mode. Restart the service after changing its environment through the reviewed
configuration/release workflow. Returning to `partitioned` restores membership
checks and routing without a data migration.
On the approved staging host, the reviewed helper is
`python scripts/configure_helpdesk_queue_mode.py --mode unified` (or
`--mode partitioned`), followed by the canonical staging service restart. It
backs up the environment privately and changes only this setting.

In unified mode membership/read scope, manual/automatic assignment candidates,
queue notifications and saved queue views use the common staff scope. User,
agent and auditor permissions, ownership/public reply guards, capacity, FSM,
SLA and closure requirements remain authoritative. Partition selectors, explicit
queue changes and manual rerouting are disabled (`QUEUE_PARTITIONING_DISABLED`).
Partition-specific smart-view filters no longer restrict the list. New tickets
route to the active common queue named by `TICKET_TAKE_QUEUE_COMMON_CODE`;
its auto-assignment switch still applies. Existing ticket queue IDs, assignments,
history and running OLA timers are preserved; no bulk rewrite occurs. All queue
configuration and the partitioned implementation remain available.
Non-queue rule actions (priority, SLA/approval policies, tags and suggestions)
continue through the canonical routing service, including policy-only updates
on an existing ticket whose historical queue does not change.

The compact list has **Открыть всю очередь**; it uses the existing full-list route
and retains search/filter state. Ordinary ticket mode shows plain requester,
contact, status, assignee and resolution-SLA facts. The full inspector with
context, device, SLA, knowledge, tools and passport tabs remains in advanced mode.
Both sidebars support
pointer resizing and arrow keys, with double-click/Home/Enter to reset. Widths
persist through the existing layout preference. On small screens **Сведения**
opens the plain facts drawer; the full queue remains reachable from the ticket
header. Explicit additional functions open the retained advanced inspector.

## Queue and actions

Five filters use server-side smart views before the queue limit: `open`, `new`,
`waiting`, `completed`; Mine uses `scope=mine` with `smart_view=open`. Resolved,
closed and canceled tickets belong to Completed. Waiting includes user, vendor
and internal-team waits. Approval has its own contextual action. Existing smart
views, saved columns and bulk operations remain in the additional mode.

New/queued/assigned tickets use one `POST /api/web/support/tickets/{id}/status`
command with `to_status=in_progress` to take/start work. Status and assignment
to the current actor become visible after success and
refetch. The server locks and refreshes the ticket before checking ownership,
permissions and the canonical transition. Unassigned work also requires
`ticket.assign` and existing queue-membership assignment checks. Concurrent
operators cannot silently take the same ticket. An explicit administrator take
also assigns the ticket to that administrator; privileged public replies from
the additional workspace retain their existing separate authority.

Legacy in-progress tickets without an owner expose **Взять себе**. The same
action lets an authorized administrator explicitly take another operator's
active/waiting work. It sends the existing `/assign` command with additive
`claim=true`, `assignee_id` equal to the caller and `expected_assignee_id` from
the displayed snapshot. The server locks and refreshes the ticket, rechecks
scope, status and expected ownership, then applies canonical assignment checks.
A concurrent claim returns409 instead of replacing the first owner. Claiming
preserves status; taking waiting work does not reserve capacity for resuming.
Resume/start checks active capacity separately. The header always names the
assignee. The compact public editor and resolution require assignment to self,
including administrators; support resolution commands enforce this on the server.

Queue items and ticket `actions` expose the additive `take_in_work` object
(`allowed`, `reason_code`, `reason`). It evaluates the same permissions,
ownership, queue membership, active-load limit and workflow transition used by
the command (status-preserving claims use assignment rather than activation
checks). Queue projection caches reads for this request only. The status
command validates again under the ticket lock. An unassigned new/queued ticket
also checks the destination active load before starting work. Membership and
capacity denials return `ASSIGNEE_NOT_IN_QUEUE` and `ASSIGNEE_CAPACITY_REACHED`
with safe, actionable text. The UI uses the projection in both queue and card
and refetches it after a failed command; it does not grant queue membership.

## Conversation and privacy

`handle_web_support_send_message` checks the appropriate comment permission,
then reads the ticket with `for_update=True`. New public replies require an
assignee and an active-work/waiting status. The assigned actor or an authorized
administrator can reply. New, queued, assigned, resolved and closed tickets
reject replies with `TICKET_NOT_IN_WORK`/409; a different support actor receives
`ASSIGNEE_CONFLICT`/403. Rejection occurs before message persistence, observer
success, broadcast or first-response SLA completion. Internal notes retain
their separate permission and do not stop first-response SLA. Sending a message
does not automatically change the ticket's status.

The additive `actions.can_send_public_message` projection provides the UI gate;
the endpoint remains authoritative. Dialog contains public chat messages,
Internal notes contains internal entries, and History contains diagnostics and
system events. Deduplication uses message/event identities, preserves attachments
and takes internal visibility when duplicate projections disagree. Real public
service messages, including solution-confirmation requests, remain in Dialog.
Public/internal composer drafts and pending attachments are separate.

Compact Dialog requests `filter=messages`, Internal notes requests `internal`,
and History requests `all` to retain both diagnostic and system events. Support
timeline reads use `TicketEventsRepo.get_recent_timeline_events`: select the
newest bounded window, then return chronological order with event-ID tie-breaks.
Public/internal chat filtering happens before SQL LIMIT so a long SLA history
or private-note stream cannot evict recent public replies. Historical `get_events`
replay behavior is unchanged. Existing stored messages are not rewritten.

The Messenger layout keeps only the message feed scrolling, with the editor
anchored below it. Bubbles have bounded line lengths, sender/time labels and
date separators. Description, structured answers and the public result appear in
the separate **Контекст** block of the right inspector, available via **Сведения**
on narrow screens. They no longer consume conversation height. An identical initial
chat message stays collapsible. Raster screenshot attachments show lazy thumbnails;
click opens a native modal in the current page, with Escape/backdrop/close controls
and focus restoration. Download is a separate explicit action. Only exact same-origin
artifact routes and raster types are previewed; errors leave the download available.
`webapp/src/components/chat-attachment.tsx` and its standalone stylesheet provide
this same viewer in authenticated requester chat, for employee and support images.
Direct requester entry loads the viewer styles without visiting support first;
its draft and cookie-authorized artifact access remain unchanged.
Other files retain their canonical download links. Ctrl/Command+Enter sends an allowed nonempty
draft, while Enter inserts a line break. New messages preserve the reading
position when the operator has scrolled back and offer a return-to-latest button.
Resolved/closed public conversations show a concise read-only notice instead of
an unusable editor. Authorized internal notes keep their separate composer and
draft/attachment state.

## Files in a reply

Requester chat and ordinary support Dialog/Internal notes accept local files
dropped anywhere over their conversation. Files upload into a draft; sending
remains explicit. The existing picker accepts multiple files. **Вложения к
сообщению** groups ready images/files, allows preview/removal and explains that
they will be sent with the text. One message command carries text and all selected
`attachment_refs`; file-only messages remain available. Removing a draft item
does not delete stored history or send a message.

Ctrl+V in either chat also adds clipboard images to the same draft queue. Existing
reply text is preserved; plain text and the text part of a mixed image/text paste
use native insertion/caret behavior. Only image files supplied by the paste event
are attached; HTML image links are not fetched. This requires no clipboard-read
permission or background clipboard access. Existing disabled/history/role guards
apply, and send remains explicit. The composers show a Ctrl+V hint.

Shared `components/chat-file-draft.tsx` provides the overlay/group. The scoped
serial queue in `components/use-chat-uploads.ts` accepts repeated drops, retains
successful files after partial failure and blocks send until uploads finish.
Ticket, audience, permission change or unmount invalidates late callbacks and
stops queued work; public and private drafts stay separate. Canonical server
capabilities, requester ownership and staff work/assignment checks remain
authoritative. Closed/read-only/history views do not accept uploads. URL/HTML
drops cannot navigate away or fetch external images; directories are skipped with
an explanation. Plain text dragging keeps normal editing behavior.

## Resolution and additional functions

Resolve opens one form using `actions.closure_requirements`. Resolution code is
optional stored metadata: neither compact nor advanced completion asks for it,
and missing-code requirements in historical snapshots or transition gates no
longer block resolution/closure. Other policy fields remain authoritative.
Missing evidence or passport requirements open the existing passport workspace.

`actions.can_resolve_and_close` advertises completion only for started work,
the assigned current operator (including administrators), both allowed workflow transitions and
an effective policy with requester confirmation explicitly disabled. The UI
then sends `to_status=resolved` with `close_after_resolve=true` and the public
result. The canonical workflow records resolved and closed in one transaction;
failure of either transition rolls back both. Events are broadcast after commit.
Explicit confirmation, approval, evidence, passport and other workflow guards
still apply. Policies requiring confirmation keep separate resolution/closure.
An agent is not required for ordinary support.

The problem and public result are visible in the compact ticket. Long public
results expand into a keyboard-accessible scroll region. Requester views use
only `requester_resolution_summary`; internal `resolution_summary` stays private.
Confirmation, rating and reopening each follow their own server capability.
Optional rating and reopening forms open only on an explicit request; mandatory
confirmation remains visible when required by policy.
An administrator using the requester workspace acts only on their own linked
requester identity, with ownership reread after the ticket lock.

Additional mode retains tools, SLA, passport, Quality, saved queue views and bulk
actions; returning to ordinary work is explicit. `?advanced=1` directly opens
those existing surfaces. Ordinary entry ignores old expanded-mode preferences.
No API, event history or subsystem is removed. Existing tooling and dependencies
are retained; the ticket-attachment migration is described above.

## Verification

Targeted coverage: `test_support_work_no_db.py`, `test_support_work.py`,
`test_support_operational_views_no_db.py`, the `simple-*` component tests and
`webapp/tests/support-simple.spec.ts`. PostgreSQL tests verify competing claims,
persisted assignee/status and SLA separately from synthetic browser fixtures.
Browser scenarios cover 1366x768, 1920x1080 and 390x768, attachment links,
dialog/note/history separation, draft privacy and resolution. Fixture results
are not installed staging or production acceptance.
`test_support_live_regressions.py` additionally covers a long noisy history,
public/private stream separation, mandatory admin self-claim and competing
legacy claims. The no-DB companion checks stale status/owner/scope denials.

Phase-one completion/identity regression coverage also includes
`test_phase1_completion_no_db.py`, `test_phase1_completion_api.py` and
`test_phase1_resolution_metadata_no_db.py`. Additive Studio publication and
preserved question/SLA branches are described in
[the catalog procedure](HELPDESK_PHASE1_CATALOG.md).

Requester steps place fields, saved answers and actions in normal document flow
so action/back controls cannot cover inputs or answers. Acknowledged
successful terminal sessions retire only their matching saved resume handle;
uncertain submissions retain recovery, while a later new request can start fresh.
