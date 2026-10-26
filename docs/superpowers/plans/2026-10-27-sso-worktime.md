# SSO and WorkTime implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for
> independently owned tasks, with fresh reviewers at each stage. Execute
> continuously under the user's explicit authorization.

**Goal:** One AD account across Helpdesk and Endpoint, independent application
permissions, durable WorkTime and safe Windows/ALT companion notifications.

**Architecture:** Keycloak LDAPS/OIDC; independent BFF cookie sessions and
databases; Helpdesk RegistryPerson as person authority; Endpoint WorkTime as
separate business records alongside existing technical Activity Analytics.

**Tech Stack:** Python/aiohttp Helpdesk; Python3.12/FastAPI/SQLAlchemy Endpoint;
Authlib1.9.1 OIDC; PostgreSQL; React19.3/ReactRouter7.18.4; existing User Sensors.

**Spec:** ../specs/2026-10-27-sso-worktime-design.md; full user specification
attachment 87aaa703-54f4-4d12-ba9a-860d30bf7718/Вставленный текст.txt.

## Global constraints

- Separate repositories, PostgreSQL, users, services and release procedures.
- Preserve current uncommitted Endpoint work and all unrelated Helpdesk files.
- No self-written OIDC, login/email identity merge, browser/device token sharing.
- No mass AD/GPO/account migration, fleet rollout or organization-wide monitoring.
- Report UTC instants in Asia/Yekaterinburg; never equate UNKNOWN with absence.
- Subagent review and focused tests at each gate; Playwright for changed UI.
- No claims of real SSO, installed notification or update acceptance from mocks.

## Review focus

- Renamed/reused domain login cannot move historical tickets or WorkTime.
- A cookie, callback state or notification from another realm/person fails closed.
- Concurrent transitions from two devices cannot double count a person's day.
- Telemetry gaps and expired technical retention cannot erase personnel history.
- Disabled upstream identity, missing MFA and stale department grants deny access.

## A1: Helpdesk confirmed identity and OIDC

**Owner/files:** helpdesk_stage_a owns server auth/registry identity, models.py,
migration151, config/routes wiring, focused server tests and CODEMAP.

**Produces:** POST /api/integration/v1/identities/resolve per spec; confirmed
binding preserving UiUser key and RegistryPerson; persisted OIDC BFF session;
explicit password-login migration flag. No new employee registry.

- [ ] Test collision, exact subject, inactive person, no role escalation and
  preserved requester identity; observe RED before implementation.
- [ ] Implement schema, explicit confirmation/audit and limited service API.
- [ ] Implement Authlib flow, server-side transactions and upstream authority.
- [ ] Verify current login/reset/logout and new route negative paths; run
  disposable PostgreSQL migration/uniqueness/concurrent-link tests.
- [ ] Independent reviewer; fix reproduced findings, rerun focused checks.

## A2: Endpoint confirmed identity, realms and grants

**Owner/files:** endpoint_stage_a owns auth/oidc.py, employee_sessions.py,
authorization.py, db/models/identity.py, identity/helpdesk_client.py, migration
0040, config/main wiring, focused tests. Preserve device/service auth.

**Consumes:** A1 service response version1. **Produces:** ConfirmedIdentity
(UUID person_id, nullable department_id, exact issuer/subject/AD GUID),
EmployeePrincipal(identity,session), require_employee(request) with CSRF,
authorize_person(session,principal,person_id,action)->ConfirmedIdentity.

- [ ] RED tests for state/nonce/replay/PKCE, cookie substitution, missing MFA,
  inactive binding, outage and bounded strict identity response parsing.
- [ ] Implement maintained Authlib flow and separate durable employee sessions.
- [ ] Implement exact scoped roles; no automatic admin or cross-department grant.
- [ ] Run auth/config/console/device/service regressions and migration checks.
- [ ] Independent security review and corrected regression evidence.

## A3: Keycloak infrastructure

**Owner/files:** keycloak_infrastructure owns deploy/keycloak, tools/keycloak,
docs/operations/keycloak-sso.md, tests/deploy/test_keycloak*.

- [x] Read-only AD-MAIN inventory; no existing Keycloak detected.
- [ ] Prepare pinned independently isolated service/DB/user/TLS/backup assets,
  read-only LDAPS objectGUID mapper and three PKCE clients, privileged MFA.
- [ ] Validate assets, independent review, then deploy via reviewed procedure.
- [ ] Validate discovery/TLS/LDAP/MFA/logout with real pilot identity; redact
  evidence and record any unavailable private provisioning input accurately.

## B/C: WorkTime persistence and scoped API

**Owner/files:** worktime_backend owns endpoint_server/worktime, migration0041,
tests/worktime, docs/architecture/worktime-v1.md; sends router/model wiring.

**Consumes:** A2 principal/authorize_person. Actions worktime.read/write/approve/
hr/admin; roles employee/manager/hr/worktime_admin/endpoint_admin/dlp_officer.
**Produces:** /api/employee/worktime self/day/week/month/status/explanations/
corrections/schedules/team/approvals, fixed versioned DTOs shared with frontend.

- [ ] RED tests for FSM, overnight shifts, overlaps/two devices, idempotence,
  immutable corrections, scope checks and technical UNKNOWN preservation.
- [ ] Implement person-serialized events/status, schedule/holiday overrides,
  explanations, correction approval audit and durable daily/monthly totals.
- [ ] Reuse existing technical analytics only through verified temporal mapping.
- [ ] Implement durable eligible >=1200-second return requests; schedule,
  prior explanation/coverage and unknown identity suppress requests.
- [ ] Verify database migrations/concurrency and review every personnel route.

## D: Employee portal and independent DLP

**Owner/files:** employee_portal_ui owns Endpoint webapp/src and browser tests;
parent coordinates server shell and DLP grants, Helpdesk WorkTime link.

- [ ] Implement separate /employee login/session and employee-only navigation.
- [ ] Two SVG rings, selected arc details/text accessibility, schedule zoom,
  day/week/month, explanations/status/corrections and scoped team/HR screens.
- [ ] Separate DLP navigation and actual server grants on its API/policies.
- [ ] Typecheck/build/focused tests; browser checks on real routes and relevant
  viewport sizes, no fixture claims substituted for real integration.
- [ ] Independent UI/security review.

## E: Endpoint companion and agent release

**Owner:** parent after A/C contracts stabilize; isolated agent worker as useful.
**Files:** existing Windows/Linux user_sensor_runtime/tray and authenticated IPC,
versioned typed contract, agent tests and CODEMAP/release metadata.

- [ ] Test measured return >=1200 seconds and no unknown/reconnect/spam/user mix.
- [ ] Typed durable request/ack delivery to authenticated active OS session only.
- [ ] Native user-session notification and trusted portal deep link; no tokens.
- [ ] Verify IPC producer/consumer compatibility, offline/later and restart.
- [ ] Independent review, signed build, integrity and rollback tests; separate
  controlled update to Linux test machine and approved local domain PC.

## F: Integration, independent commits and pilot

- [ ] One AD pilot user enters Helpdesk and WorkTime with SSO; existing tickets,
  devices/messages/consents retained; employee cannot reach admin/DLP APIs.
- [ ] Manager department isolation, MFA and disabled-user/new-login rejection.
- [ ] Windows and ALT measured-return notification, explanation and day rings.
- [ ] Workspace verification, exact targeted checks, diff-check, independent
  combined review, atomic Conventional Commits per repository and SHA receipts.
- [ ] Deploy compatible independent versions using reviewed scripts; record
  installed source/artifact hashes, rollback and residual operational limits.

## Current evidence

The identity, WorkTime, portal, DLP separation and typed companion implementation
has received independent reviews. The unchecked stage gates above still require
installed end-to-end acceptance; fixture results alone do not close them.

- Helpdesk candidate `736f3ae81616fd9a6304457c2a512001f7d6337c`: all 18 canonical
  CI layers green, including 892 frontend unit tests, 168 browser cases and the
  disposable PostgreSQL layers. Staging `.118` runs this revision/schema151.
  Exact-revision cross-repository acceptance also passed (4 tests, pinned provider
  `8472d94f897c48041b718dafb84924b6cb73b86a`). Actual business API, ticket WSS
  subscription and isolated backup restore passed on earlier staged revisions;
  the current revision still needs its complete six-scenario deployment receipts
  and an owned mutating requester/support lifecycle. Do not relabel old receipts.
  Production Helpdesk remains on the preceding release pending its release gates.
- Endpoint server `.19` runs `62fb4c83efbea9e4acc19c779db034a80087d2f9`, schema0042.
  Its SSO and WorkTime flags remain disabled. The pre-upgrade backup was verified;
  the independent Helpdesk service/database were preserved.
- Windows ADMIN-2: signed Foundation/Core3.2.158, source
  `9423d9c27ea6b2d6c544c1bcdc1edb7cc9d15421`, installed through native Setup;
  installed verification reports READY. ALT `.210`: signed Foundation/UserSensor
  RPM3.2.158 installed with protected enrollment/configuration unchanged; selected
  Core remains3.2.156 pending a separately assigned singleton update.
- Dedicated Keycloak26.8.1: all three own-client audience/basic-scope corrections
  passed actual provider login, MFA, refresh and cross-client introspection checks.
  This proves provider behavior, not the Helpdesk BFF. Subsequent AD-disable
  acceptance exposed a blocking LDAP configuration defect: the enabled-only
  filter deleted the imported pilot identity and its OTP. The AD pilot was
  re-enabled; application SSO/WorkTime flags remain off. Reviewed source correction
  `1b4c6b4695b0b595ab74f8bf6ba9f24006ed1c71` is not yet applied to public Keycloak.
  A fresh private candidate restored from the original backup preserves the old
  subject and OTP; metadata checks passed. Private runtime qualification, session
  purge, complete drift review and separately reviewed database switch are pending.
  Never re-enrol OTP, accept the replacement subject or run another AD window
  before completing that recovery.
- Dedicated Keycloak backup and isolated restore on port5544 passed, including
  101 public tables, the pilot realm and three clients; the temporary DB was
  removed. No application database was used for that drill.
- Query-safe Nginx access logging is installed and checked for both applications
  on `.19` and `.118`; service identities were preserved. Helpdesk's query-safe
  application logger is present in staged736; production still runs the old
  release. Complete real BFF identity-link/revocation and installed notification
  acceptance before enabling application SSO/WorkTime. Three
  short-lived callback codes reached the existing Nginx access log during initial
  private-harness attempts; corrected interception prevents further harness leaks.
- ALT Core158 canary and the signed Linux kit are published; downloaded bytes and
  signatures were independently reconciled. No rollout or target was created.
  Windows Setup158 remains excluded from administrative default delivery pending
  campaign compatibility and exact-source automatic-compensation qualification.
- Endpoint staging remains on schema0039; its root free space is below the
  deployment threshold. Bounded backup preparation and full off-host restore
  tooling are under review. No new staging-capacity backup, LV resize or
  filesystem resize has run.
  A concrete storage expansion requires separate approval after verified backups.
- Windows `.120` still runs its original3.2.81 agent with production origin.
  Handoff Prepare/Apply, watchdog, claims and campaigns have not started; its live
  Windows deployment gate is `not_run`. Valid existing Endpoint staging and
  production update-admin credentials remain required through a private channel;
  do not reset accounts or bypass their current authorization.

Private redacted receipts are under `C:/Temp/helpdesk-sso-staging-20261027`,
`C:/Temp/endpoint-sso-browser-20261027`, `C:/Temp/endpoint-sso158-linux-20261027`
and `C:/endpoint-platform-wix-build/staged-3.2.158-9423d9c`. These are local evidence
locations, not portable release artifacts. See root PLANS.md for handoff.
