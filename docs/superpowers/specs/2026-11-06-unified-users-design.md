# Unified user administration

## Intent and accepted direction
The user explicitly requested implementation of the previously proposed unified
person card, and a visual/functional refactor into separate Users and Registries
navigation entries. The principal acceptance scenario is opening Marina
Zavarukha's person card, enabling/linking her account, assigning Support and
selecting a working queue without moving between administration pages.

## Structure
- `/app/admin/users`: searchable compact people list and selected person card.
  Card tabs: Profile, Account, Permissions. Account creation/linking, role,
  active status, direct queue membership and access-group membership belong here.
  Account-less people and unlinked accounts must remain discoverable.
- Users workspace secondary tabs: access groups, role/permission reference and
  audit (reuse the existing canonical editor), password reset requests and
  profile schema. Avoid two competing people lists.
- `/app/admin/registry`: overview, devices, bindings, registration claims,
  data quality, locations, departments, audiences and policies. No people,
  password-reset, profile-schema or access-group editor/summary tabs.
- `/app/admin/access` is a compatibility redirect to Users access settings.
  Existing contextual links to people must reach the unified person card.

## Card behavior
Profile uses canonical person editing and identity, merge/archive and device
context capabilities; retain existing safe advanced operations without making
technical identifiers the main workflow. Account allows creating a local login
with password or linking an existing unlinked login; existing logins cannot be
renamed or stolen from another person. Multiple linked accounts are selected
explicitly. Role labels are Russian; support is `Сотрудник техподдержки`.
Permissions selects active queues and groups by name and explains inherited
queue access separately from direct assignments. Explicit save with reason and
visible success/error preserves drafts on failure and during background reads.
Never display stored passwords or hashes. Avoid body horizontal scrolling;
stack list/card on narrower screens. Primary action visible at 1366x768.

## Provider contract (no schema migration)
Admin-only `GET /api/web/admin/users/{person_id}/account` returns standard success
envelope data `{accounts: UserAccount[]}` for linked accounts. Optional
`?user_login=<login>` reads an explicitly selected unlinked account's exact
direct assignments before linking; reject ownership by any other person.
Admin-only `PUT` on the same route receives `{user_login, password?, actor_role,
is_active, queue_ids: number[], group_ids: number[], reason}` and returns
`{account: UserAccount}`. `UserAccount` has user_login, actor_role, is_active,
queue_ids and group_ids. Role values remain user/support/admin/auditor.
The provider validates all targets, password policy, active person, active grant
targets, duplicate/case-insensitive login ownership and protects self lockout.
Account changes, verified person linkage, direct queues, groups and audit are
one transaction. Existing linked accounts may be edited, never implicitly moved.
Unselected inherited group queues are not removed as if they were direct grants.
Read/write failures must not masquerade as success/empty data. Password never
enters logs or audit. Existing auth/actor/visibility checks remain authoritative.

## Alternatives considered
Keeping two pages with cross-links leaves the broken person/account workflow.
Putting all registries and permissions on one giant page makes unrelated jobs
harder to find. The requested Users workspace plus separate Registries preserves
one owner for each task and reuses existing authorization/storage boundaries.

## Constraints and builder decisions
React 19.2.5, TanStack Query 5.99.2, Router 7.14.1 and existing aiohttp/SQLAlchemy
stack; no added dependency. Work in the existing dirty checkout, preserving all
unrelated work. No production deployment or live role grants requested; validate
with isolated fixtures/tests and report live acceptance limits honestly.
Builder owns component breakdown, layout details and backward-compatible links.
Backend contract is Helpdesk-local, not an Endpoint API change. GitNexus tools
are unavailable in this session; use bounded source/tests and record limitation.

## Verification
Focused backend tests cover authorization, invalid grant targets, atomic rollback,
ownership conflicts, role changes, password redaction and direct/inherited queues.
Component tests exercise account-less person -> support role -> queue -> save,
existing account editing, account-only search and server errors. Navigation tests
prove no duplicate entry. Real browser fixture validates Russian text, the
complete workflow, errors and responsive screenshots at 1366x768/1920x1080.
Run frontend build, relevant existing regressions and workspace verifier.
