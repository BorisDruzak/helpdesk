# Unified support ticket — 2026-11-09

The ordinary ticket now contains the retained full inspector with one navigation row,
a collapsible working queue with SLA risk, and a compact next action. Diagnostics,
SLA/OLA, knowledge and passport stay inside the same conversation layout. The
“Дополнительные возможности” button was removed. Saved views and mass queue
operations remain available through “Виды и действия очереди”.

Context presents the known service name or submitted form title, answers, description
and public result; raw category/service IDs are no longer shown as names. Requester
contacts use the existing actor-scoped profile and declared-account projection; no
account, person, rights or device binding is changed. Missing contacts remain unknown.
Device and agent share one section and use the actual supplied agent version; loader
version remains “Нет данных” because the projection does not supply it. Quality and
problem status labels are Russian; missing quality and failed problem reads do not
claim zero issues. Deadline history separately requests recent history and filters
SLA/OLA types; it is bounded by the existing timeline API, not a complete audit export.

## Verification

- `pnpm --dir webapp test src/pages/tickets/list-page.test.tsx src/pages/tickets/components src/features/queues/support-workspace-mappers.test.ts`: 127 passed / 7 files.
- Frozen candidate `pnpm --dir .../source/webapp build`: TypeScript and Vite passed; existing large-chunk warning.
- Frozen candidate `pnpm --dir .../source/webapp exec playwright test tests/support-simple.spec.ts`: 15 passed. Covers 1366×768, 1440×900, 1920×1080 and 390×768; lifecycle, unavailable take, drafts, attachments, public result, queue widths/collapse, tabs and passport without leaving the ordinary card.
- `python scripts/verify_workspace.py`: passed. `git diff --check`: passed.
- Read-only review found and verified fixes for controlled inspector Escape and known problem status labels; their RED→GREEN regressions pass.

The shared-workspace full frontend attempt encountered unrelated dirty Studio fixture
failures. A frozen candidate full run was interrupted after the pre-existing requester
shell label test and an intermittent Forms Builder required-field preview test failed.
The same requester-shell failure was reproduced on the untouched installed baseline
90fe32ecedda8a663d2d930866a4ada1d787ca56; the Forms Builder test passed in isolation on
that baseline. This task does not claim a green full suite or full CI/release gate.

Fixture browser logs distinguish supported reads from missing fixture routes: the
spec supplies timeline/read/problem responses for endpoints that the static fixture
omits. Lifecycle tests assert no page/console errors or failed HTTP/network reads.
Windows fixture shutdown emits occasional Proactor ConnectionResetError after a
browser closes; browser assertions passed. Live staging evidence is recorded separately.

## Isolation and release

Candidate overlays only the task's explicit files on the installed staging baseline.
CODEMAP/PLANS additions are applied independently so unrelated dirty documentation
and Studio/catalog changes are excluded. Normal checkout branch/index are preserved.
No new route, migration, dependency or cross-repository HTTP contract.
GitNexus MCP was attempted at its configured endpoint and timed out; source and tests
were used for this UI-only change. Production is outside this task.

Evidence: `tmp/unified-ticket-20261109/` (candidate manifest/diff, focused/build/browser
logs, screenshots, baseline reproduction, backup/restore and installed receipt).
