# Requester registration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Register an ordinary requester through guided personal/profile/password steps and land in a ready requester workspace.

**Architecture:** Preserve the existing password login and role authority. Add bounded requester signup with server-generated login, atomic own-profile creation and a durable retry receipt. Reuse requester profile validation/rendering for existing incomplete accounts. Import only department names and archive exact synthetic records while retaining existing references.

**Tech Stack:** Python/aiohttp, SQLAlchemy 2.0, PostgreSQL/Alembic, Pydantic 2, React 19.2.5, React Router 7.14.1, TanStack Query 5.99.2, Vitest/Playwright. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-04-requester-registration-design.md`, with the user's explicit correction: completed signup opens the requester home, never the ticket form.

## Global constraints

- Only this checkout and isolated Helpdesk staging `192.168.101.118`; leave staging running.
- Preserve pre-existing dirty changes and the registration configuration utility from the previous task.
- New accounts always use `user`; no role/person selection, inferred AD binding or employee import.
- Three steps: ФИО → отдел и контакты → пароль. Completion goes to `/app/requester`.
- Base login `ipetrov`, collision suffix starts at `2`; keep existing logins unchanged.
- Department label «Отдел»; no requester location requirement or erasure of historical location values.
- One list of 30 departments; normalize only the three documented spelling variants.
- Canonical staging deploy/lifecycle/backup and audited Registry operations; no runtime code patching.

## Review focus

- A lost signup response must not create another suffixed account on retry.
- Concurrent namesakes must get separate unique accounts without joining an existing person.
- Old profile schemas must not retain an invisible required-location blocker.
- Editing a profile must not clear hidden old location/custom fields.
- Old synthetic catalog references remain readable but unavailable for new selections.

## Task 1: Profile completion without a location

**Files:** `server/registry/profile_schema_service.py`, `server/requester/identity_service.py`, `server/registry/registration_form_service.py`, `webapp/src/features/requester/profile-runtime/index.tsx`, `webapp/src/pages/requester/profile-workflow.ts`, related profile tests.

**Interfaces:** Existing profile payload accepts omitted `location_id`; schema projects `department_id` as «Отдел» and location as optional/hidden. Existing stored location is preserved unless explicitly changed through an authorized surface.

- [x] Add regression tests for `missingProfileFields` without a location, saving a new profile without location, legacy schema normalization and preservation of an existing hidden location.
- [x] Run focused tests and confirm the current location requirement fails the new cases.
- [x] Remove the hard-coded location requirement and align schema/client fallback/validation. Validate an explicitly submitted nonempty location through the existing Registry scope. Preserve hidden metadata.
- [x] Filter active department/location choices in the requester lightweight options without changing administrative historical lists.
- [x] Run profile/schema/registration-option tests; update owning docs/CODEMAP with the behavior change.

## Task 2: Server-owned requester signup

**Files:** create `server/auth/requester_registration.py`, focused `server/tests/test_requester_registration_no_db.py` and `server/tests/test_requester_registration_db.py`; modify `server/web_api/session_handlers.py`, `server/web_api/dto/session.py`, `server/routes.py`, `server/auth/middleware.py`, `server/app/repos/ui_users_repo.py`, `server/app/db/models.py`; add migration after actual current head (`151` observed during planning).

**Interfaces:**
- `registration_login_base(first_name: str, last_name: str) -> str` performs the documented transliteration.
- `GET /api/web/session/registration-options` returns a bounded safe signup profile schema and active department choices only when registration is enabled.
- `POST /api/web/session/register-requester` accepts UUID `request_id`, name parts, department/contact/profile values and password/repeat. Returns actual `user_login`, `actor_role='user'` and ready-profile status. No session token is exposed in the response.
- `UiUsersRepo.create_user(..., commit: bool=True)` retains existing behavior by default; signup can flush within its transaction.
- A durable registration receipt binds request ID, created login/person and a fingerprint of non-password signup fields. Replays verify the supplied password using the existing verifier before returning the same login. Raw passwords never persist in receipts.

- [x] Add failing transliteration tests for `Петров/Иван → ipetrov`, `Ёлкин/Юрий → yuyolkin`, compound surnames, signs and unsupported/empty input.
- [x] Add DB regressions for concurrent collision suffixes, duplicate request ID, changed payload/password on replay, rollback after profile failure, normal role, archived department and forbidden role/person fields.
- [x] Implement canonical account/profile creation in one transaction, a receipt lock for repeat request IDs, and conflict-safe unique login allocation. Retain default repository transaction behavior for all old callers.
- [x] Expose the two bounded signup routes. Keep the legacy registration route compatible for incomplete-account recovery; preserve rate limits, disabled flag, validation, audit and same-origin guards.
- [x] Run no-DB targets and focused isolated PostgreSQL tests using the existing protected test harness. Verify migration upgrade/head and cleanup of the isolated test database.

## Task 3: Guided browser registration and existing-profile setup

**Files:** `webapp/src/features/auth/register-page.tsx`, `webapp/src/features/auth/api.ts`, new focused `registration-*` components/hooks/helpers, `webapp/src/pages/requester/profile-page.tsx`, profile components; corresponding component and browser tests.

**Interfaces:** signup API types match Task 2. Client retains a per-attempt UUID across uncertain retries and uses the returned actual login for the existing `loginWebSession` command. Login/session-provider lifecycle stays canonical. Successful onboarding navigates only to `/app/requester`.

- [x] Add failing component tests for each step, preview login, validation/back navigation, no password storage, API uncertainty/retry, successful canonical login and home navigation despite a `next` ticket path.
- [x] Build a compact accessible wizard: names; department/contact/profile fields; password and summary. Field errors stay visible and focusable. Show actual generated login on success/home.
- [x] Resume an existing incomplete account through profile setup without creating another account; existing complete-account login is unaffected.
- [x] Add browser regressions for ready profile/home, no ticket creation/navigation until clicking «Создать обращение», refresh/retry recovery, existing incomplete account, 1366×768/1920×1080/390px layout and no overlap/body overflow.
- [x] Run focused Vitest, TypeScript/build and browser specs from the current compiled bundle. Capture console/network evidence separately from mocked fixtures.

## Task 4: Department catalog and staging acceptance

**Files:** new `scripts/helpdesk_requester_departments.py` plus focused tests and names-only data under the subsystem's existing data convention; owning Registry/registration docs. Private extraction/evidence stays in `tmp/onboarding-20261104`, not committed.

**Interfaces:** a read-only plan reports the exact existing synthetic IDs/statuses, proposed 30 names and baseline fingerprint. Apply requires the same fingerprint, staging database guard, explicit actor/reason, fresh private backup and a transaction. Use `RegistryAdminOperationsService` create/archive methods; keep old person/device memberships and ticket snapshots intact.

- [x] Test normalization, 30-name uniqueness, plan-only behavior, idempotent second apply, stale baseline rejection, foreign database rejection, exact synthetic-only archival and retained references.
- [x] Implement the names-only import and audited archival. Do not infer employees, real department assignments or department merges beyond the three documented name aliases.
- [x] Review the complete task diff and focused checks; inspect staged files and `git diff --check` before each atomic commit. Preserve unrelated changes and report full SHAs.
- [x] Take the canonical staging database backup, install the committed app/migration through `deploy_helpdesk_release.py`, then apply the reviewed catalog plan. Retain a private restoration receipt.
- [x] Verify exact deployed SHA, health/capabilities, 30 active real departments and no active synthetic choices. Check prior row/reference counts and repeat import no-op.
- [x] Run a live owned synthetic signup through profile completion, home and explicit ticket-form opening; verify `user`/requester-only workspaces, filled profile, no auto-created ticket, no location requirement, OIDC initiation with no MFA request. Fresh real-credential AD login was not repeated; record this verification limit.
- [x] Run `python scripts/verify_workspace.py`; update acceptance notes and leave staging running. Production deployment/full CI are outside this task.

## Plan review

Spec coverage is assigned to Tasks 1–4. The five review-focus cases have explicit
profile, DB, API or browser assertions above. A schema migration is required for
the durable signup receipt; it must be called out in the release receipt and
tested against the actual Alembic head before deployment. Native execution in
this session preserves the current checkout and avoids concurrent source edits.

## Acceptance receipt

Completed on staging at application SHA `153dc3faf16f2759469c84758f131d58a4f538ca`.
Migration152, backup, 30 active departments, 29+29 archived choices, preserved
history and owned live signup/home/manual-form acceptance verified. Service
left running. Full evidence and limitations: `docs/UX_REGISTRATION_ACCEPTANCE_2026-11-04.md`.
