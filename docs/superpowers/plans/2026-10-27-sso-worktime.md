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

Checkpoint: **2026-10-27 05:30 UTC / 10:30 Asia/Yekaterinburg**. This supersedes
earlier progress notes. Product implementation has received independent reviews;
all unchecked A–F acceptance gates above remain open. No private recovery or
installed SSO/WorkTime/notification qualification is claimed complete.

- Helpdesk candidate `736f3ae81616fd9a6304457c2a512001f7d6337c`: all 18 canonical
  CI layers green, including 892 frontend unit tests, 168 browser cases and the
  disposable PostgreSQL layers. Staging `.118` runs this revision/schema151.
  Exact-revision cross-repository acceptance also passed (4 tests, pinned provider
  `8472d94f897c48041b718dafb84924b6cb73b86a`). Actual business API, ticket WSS
  subscription and isolated backup restore passed on earlier staged revisions;
  the current revision still needs its complete six-scenario deployment receipts
  and an owned mutating requester/support lifecycle. Do not relabel old receipts.
  Production Helpdesk remains `6cca48e5780d625cace590e46a30212ca9ecfb4d` pending
  all six current receipts, the owned lifecycle and the live Windows gate.
- Endpoint server `.19` runs `62fb4c83efbea9e4acc19c779db034a80087d2f9`, schema0042.
  Its SSO and WorkTime flags remain disabled. The pre-upgrade backup was verified;
  the independent Helpdesk service/database were preserved.
- Production Endpoint62's P1 source0666/directory0777 permission defect from the
  Windows-produced archive/runbook was repaired by Root through metadata-only
  changes at 04:41:02 UTC. Independent 04:42:29 reconciliation verified all 373 nodes
  (299 qualified+74 opaque cache) root-owned with directories0755/files0644,
  including 12 required cache ownership changes; all 373 intent/completion pairs
  complete and zero currently open writable descriptors. The 265 qualified archive
  files' bytes/mtime/inodes, 5208 venv nodes, selector and service PIDs314437/314438
  stayed unchanged; strict TLS health200. This proves current bytes/permissions,
  not absence of historical writes or exploitation, and does not qualify opaque
  cache provenance. Immutable archive `d6df0a87` remains retained. The five-file
  producer fix is committed as `f4120e9e999dd236dce7a47c53df98b84136edea` with
  14 real regression passes; the old archive remains immutable, with no repack or
  deployment claim. No repair repeat is needed. Production Helpdesk6cca's audited
  directories0555/files0444 remain unchanged. Safe receipt:
  `C:/Temp/endpoint-production-permissions-20261027/post-repair-independent-safe-receipt.json`,
  SHA256 `fc222b31abaea81ef1fba6052684af297cc107923ea50c21bfef8662ff9cd791`.
- Endpoint staging remains `3e3528fb`/schema0039. Its capacity gate now passes;
  upgrade preparation proceeds under existing OS authorization and release gates.
  Application-admin integration acceptance awaits a valid existing staging-admin
  session; the supplied credentials in staging tab3 were invalid, so app-admin
  acceptance remains unavailable. No account reset or bypass is authorized.
  Endpoint source HEAD is `f4120e9e999dd236dce7a47c53df98b84136edea`, following
  v8 namespace commit `44302b599330d6f695bd43360bf60f01a0f9fdd0` and executor SHA256
  `2e7206740550f6442355d07a41f6858a1b5f2c10252f0d2ca01305e3cc0896b4`, used in
  actual run7 below. Full private runtime qualification remains incomplete.
  Candidate62 completed one
  offline installation with 33 dependencies, exact pip freeze `7efc907b`, pip-check
  and actual service-user Settings validation (staging DB/origin/artifacts,
  OIDC=false/WorkTime=false). Alembic head0042 and offline migration SQL passed;
  no database migration, application restart or live selector switch occurred.
  Existing3e source/env/units/PIDs/schema/flags/packages stayed unchanged, with
  16536801280 bytes available afterward. Genuine app-admin, active-work and live
  switch gates remain HOLD. Safe receipt under the staging evidence root:
  `stage-release-plan/task1-install-final-result.json`; validation freeze SHA256
  `a9a2969e98c6e6ec81e7ef095e6ff856055f6cbcad8d0fd19e59dde7e54b3e0c`.
- Windows ADMIN-2: signed Foundation/Core3.2.158, source
  `9423d9c27ea6b2d6c544c1bcdc1edb7cc9d15421`, installed through native Setup;
  fresh read-only native verification reports READY. The retained exact source,
  signed Setup/MSI and protected credential/identity checks passed; local
  processes stayed unchanged for 98.508769s. Actual provider 62 read-only samples at
  `2026-10-27T02:04:36.595916+00:00` and
  `2026-10-27T02:05:46.894260+00:00` were 70.298344s apart: the same authenticated
  Gateway session's last-seen advanced by 90.027236s. This is bounded evidence,
  not 20-minute or notification acceptance. Earlier preflight WSS remains
  classified historical; source is verified locally, not attested by server
  rows, and NAT/zero compatibility instance does not attest local IP or a unique
  runtime. Receipt `release-plan/local158-fresh-readonly/readonly-reconciliation-final.json`
  under the 158 evidence root has SHA256
  `ac83bb20ea205259207c7bb27b8e3d873cdc292c3c206a8deeaefe33c49a42d5`;
  Endpoint doc commit `118ff` records its limits. ALT `.210`: signed Foundation/UserSensor
  RPM3.2.158 installed with protected enrollment/configuration unchanged; selected
  Core was 3.2.156 at the earlier native receipt. Subsequently the user supplied
  existing production application authentication and an authorized normal-UI
  singleton rollout was created (listing 80 versus 79). Provider read-only evidence
  at `2026-10-27T04:00:15.174346+00:00` records rollout
  `68ae441c-3578-42b4-99e0-bdcfca0ae95d` COMPLETED, its sole target
  `94186fc6-2569-4a06-81ef-78518332dbcc` for device596d APPLIED at
  `2026-10-27T03:58:58.436390+00:00`, version 158 and
  `post_restart_handshake_confirmed`, with a new Gateway session. Subsequent bounded
  native acceptance verifies selected Core158/source9423, all 98 runtime files
  against the published manifest and the mapped executable. Service/Core/UserSensor
  processes stayed stable for 70.133513s. The same authenticated Gateway remained
  open/unexpired across 280.288251s with last-seen advancing 270.008612s.
  Current protected configuration/credential/identity/CA bytes and metadata match
  across the two on-host samples ONLY; raw pre-OTA four-file baseline is unavailable,
  so exact historical cross-OTA continuity is not claimed. Final safe receipt:
  `ui-pilot158/acceptance-readonly-v1/alt158-singleton-final-safe-receipt.json`, SHA256
  `d6c3c7063fc644f1f1529e569d4b8a01ac80f4b9bd7c294d79c2d447d1b1f3b3`;
  Endpoint report commit `c9421b42a7fba64c3692bac72a946ba37ad20876` records the limits.
  Safe receipt under the 158 root: `ui-pilot158/acceptance-readonly-v1/provider-initial.json`.
  Earlier singleton-assigned UI screenshots retain their assignment-only scope.
  A later normal-UI observation at04:04 UTC explicitly shows COMPLETED/APPLIED1,
  errors0, working0, exact device596d and post-restart confirmation158. Its actual
  screenshot and accessibility text are `ui-pilot158/singleton-applied.png` and
  `singleton-applied-ax.txt`; they are separate from the later native/provider proof.
  Real Windows
  and ALT notifications, 20-minute observation, OS-user/SSO mapping and new automatic
  crash-rollback acceptance remain pending. Server rows alone do not attest source.
- Dedicated Keycloak26.8.1: all three own-client audience/basic-scope corrections
  passed actual provider login, MFA, refresh and cross-client introspection checks.
  This proves provider behavior, not the Helpdesk BFF. Subsequent AD-disable
  acceptance exposed a blocking LDAP configuration defect: the enabled-only
  filter deleted the imported pilot identity and its OTP. The AD pilot was
  re-enabled; application SSO/WorkTime flags remain off. Reviewed source correction
  `1b4c6b4695b0b595ab74f8bf6ba9f24006ed1c71` is not yet applied to public Keycloak.
  Private candidate OID 20856 restored from the original backup preserves the old
  subject and OTP. Actual run3/v4 ended in an unknown refusal; run4/v5 failed
  `PrivateRuntimeListenerNotLoopback`; run5/v6 failed
  `PrivateRuntimeUnexpectedClusterSocket`. Each subsequent read-only reconciliation
  historically verified all 101 candidate tables unchanged, original UUID/OTP intact, canonical
  service PIDs/database OIDs unchanged, no matching private processes and private
  ports free. Failed attempt journals and private directories remain retained.
  Later actual run6 refused `PrivateRpcReplyMissing` at
  `prove_browser_cookie_before_purge` after changing seven tables in old 20856;
  the original UUID/OTP remains exact, but the database is not a pristine restore
  and cannot be retried/reused. Its full 101-table inventory and failed journals
  are retained under `recovery-plan/run6-readonly-reconciliation`; canonical
  PIDs/OIDs remain unchanged, private processes absent and private ports free.
  Schema/sequences remain unchanged; browser positive/negative/revocation and
  final17 proofs are absent. No failure-cause attribution or semantic drift
  approval follows from the seven changed tables.
  Narayana V3's actual isolated library mechanism probe PASSED: default
  `SocketProcessId` added one loopback listener; `MBeanProcessId` added none and
  returned the native PID. It neither attributes prior sockets nor qualifies
  actual Keycloak runtime. Safe receipt: `recovery-plan/narayana-native-pid-probe/native-v3-final-safe-receipt.json`,
  SHA256 `b92554f29e20ac5bdb346315cc3a85051a1d0865dfa260896782345b08995154`.
  One fresh preparation passed actual execution and independent metadata review:
  `keycloak_recovery_20261027_2190f3d5`, OID 22159, all 101 original table multisets,
  schema/ACL/sequences and original UUID/OTP exact. Old failed20856 is preserved,
  as are all six earlier catalogue entries (seven entries after the new candidate).
  At that preparation checkpoint no candidate JVM, API write or public switch
  occurred. Preparation metadata was independently accepted; semantic review and
  private qualification remain HOLD, switch_ready=false. Safe preparation result
  under the browser evidence root:
  `recovery-plan/fresh-candidate-after-run6/root-one-fresh-prepare-result.json`.
  Subsequent actual run7 recorded positive original-browser initial and SSO
  callbacks, then failed with `RecoveryRefused` / `UnclassifiedRefusal` in
  `purge_restored_sessions_master_last` before `session-provenance-before.json`
  existed. The exact cause remains UNKNOWN and purge completion is not proved.
  Independent cleanup/reconciliation confirmed `OwnedCandidateStopConfirmed`,
  owned PIDs347374/347618 gone, all private ports free and public services
  unchanged. Old20856 forensic state and both original UUID/OTP identities remain
  exact. Candidate22159 now has eight changed tables: it is forensic evidence,
  NEVER a pristine retry candidate. Negative-browser, revocation, final17 and
  public-switch acceptance remain incomplete; no semantic drift approval follows.
  Safe receipts under `recovery-plan/run7-readonly-reconciliation`:
  `journal-result.json`, SHA256
  `cb05ca1ee0f5b0b01073a5eaa060dea67dbf3c025ef22706bff22a30b5de30de`, and
  `full-result.json`, SHA256
  `8f7dd35f2a38393b1930a93a50e0982f579853f46c5fd23854c1badc6bdbaf44`.
  Actual browser proxy run3 passed all 3 fake-owned literal127 loopback cases in
  44.818s under the original150s deadline; Node controller source SHA256
  `518fec7e27fe1eaf85cfdaaa7b54a079d1595e6462a6c574c33063fd3118aa65`.
  The owned job was empty before cleanup and cleanup was confirmed. First and
  second runs remain HOLD with1pass/2fail each. Safe result under the browser
  evidence root: `recovery-plan/browser-v2/owned-fixture-diagnostic-run3-result.json`,
  SHA256 `8a6b1fadaf2275f67c25ff0926da1a0eb3db94290feafbe76c136ab7251778b9`.
  This isolates browser transport behavior and proves no production TLS, AD/OTP
  or private Keycloak acceptance. Run7's partial original-browser success above
  does not qualify the complete private recovery flow; neither failed candidate
  may be retried or reused as pristine.
  No guard relaxation or public switch follows from these observations.
  Private runtime qualification, session purge, complete semantic drift review
  and a separately reviewed database switch remain pending.
  Never re-enrol OTP, accept the replacement subject or run another AD window
  before completing that recovery.
- Audit database OID 19553, owner `postgres`, exactly matches the saved ORIGINAL
  restore's full-row hash multisets across all 101 tables. Its 353 relation owners
  and database ACL account for the structural differences; other structural and
  sequence metadata match. It does not match saved current-at-prepare content:
  12 tables differ and their semantic drift remains UNREVIEWED. The exact
  comparator still refuses `DatabaseOwnerMismatch`; no owner relabelling or
  candidate reuse/promotion is allowed. Clone creation provenance is not inferred
  from content equality. Safe evidence: `recovery-plan/audit-clone-provenance-readonly/summary.json`
  under the browser evidence root.
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
  signatures were independently reconciled. At the immutable
  `2026-10-26T22:25:25.072566+00:00` snapshot, no 158 rollout or target existed;
  this is not a claim about later live state.
  Windows Setup158 remains excluded from administrative default delivery pending
  campaign compatibility and exact-source automatic-compensation qualification.
- The user explicitly approved the staging-only `.118` +10GiB capacity change.
  Earlier 00:18–00:21 UTC backup/restore evidence and its expired parent lease
  remain historical and were not reused. Fresh exclusive v6 capped backups ran
  `03:54:44.298009–03:54:51.387577 UTC`; two actual isolated PostgreSQL16.15 SCRAM
  restores completed `03:55:57.073841 UTC`, including wrong-password rejection:
  Helpdesk schema151/194 public tables and Endpoint schema0039/52 public tables,
  isolated PostgreSQL16.15 with SCRAM and a real wrong-password negative control.
  The owned cluster was stopped and removed. Independent reconciliation accepted
  all nine artifact hashes, sizes, private ACLs and source/dump provenance.
  Fresh approved passive Windows120 observation and a parent-held lease were
  independently verified. Root invoked the exact protected v6 guardian once:
  Apply and postconditions passed `2026-10-27T03:58:49.430235+00:00`.
  Independent read-only reconciliation at `04:00:15.996752 UTC` verified exact
  PV/VG/LV/ext4 UUIDs and absolute 15103 extents: LV/block/ext4 all 63346573312 bytes,
  previously 52609155072 bytes, available 16672423936 bytes. Application source,
  configuration, service PIDs and strict HTTPS health remained unchanged.
  The private consumed marker records exactly
  `lvextend --resizefs --extents 15103 /dev/ubuntu-vg/ubuntu-lv`; it is retained,
  with no second Apply/retry/cleanup. All old/new backups and journals remain
  preserved. Production `.19` storage was not queried or changed by reconciliation.
  Safe evidence: `C:/Temp/endpoint-sso-staging-20261027/capacity-refresh-v6/root-apply-result.json`
  and `independent-postapply-result.json`; the latter SHA256 is
  `9886e7d6bbda5b022c143d818b79e3274094b0ef58a5a161f99d525566f0eac0`.
- Windows `.120` still runs its original3.2.81 agent with production origin.
  Handoff Prepare/Apply, watchdog, claims and campaigns have not started; its live
  Windows deployment gate is `not_run`/HOLD; no claims, campaigns, real tickets or
  diagnostic mutations were performed. Valid existing Endpoint staging
  application-admin access remains unavailable after invalid credentials;
  existing production
  update-admin authentication is now available through the user's normal login.
  A valid staging app-admin session is needed for authenticated integration acceptance;
  do not reset accounts or bypass their current authorization.

Private redacted receipts are under `C:/Temp/helpdesk-sso-staging-20261027`,
`C:/Temp/endpoint-sso-browser-20261027`, `C:/Temp/endpoint-sso158-linux-20261027`
and `C:/endpoint-platform-wix-build/staged-3.2.158-9423d9c`. These are local evidence
locations, not portable release artifacts. See root PLANS.md for handoff.
