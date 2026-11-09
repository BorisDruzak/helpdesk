# Settings refactor implementation plan

Goal: fix the audited settings defects, separate personal preferences from service configuration, deploy to Helpdesk staging and validate in a browser.

Spec: `tmp/settings-audit-2026-11-10/ANALYSIS.html` and the user's explicit implementation/deployment request.

Architecture: `/app/settings` is personal preferences, with no dependency on the service-settings read API or management permissions. `/app/admin/settings` keeps service configuration behind the existing admin workspace and backend permissions. Existing notification and service APIs remain authoritative. No new dependencies, schema changes or Endpoint ownership changes.

Actors / jobs: support changes own notifications and browser workspace preferences; admin configures service policies; auditor reads existing authorized configuration. Settings archetype: grouped sections, explanatory text, visible save/error state; list/detail for service objects.

## Tasks

- [x] Regression tests: new queue/policy/calendar/result POST instead of updating first existing entity; actual alerts response; missing duration values; draft retention and cancellation; notifications without management permissions; failures distinct from empty data.
- [x] Fix the defects. Use explicit create selection, sparse duration drafts with validation, actual alert DTO and dirty-state protection against refresh/navigation. Keep server authorization intact.
- [x] Separate personal and service page entry points; extract model, controller and bounded section components; grouped URL-addressable service navigation. Personal screen reuses browser push and current notification preference APIs. Workspace controls reuse existing account-scoped panel preferences; new preferences without a working consumer are excluded.
- [x] Improve duration labels/units, readable copy and advanced-only raw/debug content. State whether service API is disabled; do not fabricate zero configuration.
- [ ] Update route/navigation tests, CODEMAP and this ledger; run workspace sanity, focused Vitest, TypeScript/build, fixture browser checks at 1366x768 and 1920x1080 and full frontend unit suite.
- [ ] Independent review of task-only diff; compose immutable candidate over actual staging parent, preserving independent source. Commit on a task branch using a separate Git index, without changing shared checkout HEAD/index. Deploy with canonical release script and expected-parent guard, then live-browser acceptance and evidence.

## Review focus

Create mode with a nonempty list; stale refetch while dirty; partially missing duration rows; failed preference reads/saves; support actor without service-management rights. Tests must exercise these conditions.

## Constraints and rulings

- Work inside the existing checkout; preserve parallel edits. GitNexus unavailable in tool inventory; verify dynamic boundaries in source/tests. Context7 consulted for pinned React Router 7.14.1 and TanStack Query 5.99.2 behavior (closest available 7.13.0 / 5.90.3 docs).
- Implement the requested fixes and separation; shifts, new delivery channels and quiet-hour server policies require separate product/runtime work and are not invented as nonfunctional toggles.
- Staging target is only `osn-admin@192.168.101.118`, isolated `/opt/helpdesk-staging`. Requested deployment means retain the deployed staging service for use. Production is out of scope.

## Verification / handoff

Implementation pending. Audit evidence is current-thread baseline, not proof of the changed version.


## Current verification

Focused settings, navigation, router, shell and sidebar checks: 79 passed / 7 files. Includes delayed-refresh selection for all five entity types, deleted routing identity, workflow event snapshots, internal/SPA draft guards and independent form saves. Root full frontend suite: 1361 passed / 3 failed in unchanged `request-template-studio-catalog.test.tsx`; same three failures reproduced against unchanged staging-parent Studio source. These failures concern service-map save, conflict retention and auditor Studio inspection, not settings. Existing service runtime write-disable switch is respected in the UI; workflow profiles retain their separate existing permission contract. Staging flags and permissions are not expanded. Final exact-candidate build and live acceptance are recorded separately under tmp/settings-refactor-20261110.

Exact composed candidate: TypeScript/Vite build passed; 59 focused tests / 6 files passed; 3 fixture-browser tests passed (1366x768, 1920x1080, API failure). Parent-only verification reproduces 4 fixture failures: 3 Studio catalog cases and 1 obsolete requester-shell text expectation. A cold auditor Studio route timing failure in the initial candidate run passed on focused repeat (4 auditor route variants passed); no product change was made to hide it. Final review found no blockers. No full CI gate or production deployment requested.
