# Unified Users Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task.

**Goal:** One understandable person/account/access workflow and separate reference registries.
**Architecture:** Reuse canonical registry and access repositories; add one atomic admin account provider. Compose a users workspace with existing advanced registry operations and canonical group editor, and remove duplicated registry tabs.
**Tech Stack:** React 19.2.5, Query 5.99.2, Router 7.14.1, aiohttp, SQLAlchemy.
**Spec:** ../specs/2026-11-06-unified-users-design.md

## Global Constraints
Preserve unrelated dirty files; no dependencies/migrations/production deployment.
Admin-only mutations, no raw secrets in responses/audit, no permission weakening.
Russian labels, explicit saves, readable responsive layout.

## Review Focus
1. Account-less people, account-only records and multiple linked accounts.
2. Incorrect login casing/duplicate ownership and archived people.
3. Inactive queues/groups and inherited queues vs direct assignments.
4. Partial save failure, stale drafts and selection changes during a request.
5. Existing deep links and advanced registry operations remain reachable.

### Task 1: Atomic person/account provider
Files: new server/web_api/user_account_handlers.py, service/DTO as necessary,
server/routes.py, focused server tests. Interface: GET/PUT
`/api/web/admin/users/{person_id}/account` as specified in design.
- [x] Write and run failing validation/authorization/atomicity tests.
- [x] Implement provider with existing repositories and one transaction.
- [x] Run focused new and adjacent auth/access tests.

### Task 2: Unified user card and list
Files: new webapp/src/features/users/* and pages/admin/users-page.tsx and tests.
Consumes registry/access data and Task 1 contract. Produces AdminUsersPage;
parent task integrates routes and registry advanced tools.
- [x] Write failing primary workflow and error/identity-selection tests.
- [x] Implement compact searchable list and Profile/Account/Permissions card.
- [x] Reuse access group editor/reference/audit without a duplicate user list.
- [x] Run component checks, provide fixture state for browser acceptance.

### Task 3: Navigation and registry ownership
Files: navigation/router/page exports, registry-page and matching tests/docs.
- [x] Test distinct Users/Registries entries and legacy access redirect.
- [x] Extract registry person operations into Users-only advanced subview;
      preserve devices/claims/quality operations in Registries.
- [x] Remove duplicate people/access/password/profile tabs from Registries.
- [x] Update CODEMAP/workflow docs/PLANS and run affected regressions.

### Task 4: Integration and evidence
- [x] Build frontend and run focused frontend/backend suites + workspace sanity.
- [x] Browser validate isolated fixture with role/queue persistence, errors,
      selection isolation and screenshots at 1366x768 and 1920x1080.
- [x] Review complete task diff and report evidence and live acceptance limits.

Verification and known unrelated full-suite failures:
../../ADMIN_USERS_VERIFICATION_2026-11-06.md.
