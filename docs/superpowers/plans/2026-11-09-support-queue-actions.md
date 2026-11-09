# Compact support queue actions implementation plan

> Execute inline with focused RED/GREEN tests and one final independent review.

**Goal:** Integrate the advanced action centre into the primary support queue and localize its operator interface.

**Design:** Support operator; primary job choose and open the next actionable ticket. List + Detail archetype, at most two content zones. The primary queue owns one compact heading/search/filter surface and switches between tickets and actions. Existing action projection, consolidation, ordering, source counts, scope, queue/search API constraints, list/board modes and ticket links remain. The action detail is concise, with rare facts in disclosures; mobile stacks detail after list. The old `/app/support/advanced` route redirects to `/app/tickets?view=actions`. Remove its duplicate navigation entry. Keep approvals as a separate guarded workflow and explain manager approvals versus requester consent.

**Tech:** Existing React19.2.5, React Router7.14.1, TanStack Query5.99.2 and CSS; no new dependencies. Context7 Query v5.90.3 documentation is the closest indexed v5 reference; pinned repo versions prevail.

## Global constraints

- Preserve all dirty working copy/index work, services, drafts, tickets, assignees, audit and consent gates. Only staging deployment; no production access.
- No new API/migration or auth/operation mutations. Acceptance uses read-only live filters/navigation; mutating workflows remain covered by fixtures.
- All UI labels and enum values localized. Preserve backend enum values and technical IDs only in optional details where relevant.
- Common centered search and wrapping action filters; no horizontal body scroll; responsive1366/1920 and390 coverage, theme-compatible styles.
- Initial API failure must not look like zero tasks; refresh failure retains previously loaded tasks with a warning. Never claim source section counts are complete deduplicated task counts; expose source limits.
- Do not refresh the user's existing tabs. Use a new validation tab.

## Tasks

- [ ] Capture source/index baseline and current staging identity/data read-only.
- [ ] Add failing component/route tests for embedded actions, shared search, localized rows, scope/filter and error preservation.
- [ ] Integrate compact action view into SimpleSupportQueue/list-page; preserve ordinary ticket view and compact ticket-side list.
- [ ] Preserve old route as alias; remove duplicate nav entry; explain approvals/consent without weakening checks.
- [ ] Verify focused unit suites/TypeScript/build, native fixtures at target widths, keyboard and error states; inspect full task diff and docs/CODEMAP drift.
- [ ] Independent final review, resolve findings; freeze task-only candidate over actual installed staging parent.
- [ ] Canonical guarded staging deployment with backup/restore, source/artifact/health checks and new-tab browser acceptance. Record exact SHA, tests, preserved data, screenshots and limits.

## Decisions

The user's detailed screenshots specify the placement and density; proceed without another design approval. Keep one primary queue with ticket/action views rather than replace ticket operations with dashboard-only summaries. Cost: operators switch one compact tab to see action prioritization. GitNexus tools are unavailable; source and tests verify boundaries. Normal checkout stays in place; use an alternate release index and immutable source export to isolate the task.
