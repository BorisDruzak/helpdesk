# Unified Ticket Implementation Plan

**Goal:** Merge the nine annotated advanced ticket capabilities into the ordinary support ticket.
**Architecture:** Retain list-page queries, mutations and authorization. Compose the existing inspector inside SimpleSupportTicket; drive inspector content from its tab rather than the former full-page layout mode. Extend the existing queue component and reuse provider-owned device/profile data.
**Tech Stack:** React 19.2.5, React Query 5.99.2, TypeScript, existing CSS and Vitest/Playwright.
**Spec:** ../specs/2026-11-09-unified-ticket-design.md

## Constraints and review focus

- Preserve unrelated dirty Studio/catalog files and existing server permission checks.
- Distinguish missing service/profile/provider data from unavailable reads; never use numeric IDs as user-facing names.
- Inspector navigation must retain conversation drafts and expose full tools/SLA/passport capabilities.
- Retain every authorized ticket action, queue filters, visibility markers and column preferences.
- Verify collapsed queue, small-screen inspector, long content and ticket switching without horizontal overflow.

## Implementation

- [x] Add failing regression coverage for the default inspector, compact next action, removed mode button, SLA risk queue filtering and Russian quality states.
- [x] Compose the inspector, move description/form/public result into its context tab, unify navigation and decouple expanded content from layout mode.
- [x] Transfer authorized ticket actions, compact next action and collapsible queue with risk filtering and full-queue navigation.
- [x] Merge device/agent context and improve service/requester projection using existing trustworthy data; localize quality and distinguish linked-problem errors.
- [ ] Run focused component tests, TypeScript/build, workspace verification; capture browser evidence at 1366×768 and 1920×1080 with console/network checks.
- [ ] Review task diff and update CODEMAP/PLANS/evidence; deploy only through the applicable staging release procedure if available and validated.

GitNexus was attempted at the configured MCP endpoint but timed out. A read-only builder review identified inspector mode gates, unavailable service registry fields, hardcoded agent versions and quality error handling; these are included above.
