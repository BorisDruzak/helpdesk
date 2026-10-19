# Everyday support workspace

The existing `/app/tickets` and `/app/tickets/:ticketId` routes open the simple
operational layout by default. `TicketListPage` retains its query cache,
realtime subscriptions, attachment upload and typed mutations. Components in
`webapp/src/pages/tickets/components/simple-support-*` provide the queue,
three-area ticket and conversation. `simple-resolution-form.tsx` presents policy
fields and optional internal information.

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

The compact list has **Открыть всю очередь**; it uses the existing full-list route
and retains search/filter state. Ticket mode reuses the existing inspector with
context, device, SLA, knowledge, tools and passport tabs. Both sidebars support
pointer resizing and arrow keys, with double-click/Home/Enter to reset. Widths
persist through the existing layout preference. On small screens the inspector
opens from **Сведения**; the full queue remains reachable from the ticket header.

## Queue and actions

Five filters use server-side smart views before the queue limit: `open`, `new`,
`waiting`, `completed`; Mine uses `scope=mine` with `smart_view=open`. Resolved,
closed and canceled tickets belong to Completed. Waiting includes user, vendor
and internal-team waits. Approval has its own contextual action. Existing smart
views, saved columns and bulk operations remain in the additional mode.

The queue and ticket use one `POST /api/web/support/tickets/{id}/status` command
with `to_status=in_progress` to take/start work. No separate assignment request
is combined with it. Status and assignment become visible after success and
refetch. The server locks and refreshes the ticket before checking ownership,
permissions and the canonical transition. Unassigned work also requires
`ticket.assign` and existing queue-membership assignment checks. Concurrent
operators cannot silently take the same ticket. An administrator can help with
assigned work without changing its assignee.

Queue items and ticket `actions` expose the additive `take_in_work` object
(`allowed`, `reason_code`, `reason`). It evaluates the same permissions,
ownership, queue membership, active-load limit and workflow transition used by
the command. Queue projection caches reads for this request only. The status
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

The Messenger layout keeps only the message feed scrolling, with the editor
anchored below it. Bubbles have bounded line lengths, sender/time labels and
date separators. Description and structured answers open in a keyboard-accessible
dialog; an identical initial chat message is collapsible. Attachments retain
their canonical download links. Ctrl/Command+Enter sends an allowed nonempty
draft, while Enter inserts a line break. New messages preserve the reading
position when the operator has scrolled back and offer a return-to-latest button.

## Resolution and additional functions

Resolve opens one form using `actions.closure_requirements`, without imposing
extra mandatory fields absent from policy. Missing evidence or passport
requirements lead to the existing passport workspace. The server continues to
enforce workflow, approval, closure and requester-confirmation policy. Resolved
and closed remain separate states. An agent is not required for ordinary support.

Additional mode retains tools, SLA, passport, Quality, saved queue views and bulk
actions; returning to ordinary work is explicit. `?advanced=1` directly opens
those existing surfaces. Ordinary entry ignores old expanded-mode preferences.
No API, event history or subsystem is removed. No migration or dependency added.

## Verification

Targeted coverage: `test_support_work_no_db.py`, `test_support_work.py`,
`test_support_operational_views_no_db.py`, the `simple-*` component tests and
`webapp/tests/support-simple.spec.ts`. PostgreSQL tests verify competing claims,
persisted assignee/status and SLA separately from synthetic browser fixtures.
Browser scenarios cover 1366x768, 1920x1080 and 390x768, attachment links,
dialog/note/history separation, draft privacy and resolution. Fixture results
are not installed staging or production acceptance.
