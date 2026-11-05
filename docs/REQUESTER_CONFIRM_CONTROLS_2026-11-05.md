# Requester confirmation controls — 2026-11-05

## Failure and cause

The employee saw the latest support message asking to use the buttons below, but
only a read-only conversation notice was visible. Read-only staging evidence for
T-000075: `resolved`, both confirmation-pending markers true, no requester-action
policy opt-out. The support UI also reports awaiting employee confirmation.

`ticket-chat-page.tsx` rendered `TicketResolutionPanel` **before** the conversation,
inside `#requester-chat-content`. Scrolling to the latest message moved the controls
out of view. The read-only footer made the missing visible action more confusing.

## Fix

Solution actions now occupy a compact footer outside the transcript scroller and
remain present in description/history view. Confirmation, optional rating and
problem-not-solved controls wrap on narrow screens. Expanded forms have bounded
scrolling. Read-only text appears only without a reply or solution action.

Server-provided action flags, mutation handlers, ownership/confirmation policy and
401/403/404 denial checks are unchanged. No ticket status or confirmation was
submitted for a real employee during this work.

## Verification

- Failing regression observed before moving the panel.
- `pnpm --dir webapp test src/pages/requester/ticket-chat-page.test.tsx src/pages/requester/tickets-panels.test.tsx src/pages/requester/tickets-page.test.tsx src/pages/requester/ticket-context-panel.test.tsx`: **25 passed**. Includes hiding cached granted controls after401/403/404 and retaining controls in description view.
- `pnpm --dir webapp build`: passed.
- `python scripts/verify_workspace.py`: passed.
- `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp test:e2e tests/requester-resolution-actions.spec.ts --output=../tmp/requester-confirm-controls-20261105/browser-final`: **3 passed** at1366x768,1920x1080,390x844. Forty-five-message history scrolls to the last support message while confirm/reject remain in viewport. Description view, rating expansion/collapse, confirmation POST and return-to-work POST are checked with synthetic fixtures; no console/page/unexpected-request errors or horizontal overflow.
- Read-only independent review: no blocking findings; permission-denial regression and rating-expansion coverage strengthened afterward.
- Canonical requester contract updated. No API, schema, dependency or CODEMAP entrypoint change. Full CI, backend DB mutation tests and production rollout are outside this UI-placement fix.

## Installed staging acceptance

Branch: `codex/requester-confirm-controls`. Initial fix:
`8202ab17a9a9059e0378178c9c3bb87f5ce465be`,
`fix(requester): keep solution decisions visible below chat`.
Installed runtime: `860c5677f26f5aabc575089819cfa41da1782124`,
`fix(requester): retain visible decisions on current staging baseline`.
The latter preserves the independently deployed Studio baseline
`dc60f34573602be834bfeebbf58424db6ccbb929`; its first-parent diff contains only this
task's7files. No Studio migration or feature was rolled back.

Canonical `scripts/deploy_helpdesk_release.py` rebuilt the exact Git source with
its frozen lockfile and installed only on isolated staging101.118. Before release,
schema155 backup was verified (13697988bytes, SHA256
`59577427b117b34eaf7df9cf7d5def754765897f35a415678c5d8189d655ff10`).
Installed source identity and all4frontend source/test hashes match. Schema155,
strict-CA HTTPS health200 and Helpdesk/Endpoint/worker active states confirmed.
Business counts unchanged across this release: tickets76, events18122, artifacts5,
users160, people44. No new profile, message or ticket decision was submitted.

Live read-only browser opened the current admin session's own synthetic T-000065,
scrolled to the latest support message and observed all3decision buttons in the
viewport outside the transcript. Live width1280, scrollWidth1280; console errors0.
The auxiliary verification tab was closed, preserving the user's original support
tab. The real T-000075 remains for its requester to decide.

Private evidence: `tmp/requester-confirm-controls-20261105`, including verified
backup, source/health receipt, canonical deploy log, fixture screenshots and
`live-pinned-controls.jpg`. Production unchanged; staging left active.

During freezing, a concurrent Studio staging operation occupied the shared Git
index. An accidental unpublished local commit was immediately restored atomically,
preserving all49staged files. Studio's own commit proceeded normally. This task
then used a private index/branch and waited for that deployment before installing
its compatible follow-up. Shared HEAD and index are not owned by this task.
