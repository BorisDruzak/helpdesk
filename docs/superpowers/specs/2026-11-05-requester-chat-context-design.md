# Requester chat: visible handling context

User request: an employee opening their ticket must see its current status,
assigned specialist, SLA response/resolution deadlines, associated device and
processing progress. Retain the simple first-stage workflow and usable chat.

## Observed evidence

The user-provided current screenshot shows a narrow message column, an isolated
bottom composer, no handling context, and an access-code system notice attributed
to the requester. Current operator-browser capture shows status/assignee/SLA/device
on its right; the requester implementation hides description/history behind a
button and renders only messages. Detail API already returns safe public events
and deadlines; its10s polling exists. Requester DTO lacks handling context and
the message renderer mistakes admin/staff/operator replies for user messages.

## Intended behavior

- Header: readable ticket number/title, current public status badge, assigned
  specialist. Show who acts next separately from the ticket status.
- Main: readable conversation with public system progress events in chronological
  order; do not duplicate chat events. Identify employee/support/system correctly.
  Preserve attachments, multiline text, result, optional feedback and existing
  authorized actions. Sticky composer stays with the conversation column.
- Context: compact persistent desktop side panel with processing, assignee,
  first-response and resolution SLA, and device. Mobile keeps these accessible
  above the conversation without horizontal overflow. No new approval/action flow.
- SLA: reuse canonical support timer semantics for pauses, accumulated pause
  seconds, stopped/completed targets, recorded breaches and missing policies.
  Effective deadline/remaining time must agree; missing SLA is explicitly unset.
  Do not fabricate a resolution promise, online state or work progress.
- Device: only associated-ticket descriptor/current authorized ownership. Current
  presence comes exclusively from the Endpoint port, validates exact device ref,
  and is unavailable on provider error. Never substitute old local agent presence
  or expose another employee's current device after ownership changes. No-device
  tickets remain fully supported. No raw IDs, diagnostics, operation payloads,
  local logs or internal notes enter the requester summary.
- Existing10s active-tab polling updates assignment/status/SLA/history without
  losing a draft or jumping when the user reads older messages. Refresh failures
  preserve cached conversation and display a clear retry state.

## Boundaries

New authenticated requester detail `handling` sibling is built only after existing
ownership verification; anonymous/public-token responses remain unchanged. Current
template visibility policy still applies. No global role/grant/binding changes,
business transitions or schema/dependency additions. Staging deployment only;
leave the authorized services running. Test ownership rejection and redaction.

Prior follow-up is complete: WorkTime return link deployed at
0554e70b0d4c679173d502af6000cc53ac17f27f; login bdryzhak verified active.
Device-binding diagnosis: staging service credential lacks device-binding.redeem
(actual403); local agent origin is production. No rights/agent config changed.
Production binding acceptance remains unverified; no production mutation approved.
