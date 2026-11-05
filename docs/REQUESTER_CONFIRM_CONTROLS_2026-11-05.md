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

Staging release and final receipt: pending canonical installation. Private evidence
is under `tmp/requester-confirm-controls-20261105`. Existing unrelated Studio work
is preserved and excluded from this change.
