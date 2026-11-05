# Helpdesk → WorkTime Login Implementation Plan

> Native execution with superpowers:executing-plans; one independent final
> security/diff review. Preserve current Helpdesk checkout and clean existing
> Endpoint staging-baseline worktree; no new checkout or concurrent implementers.

**Goal:** An employee registered/logged in to Helpdesk opens their own WorkTime
cabinet without another login; Helpdesk clearly offers its existing AD login.

**Architecture:** Endpoint-initiated state/PKCE flow, Helpdesk source-session
authority, confidential single-use exchange and separate WorkTime-only cookie.
Existing employee OIDC, DLP/admin and person histories remain independently scoped.

**Tech stack:** Existing aiohttp/SQLAlchemy2/PostgreSQL and FastAPI0.115/httpx/
Fernet/React. No dependencies added.

**Spec:** `docs/superpowers/specs/2026-11-05-helpdesk-worktime-login-design.md`.

## Constraints / review focus

Use fixed staging origin pair; no secrets in URLs/logs, no AD identity guessing,
no privileged/DLP handoff access. Preserve token rotation grace, source revocation,
Registry blocking and OIDC revalidation. Provider outage503 differs from revoked
authority401. CSRF must match selected session. Explicit verified AD login must
clear a shadowing handoff cookie. Local→AD promotion preserves one person/history.
Staging services remain running. Never modify/replay historical business receipts.

## Task1 — Helpdesk authority and protocol

Files: new `server/auth/worktime_authority.py`, `worktime_handoff.py`,
`worktime_handlers.py`; modify `auth_tokens_repo.py`, opt-in outage handling in
`auth/oidc.py`, `app/db/models.py`, migration153, `config.py`, middleware/routes.
Tests: new `server/tests/test_worktime_handoff_no_db.py`,
`test_worktime_handoff_db.py` and focused existing token/OIDC tests.

Interfaces: exact version1 exchange/introspect/people payloads from spec;
`AuthTokensRepo.verify_ui_token_hash(hash, *, commit=True)` shares canonical
rotation/expiry checks; handoff uses `commit=False` under its transaction.
`validate_oidc_session(..., raise_unavailable=True)` distinguishes remote outage
without changing legacy callers. Strict own browser cookie authorizes code issuance.

- [x] RED focused guard/PKCE/source validation tests, then minimal authority/
  models and single-use service implementation; verify GREEN.
- [x] Add bounded HTTP handlers, fixed form-post callback, rate limits/audit;
  test disabled flag, bad service auth, extra fields, source profile/account state,
  code replay/concurrent exchange, rotation and OIDC outage. Migration head153.
- [x] Update provider SSO contract/CODEMAP and preserve legacy auth tests.

## Task2 — Endpoint WorkTime-only consumer

Checkout: `C:/Users/admin-2/Documents/endpoint/.worktrees/worktime-recorded-release-20261030`.
Files: new `endpoint_server/auth/worktime_sessions.py`,
`auth/worktime_handoff.py`, `identity/worktime_client.py`,
`db/models/worktime_sessions.py`, migration0044; modify identity model, app
composition/config, WorkTime dependency/authorization and explicit OIDC promotion/
AD-switch marker. Add tests under `tests/server/test_worktime_handoff*.py`.

Interfaces: existing dedicated service credential/TLS client config; new typed
WorktimeAuthorityError distinguishes invalid vs unavailable. Prefix remains
`/api/employee/worktime`, session GET/DELETE under `/session`. New principal source
`helpdesk`; every unsafe request/logout calls existing CSRF check with its cookie.

- [x] RED source-client response/origin/replay/isolation tests; implement
  disabled-by-default settings, fixed login/form callback, durable flow/session.
- [x] Introduce explicit nullable-AD local identity kind, unchanged existing OIDC
  defaults; strict same-person local→verified AD promotion under lock.
- [x] WorkTime-only dependency/grants/authorization; self-only people; preserve
  original DLP/admin/session APIs. Verify cross-person, missing/mismatched CSRF,
  expired lease, provider outage and explicit AD recovery.
- [x] Test migration43→44, callback concurrent replay, history identity stability
  and existing WorkTime/SSO boundaries using isolated PostgreSQL only.
- [x] Update canonical OpenAPI, CODEMAP/SSO docs and consumer contract tests.

## Task3 — Browser flow

Helpdesk: existing `worktime-link.tsx`, session DTO projection, new continuation
page in auth routing; login-page label «Войти через AD» and domain description.
Endpoint: `EmployeePortal.tsx`, `employeeApi.ts`, existing tests; new WorkTime
session endpoint selection, own logout and primary Helpdesk/secondary AD login.
Companion/DLP retain their existing AD login and session behavior.

- [x] RED routing/link/session tests, then implement exact fixed continuation
  and matching CSRF source. Retain safe next routing and existing profile wizard.
- [x] Focused frontend tests/builds and browser desktop/mobile fixtures prove
  no second password prompt, intended identity, errors/reload and separate realms.

## Task4 — Reviewed staging release and live acceptance

- [ ] Independent final review of both diffs and contract/migration/auth scope.
  Run focused gates, workspace verification, full diff/check and atomic commits;
  preserve unrelated dirty state. No push/production/full fleet action.
- [ ] Fresh private backups for both databases, exact current revisions and
  WorkTime/business/auth baseline. Use canonical build/deploy/migration procedures,
  explicit staging flags and fixed origin configuration; never patch runtime files.
- [ ] Verify installed SHAs/digests, TLS, service health and schema revisions;
  preserve prior personnel/grant/session rows apart from expected audited checks.
- [ ] Live current Helpdesk user→WorkTime own cabinet→reload, without starting a
  day/correction/device action. AD button initiation and isolation checks; if no
  current AD credential proof available, report that precise limit.
- [ ] Record report, final own PLANS section and progress ledger; leave both
  staging services running.

## Design review rulings

Builder check found no fundamental blocker; three implementation rulings are
recorded in the spec: source hash validation/typed OIDC outage, CSRF from selected
cookie, and successful explicit AD recovery clearing the WorkTime cookie.
The user's latest approval covers the proposed one-time handoff and all local
registered employees. No additional design or routine deployment permission asked.
