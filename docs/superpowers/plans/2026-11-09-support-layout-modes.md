# Support layout and queue modes implementation plan

**Goal:** Keep support navigation, ticket queue and SLA inspector readable and reversible at narrow sizes.

**Design:** Actor support. Primary job work on a ticket without losing the queue or draft reply. List + Detail workspace; navigation is a temporary overlay when unpinned. Three explicit queue modes share the existing list: collapsed rail, compact list alongside the open ticket, full queue with a visible return to the selected ticket. Full mode preserves selection and draft state rather than navigating away. Direct queue arrival has no fabricated current ticket. Keep existing actions/ticket view and expert tools.

**Tech:** React19.2.5, Router7.14.1, existing account/workspace-scoped panel storage and CSS container queries. No dependencies, migration or API change.

## Constraints

- Work in current dirty checkout without changing unrelated Studio work or ordinary index. Build a task-only immutable candidate over actual staging parent.
- Staging only; no production. Preserve services, schemas, tickets, assignees, commands/consent gates, original user tabs and typed replies/attachments during mode changes.
- Support navigation defaults to collapsed when unpinned, expands on pointer approach/keyboard focus and overlays content. Adjacent manual expand and pin buttons remain accessible. Pin state is account/workspace-specific; old stored preferences and blocked storage remain safe. Admin/requester navigation retains current behavior.
- Full/compact/collapsed controls always explain the active mode. Return works with a selected ticket; direct full queue without a ticket invites selection. Compact mode falls back to a small recent-ticket strip on mobile without replacing the conversation.
- SLA overview and related summaries respond to inspector width rather than whole window. No letter-by-letter labels, clipped values or horizontal document scroll; adapt font/spacing and stack cards when narrow. Do not change timing values/calculations.
- Preserve URL/history/deep-link behavior, queue filters/actions, draft reply text and attachments. Avoid resetting selected-ticket query state when merely changing queue presentation.
- Verify1366/1440/1920 and390, narrowed/resized inspector, light/dark, hover leave/focus/Escape, pin reload/account isolation, and round-trip modes with an unsent reply.

## Steps

- [ ] Capture baseline and staging data/identity.
- [ ] Add failing tests for auto-hide/pin, legacy storage and reversible queue modes.
- [ ] Implement navigation behavior/persistence and three-mode queue controls without changing ticket mutations.
- [ ] Extract or mark scoped SLA panels and apply width-based layout/type rules.
- [ ] Focused unit/TypeScript/build and native responsive/interaction regression checks.
- [ ] One independent final review; resolve confirmed findings in one scoped wave.
- [ ] Canonical guarded staging update with verified backup/restore and source/artifact/health validation; new-tab live read-only acceptance and preservation report.

## Decisions

Proceed from the user's concrete three screenshots without another design approval. Apply hover/pin to support, preserve other workspaces. New pin flag extends existing v1 preferences without a migration. Full mode keeps the open ticket mounted in the workspace state; no guessed return target when arriving directly. GitNexus unavailable: verify boundaries in source/tests. A mobile compact strip preserves both queue and conversation.
