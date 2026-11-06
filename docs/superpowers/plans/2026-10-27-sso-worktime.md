# SSO and WorkTime implementation plan

## Current checkpoint: separate deployment reconciliation, 2026-11-03

CurrentDeploymentReconciled for staging1b6ce5a/schema43, independently verified.
The historical activation HOLD and all original receipts remain unchanged; exact
original failure cause is unrecoverable from the retained evidence. Confirmed
code-loss defect is fixed in the new reviewed restore/reconciliation primitive:
register actual imported Hold/Refused classes; output only allowed symbolic codes.
Tool commit e40fd3eca3ff321a2f6870535ac688bbc634e551 is local/no push;134 focused
tests passed. Short delta review covered only new guards/controller/receipts.
Original backup actually restored in an exclusive no-TCP PostgreSQL16 cluster:
71 tables/schema43, all constraints validated,24 protected table seals match the
original baseline except3 qualified shutdown events bounded by consumed/backup
markers. This backup bound is not a reconstruction of original startup windows.
Owned cluster/processes/socket removed; current full business seals, app processes,
controls/main PG preserved. Exact source/packages, served bytes/TLS, actual Linux
OIDC entry/stepup probes and anonymous employee API401 checks passed; blocking0.
No application release/restart/migration, production promotion, identity grant or
native session change. Original HOLD remains historical, not rewritten as PASS.
Receipts: C:/Temp/worktime-hold-reconcile-20261103. Native/real pending explanation
acceptance remains separate; user will prepare the selected domain session later.

## Historical checkpoint: live employee SSO and recorded corrections, 2026-11-02

Actual browser /employee SSO accepted with the existing Keycloak session and no
phone challenge. Fresh canonical identity comparison verifies the already-created
admin-2 profile; its separately authorized Helpdesk admin role is preserved and
does not create Endpoint administrative or personnel grants. Helpdesk staging is
now376b46c/PID316910; Endpoint1b6ce5a/API272154/worker272211, config hashes
unchanged. No identity/profile/role changes were needed in this turn.
Five real UI FSM transitions persisted; two TEST corrections are recorded with
approvals0/audit7. First automation datetime fill displayed a minute but submitted
the default hour; that failed input is retained. After keyboard-event/rerender
qualification, a new ENDED59-minute correction compensates the original test hour
without rewriting it. Exact server bounds verified; UI shows one test minute plus
FSM seconds, survives reload and has no browser warnings/errors. Foreign business
rows unchanged, except state-maintenance cursors are outside the digest; UNKNOWN
remains UNKNOWN. This does not accept native notification or the original HOLD.
Windows .120 is now in the domain; the selected domain session is absent. User
will prepare it later. No session switch, second collector or fabricated OS mapping.
Evidence: C:/Temp/worktime-admin2-profile-20261102. Short independent delta review
covers profile reuse, scoped writes and compensation; no application source edit.

## Historical checkpoint: ordinary employee authentication, 2026-10-30

Endpoint staging now runs1b6ce5a83dd17852ecca724c1b45378ac8536041/schema43,
API272154/worker272211. Ordinary employee entry no longer requests admin MFA;
explicit step-up/privileged sessions retain their assurance checks.97 focused
source tests and10 deployment guards passed; short delta review completed.
The original activation receipt remains HOLD with an unrecorded cause. Separate
readonly verification confirms the current release/runtime, strict TLS/assets,
unchanged controls and non-audit rows, preserved historical audit and only3
qualified close/3 connect appends. This is not a passed original activation gate;
no activation replay was performed. Backup SHA/TOC verified, not restore-tested.
Exact-object readonly AD qualification enabled business login for admin-2 while
preserving the pilot and application roles. The fresh browser has a normal
login/password form with no acr_values parameter; stale OTP enrollment was closed.
Cabinet acceptance remains pending: admin-2 has no staging employee profile or
confirmed binding. Awaiting profile selection; no personnel/role mutation made.
Receipts: C:/Temp/worktime-employee-login-level-20261030 and
C:/Temp/worktime-domain-login-20261030/v2. Production application deployment and
the separate native measured-return gate remain unchanged.

## Historical checkpoint: companion opens web entry

Endpoint staging now runs93525ba4740f62171a9d7161460b01e823f39b6b, schema43,
API270584/worker270639. The existing agent only notifies and opens an owned
employee context; web transitions/explanations/corrections remain immediate.
Login now retains a bounded day/request target in the one-use encrypted OIDC
flow. Source checks65 backend/agent,73 UI, build and2 fixture Chromium cases passed;
10 deployment guard tests and short delta reviews passed. Native deployment and
strictTLS/served-byte checks accepted. Fresh12.5MB PGDMP SHA/TOC qualified but not
restore-tested; auth/WorkTime rows preserved with only3 owned gateway-close audit
appends. HD/Nginx/config unchanged, no blocking jobs, no production deployment.
The actual anonymous browser reaches SSO with its synthetic navigation-probe
target preserved. Employee authentication/save and genuine native domain return
remain pending, independent of successful deployment. Local signed-Setup158 Core
still uses production origin; no second collector, fake OS binding or redirect.
Full receipts and exact hashes: C:/Temp/worktime-companion-web-entry-20261030/verification.md.

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

2026-10-30 follow-up: the two acknowledged inventory requests reached EXPIRED
through native15-minute timeout after their sessions closed, with no results.
Fresh readonly13:34UTC counters clear=true/inflight0/unknown0/inconsistent0;
no command was replayed or marked successful. Helpdesk staging navigation is now
deployed at19d53152f1b1da6330654d740d7c6993fe70a583: exact production/staging
config pairs and frontend whitelist,31 backend/31 UI/4 browser checks, short delta
reviews. HD267363/schema151, same39 packages, six durable identity/person/audit
table sets exact; only WORKTIME_PORTAL_URL changed. Endpoint10c/schema43 and
both runtime processes unchanged. Native correct-pair projection/strictTLS and
16 served asset hashes verified. Fresh backup SHA/TOC verified, not restore-tested.
The first installed-candidate check failed due to the diagnostic import path;
OLD was restored, then exact owned candidate activated after fixing that driver,
without repeated package install/migrations. Failed receipts preserved. No fresh
employee SSO login/native notification acceptance. Waiting for the prepared
domain pilot PC address/readiness; source stage plan and evidence:
docs/superpowers/plans/2026-10-30-worktime-staging-navigation.md,
C:/Temp/worktime-inventory-followup-20261030/activation-result.json.

2026-10-30 user explicitly removes WorkTime reviewer/confirmation. This supersedes
all historical second-approver requirements below; no second AD approver needed.
Explanations stay direct; corrections without historical decisions apply at once,
while archived rejected/approved history and immutable tabules remain intact.
New local commit10c2aa963fb98685f6146be13f82d06f392bcea4 contains18 task-only files
for backend/UI/0043 migration/tests/docs, no push. Isolated Linux52PASS incl3PG,
frontend69PASS/build/13browserPASS; bounded review fixed stale HR report/CSV and
closed. Clean canonical archive SHA5cba11ff2346c3e477004c869a2d8eb3ddc82e756f696e6b44f67a1b4dcdec94
with exact300-member inventory; static protected inputs installed on staging .118.
Staging .118 now serves10c2aa/schema43, qualified API263352/worker263407,
strictTLS/health200. Fresh dump SHA/TOC verified (not restore-tested). Existing
correction1 is recorded/approvalnull and applies900s without replay; approvals0,
events5/explanation1/WTaudit7 retained, UNKNOWN untouched. All3 served assets
match canonical archive; previous-release marker CAS ab9->62 completed after effect.
V3 early HOLD safely recovered OLD; V4 switch/migration completed but its final
premature audit-window closure held on a late genuine gateway connect. NEW startup
resume retained failed journals;120s quiet wait expired. Separate readonly receipt
verified full prior24-table rows/source/controls with only12 qualified owned
lifecycle appends. Two context.inventory.collect inflight are classified/linked;
global quiet gate remains false, no force/replay or blanket release PASS.
Final: C:/Temp/worktime-self-recorded-20261030/release-v4/post-effect.json;
runtime receipt880f69caa3c32b1f53d05f2ed903df0ee7fefd4b148e819d42d93de30b1be33b.
Independent delta reviews clear. No fresh employee SSO browser/native notification
acceptance claimed; domain session remains a separate pending gate.
No personnel grants/Keycloak/prod/fleet changes; domain session still needed for
native notifications, independently of the removed approval workflow.

2026-10-29 identity-operator source/test stage PASS; no live account/grant or
deployment. Endpoint helpera66fd2b445ab97c131604d969a245c4fab10e25db9ec426f5efdc91c2e82118e
provides exact identities:manage SSO-only creation plus audited owned retirement.
Root25 unit and31 existing SSO tests passed on Windows3.12; actual Linux3.12.3/
SQLAlchemy2.1.6/asyncpg0.32.0:28PASS incl3 disposable PostgreSQL cases, zero skips.
Real concurrency/rollback and whole employee/fallback preservation verified.
Independent delta reviews covered the code and isolated test runner; confirmed
audit-redaction/driver UUID compatibility defects fixed with regressions. Failed
first PG result preserved; successful second raw result
127f789e6ef85e505ec798c234fe3947716493bf12967afdc0c79f983606dccf and Root719-file
closure08210169086a7cb2fa76889ad7945c2fe071e9087ec66a717f983a51d7edf286.
Owned PG stopped, process/listener absence verified; app DB/config/services intact.
No auto-expiry/fleet/prod/commit/push claim. Next: reviewed operations deployment
and explicit actor qualification; approver/domain pilot PC readiness pending.
Helpdesk staging navigation remains disabled: current fixed portal allowlist
accepts production only, so a separate safe staging boundary is still required.

Current business-resume-v1 actual PASS supersedes current-state counts in the
historical checkpoints below. Freeze60439793ad483c6493dc088f4a8b511378e630754d09d392b3359d2a0abce984;
resultc0618c1424fd9a5855c5c71159ea68ac9adf034b4e44df0b507ecafc211a9f2c;
Root verification0b914fe3ddc54a0c96f6352c073d985aed047875bdb713cb5c7816609af29e0e;
accepted7caf1c4850afd5f78e56cecac75ee6078ce6e6c4a9349de130df7858b8d4f3093.
One new pending correction only, prior six whole records unchanged; fresh real
password1/OTP1/callback303, native session/HMAC, admin401/DLP403/HR403/CSRF403,
desktop/mobile/no-overflow and actual UI logout204+old-cookie401/native revoke
passed. Root inspected both genuine screenshots; errors/blocked/5xx0. Original
pilot/OTP, HD20/admin/scopes and old auth/audit seals passed. Current identity1/
employee4/upstream4(all revoked)/flows6, WTstate1 ENDED/events5/explanation1/
correction1 pending/audit7, all other WT tables0. Work62s/offpc1s/break1s and
UNKNOWN86400 remain exact. Forty-five focused checks and bounded native/UI/
transport reviews passed. Prior HOLD stays immutable, no historical replay.
No approved correction/roles/notification/RP/canonical-six claim. Separate AD
approver and domain PC readiness are pending. Next source/test-only work is the
controlled SSO-only identity operator CLI described by Endpoint's separate
2026-10-29-identity-operator plan: exact identities:manage, unusable password,
fresh authority, audited owned retirement and unchanged fallback; no live grant.

Latest business attempt1: actual HOLD after canonical prefix6 (5 FSM events +
explanation), freeze0ebbdbee42413018350cf2b754b0f1d1c24da5d5cbb25c3a76f04393b1ccbee2,
resultd0e21321267cc21aea78ef6ac591d7ae4e5c75a994f14362910568714d1c8d5c,
accepted6sha9e502267e8e36a2d5dc392bd37cffea017ec1721aa427df062ea1590af59f0db.
Actual work62s/offpc1s/break1s and idempotent replay200/conflict409 verified;
explanation preserves history/totals/UNKNOWN. Native partial-after and API logout
passed, original pilot/OTP/admin/HD20/old-row guards exact; full flag remainsfalse.
No correction request was sent. Failure is harness exact-label select_option;
canonical synthetic Chromium reproduction gives old selector0, scoped combobox1
with correct defaultWORKING. Preserve immutable HOLD and six records; no reset,
rerun or false all-green reconciliation. Current auth1/3/3/5 all sessions revoked,
owned SSO created/revoked3 each; WTstateENDED1/events5/explanation1/audit6, others0.
Prepare bounded business-resume-v1 for only correction7 after qualified partial
and fresh session. Elapsed real-minute evidence does not claim a ticking UI timer.

2026-10-29 00:04 UTC: genuine employee readonly acceptance PASS. Protected
employee-worktime-browser-v1 sourcefreeze8af92df9f544598955b97f9e4f25f9d818e8737dc09eec4d0fae2873abcba78f;
resultf8a7d9f6a53e5fc3ef27515d8fdeca1818de38583afd6258888c4e601a865566;
Root evidence+visual verification6e17d173cf3fdfcfda9d861927745a31eafe6e3fa61d481c9576175e4a9ad53d.
Actual password1/OTP1/callback303, employee BFF, admin401/DLP403/HR403/CSRF403,
day/week/month/history, pointer+keyboard ring, desktop/mobile no-overflow, actual
UI DELETE204 awaited +old-cookie401/native revocations all passed. Browser/page/
5xx/blocked0. Root inspected two genuine non-auth screenshots. All14 WT tables
remain0; virtual categories7 and UNKNOWN86400 do not create personnel work.
Old auth/audit/HD20/admin/pilot/OTP preserved. Current retired auth: identity1,
employee2/upstream2 revoked, flows4, created/revoked audits2 each; no roles/admin
mapping. Source-only P1 CA encoding/P2 static HTTPS fence fixed before any native
attempt; candidate1 retained,39 focused checks and independent delta review pass.
Do not rewrite previous V3 HOLD. Next owned business UI stage is source-only
preparation (5 transitions/explanation/pending correction/idempotency). No manager,
approval, notification, RP logout or canonical-six acceptance is claimed. Original
domain pilot PC readiness remains pending. WT gate native_after remains current;
its old strict accounts-before must not be reused after new owned auth rows.

Latest native state: WorkTime staging enable1 preflight/apply/verify PASS:
HD OIDC=true/EP SSO=true/EP WorkTime=true, one WT-only flag change, one restart
call/two EP units. Whole auth/audit/admin/password/scopes, original HD20/binding,
prepared10/source/schema0042 and all14 empty WT tables were preserved. New
protected control /root/endpoint-staging-worktime-enable-v1 freeze
9ce960cd91fc762e45597f4d4df570b9f624a869dbddb7e5806172bef03682b3,
applyecb0d2029f66b87e32e759c01f38d555bf0146ca11e1f33ca5b7f6016da87dc3,
verify97c999db96b5e3336b7bd031636493a21bd291a1f1e1221703156808d76c4695.
Its result.native_after is the CURRENT native/PID/env authority; earlier EP
enable1 after-state is historical. Owned stored-auth+WT baseline is post-BFF
checkpoint17ffe662d79d188729f92f5749e92af61f7b6b0bc1a24259b6950bc4511d9799.
Twenty-one focused checks and independent delta review passed. V3 HOLD remains
unchanged; feature/negative/notification/RP acceptance stays pending. Next source
preparation is employee-worktime-browser-v1 for genuine auth + readonly UI,
correct admin/DLP/invalid-CSRF negatives and logout. Category defaults are virtual
DTOs (SELECT-only), so all14 WT tables must remain0 during that readonly pass.
Dedicated pilot domain-session IP/readiness is still pending.

Latest checkpoint, 2026-10-29 local date: Endpoint employee v3 performed genuine
password1/OTP1 OIDC callback303; actual principal, stored identity/session/upstream,
same-cookie local logout/401, native/source/HD20/admin-role and original pilot/OTP
guards passed. Overall immutable receipt remains HOLD/EmployeeReachedAdmin,
SHA2fe4dc395a5aa37fb3b8927b9875a2ee5e5ec4e244fea67dedd8fee36d374c5a:
harness GET/api/admin/session is unsupported405; canonical protected GET is
/api/admin/console/session (separate unauthenticated strict-TLS401 confirmed).
The broad /admin egress deny covers shared /admin/assets CSS; blocked1/console1
were recorded without per-request attribution. No full browser/negative-gate
PASS is claimed. Carry correct admin/DLP/CSRF/UI checks to the next WorkTime UI
pass, preserving this HOLD and avoiding a login merely to relabel it.
Exact old2 expired/unconsumed flows were independently qualified and retained;
root-private EXCL checkpoint da5d6504375ff78a43eeac7b8f341cf81fbf5f61d688d5b38f08e863b8946666
was captured before v3. Reviewed pin-only probe84454 and aggregate freezec326113b
passed32 focused checks and independent delta/closure review. Current owned auth
rows are identity1, revoked employee/upstream1 each, flows3 with only new1 consumed;
admin link/grants/admin OIDC remain0. A new bounded readonly post-BFF whole-record
checkpoint is source-only preparation for WorkTime flag activation; the flag is
still false. Domain-session IP/readiness for live notifications is pending.

Current staging checkpoint, 2026-10-28 22:43 UTC: EP-only SSO enable1 native
preflight/apply/independent verify passed: one EP flag flip, one restart call/two
EP services; HD unit/env and WorkTimefalse untouched. Whole private admin/password/
scope/role snapshot, empty EP identity/auth/grant tables, source/schema0042/loaded
config/strict health/material10 and HD full20+binding remained exact. Root17 focused
tests/delta review passed; timer budget was fixed before freeze/native use.
Sourcef94b1868e8b0cfaffcaa7d6171c6a70845eb0cd400172409b3c7b5da2f73bbf9 /
freeze923a35df82dfbd5933ab0fffa36d5cf50e8eee1989999673c8b8f5e1b87cfeae;
protected applyb9dcd2d43f0cf921ab876583750210427a6bc786a524168c5fc7f93be5905954 /
verifydb69ffa367685ed258dfb72d7cb7cdd49c347b3e98f55e641caa48e09bfa4012.
HD+EP SSO true, WorkTimefalse; EP employee BFF acceptance is next. No personnel
grants/admin links/password migrations or broader gate claims.62 lacks a canonical
scoped mapping-operator provisioner; preserve the sole updates:write admin.
User will prepare a separate genuine pilot domain session; address/readiness
pending. No domain join/forced logout/fleet/prod promotion/commits/push.
Employee BFF source review caught/fixed CSRF64 versus canonical43 before use.
Actual v2 stopped before password/OTP on missing state capture; metadata-only
auth-start confirmed the flow cookie correct and redirect route unobserved.
No cookie/Nginx change: keep failed receipt/2 unconsumed rows immutable. New v3
CDP interception covers redirects, 307 replay blocking passed real Chromium
loopback +11 unit checks and delta review. Explicit expired-owned-flow checkpoint
and adapted probe are source preparation; no employee authentication is claimed.

Previous staging checkpoint, 2026-10-28 22:19 UTC: real owned HD staging OIDC
browser login passed callback302, exactly one password/OTP, native persisted
BFF/UiToken and /me user/oidc checks; T64/public/private DOM passed with no errors.
UIlogout303 and exact actor Observer revoked=true are independently proven;
cleanup revoked=false, same-cookie final native check passed, active0 with one
retained revoked OIDC row. Browser5 original HOLD/OldCookieStillValid is immutable
(944ad843a4c653edc81b88c7ba6f844ec5be3090b1cb6cbd4f303d920da39ede).
Separate reviewed readonly reconciliation passed without another login or DB
write; this supports a response-timing race but does not establish precise early
GET ordering. strict_browser_post_response_wait_verified=false and RPlogout=false.
Browser25 focused checks/review and reconcile9 focused checks/review passed.
Reconciler86513d477d6e9c31b28a9ebb5945df995791afba5d0f465f34f84fce1625de67;
HTTP proofc4c3a2ef13fa458a224fc43babba0c925efb4d163e9a04abaa1ec1881c17cf8e /
Observer proof232f6251758bea13dbb6f0e01523817275d526faf8fd15479e830d6706da4817.
All failed/source-only attempts are preserved: network-repeat budget P2, local
Get-Acl autoload refusal before credential reads, UPN user_not_found qualified by
fresh fixed-same-user SAM proof, and pre-send OTP selectedCredentialId refusal.
No account/OTP/provider/binding reset or replay. Source/template/mapping fixes
were reviewed before each fresh bounded stage. Native/full20/pilot/OTP unchanged.
HD SSO true; EP SSO/WorkTime false; password/roles unchanged. Password migration
still needs a fresh active genuine OIDC session. Next scoped EP identities/grants,
WorkTime/consent/device/notifications; six broad gates remain open, no commits/push.
Next EP employee authentication does not require identities:manage; prepare only
its SSO flag activation, WorkTime off. No EP runtime mutation has run. Read-only
checks found .120 outside the domain; local PC domain-joined but active WTS
identity unverified. User input on a genuine pilot domain session for future
notification testing is pending; no forced logout/domain join/OS identity mapping.

Previous staging checkpoint, 2026-10-28 21:55 UTC: Helpdesk-only activation1
preflight/apply/independent verify passed. One OIDC_ENABLED false-to-true flip,
one HD restart; Endpoint SSO/WorkTime, EP env and both processes unchanged.
Loaded config/source/selectors/unit assets/strict health and whole binding+owned
records remain exact; original19+sealed20 chain independently verified. Fourteen
focused checks and delta review passed. Protected applyf70b6b5995164392f37ef557ea53d5d511cea908f6894fafffaf0e6d8a254f8e /
verify6bcaf84970c855b9369f979ca479d39496a8e2de9f38b4c4bed0916ba2f725ad.
Owned real-UI OIDC browser/session/T64/logout helper is source-only (20 focused
tests pass); source review and native acceptance remain pending. No real BFF,
password migration, Endpoint grants, RP logout or broader gate claim. No commits/push.

Previous staging checkpoint, 2026-10-28 21:44 UTC: disabled installer2 native
preflight/install/independent verify passed (26 focused tests and delta review),
with two active env swaps, three restarts, exact loaded env/source/native/health,
ten prepared file identities and original19+sealed20 continuity preserved.
Protected install0181b09c7a79a512637547b96fb06e45659bd4319aaf52f049398f64b4cd7f74 /
verify64d522d510922a5aa4e40970d1d6c512b7c7b54e83f1395fd2a2ff5aebdc6eb0.
Owned binding3 preflight/apply/independent verify passed with exactly two canonical
API mutations, exact returned IDs/owned records/service resolution and logout.
Protected apply6122f99c9fe7eec474d377e44ad53ec66584bb5d70651ea4fdb30463e020b465 /
verifyfa76cb7c498660ba08d8cdfcc764b2dbbe7bc31b2b0ee86e4e1bebd3a55ef70c.
Binding26 checks and delta review passed. Preserved v2 preflight stopped before
.118 transport on clock age -0.167s; v3 uses same-response monotonic duration
locally while preserving original receiver age0..120, TLS and OIDC time checks.
Pilot/OTP, requester/person/password/roles and T64/full20 unchanged. SSO/WorkTime
still disabled; real OIDC authentication unclaimed. Next: Helpdesk-only staging
activation and BFF acceptance. All broader gates stay open; no commits/push.

Previous staging checkpoint, 2026-10-28 20:47 UTC: app-inputs2 native preflight,
prepare and verify passed. Ten prepared files: two disabled env candidates,
two exact backups, four independent Endpoint secrets and two CA copies. Both
actual service UIDs validated canonical config/Fernet/strict TLS; active envs
and PIDs unchanged, flags off. Sourceadb54b3c5f7d470a68c483f9d5721a60f7f12b1f167e997d609d449bae7ca896 /
freezeb2a55fb4638eb66fac5f3d9c422657d92918addb1504b3026b8d493d4b33081d;
prepare7411fcd50a7c1fe21070b4494c1e394a4f040cb94e55bd3adf4546f81a6b95cc /
verifyde1409e122089c8aa7768a3ce885243bc9409a3f681740f7404aa85c3e7d0852.
V1 system-Python asyncpg refusal created no paths, independently reconciled;
v2 DB source check uses the existing HD venv. Eighteen checks/delta review passed,
with both metadata-adoption and foreign-control receipt fixes before native use.
Disabled installer source/continuity adapter have21 focused checks passing but
are unexecuted and under independent review. Explicit original19+sealed20 history
remains mandatory. Real identity/OIDC/WorkTime/notification and six gates open.

Previous staging checkpoint, 2026-10-28 20:01 UTC: enable2 actual preflight,
enable and independent verify passed 43/94/43 requests. Exactly three owned
staging clients enabled; production clients/original pilot+OTP/native/material
unchanged. Reviewed source b1f4e79d77618c48fdd0c56c8eeb25b30565491cae209b149743b5b0cd5014c9,
freeze2c6e30e6bb8cf66394e0b68de84b1be86d01b45391619a3381800f851a11dfc6;
Root12 focused checks and eight-file closure passed. Unexecuted v1 review found
cached validation after backup; v2 backs up before canonical fresh reads, with
three drift regressions proving zero PUT. Actual protected result967c8b5ff3776e72179b79ad399470fcbe2488d0712b3f5977871f72c3124ff9 /
verify75d6812f7033068be13f84bcf23fed2ee5792fdf709ad3211b37bd95c8b2a6d9.
Backup20:01 durable/checked, restore untested. .118 active env/PIDs unchanged;
SSO/WorkTime off. Disabled app candidates/private delivery are source work;
explicit identity binding/live BFF and broader gates remain open. No commits/push.

Additional source-only logout preparation: Endpoint staging generator registers
exact HD /app/login separately from its callback; RED then25PASS and delta review.
This has not updated an installed client or enabled RP logout. Current anonymous
strict-TLS provider probe returned400/invalid redirect. Keep logout env settings
blank until a separate reviewed client update/probe; frozen actual libraries stay
unchanged. Application-local logout is the current scoped behavior.

Previous staging checkpoint, 2026-10-28 19:45 UTC: browser6 passed both real UI
logins/DOM/privacy, separate internal tab, requester expected denial and native
support WSS subscribe, zero errors, logout and exact20-history/native guard.
Keycloak three disabled staging clients prepared and independently verified;
91/96 requests, production clients/pilot/OTP/native unchanged, independent root
secret store .19 only. Durable backup checked; restore untested. V2 readonly
ProcessLookup hold preserved and reconciled before fresh v3, no IO patch.
Enable source work is next. .118 OIDC/config inputs and identity/session tables
are empty, DNS/TLS3origins passed; actual Endpoint switch ENDPOINT_SSO_ENABLED.
No production app flags or real-person mappings changed; broad gates remain open.

Previous staging checkpoint, 2026-10-28 19:33 UTC: T64 lifecycle continuation/native
and independent readback passed: closed, three messages once, original19 events,
stable identities, UI sessions0 and public session revoked. Browser requester
DOM/privacy/TLS and expected subscription denial passed; requester polls, support
WSS remains to sign off. Support internal note needs its normal separate tab.
One authorized message_read extended history19→20. Exact-prefix/typed-event proof
is separately sealed at /root/helpdesk-owned-browser-history-v1.json, SHA
1e3cd438fe8e4ce4676bf410b9b7935df6f5b3b0283eb4685f7d49404eda286d;
consume it explicitly in browser and later SSO continuity, preserving original
raw result b7571fed6c55fa7c2295151ba0dbcc3b4042cd0a4c5f20b291af85c3f98efc4e.
Endpoint staging owned admin login/logout passed via approved protected channel,
no device action. Keycloak staging readonly plan40 passed actual levels1/2 and
pilot/OTP/native guards; three clients/secrets still absent. Create carrier v2 is
pending a finally production-postcheck fix before native use. All broad gates open.

Previous staging checkpoint, 2026-10-28 18:55 UTC: fixture-v4 actual nine additive
API mutations passed, with independent read-only role/person/org/identity/audit
and native-resource verification. Test secrets remain protected on host. Review
confirmed that nonempty local-consent was an artificial helper prerequisite;
v2 retains exact continuity and declares empty coverage/live-consent pending and
canonical-six=false. Actual one-ticket T-000064 passed create idempotence/conflict,
foreign/role denial and in-progress/premature-close checks, then held because the
helper misread nested support message event_id. Read-only reconciliation found
exactly one requester/support message each and no active fixture UI sessions.
A separate zero-new-ticket continuation is pending; original journal/fence stay.
The old public-token check also used a device-only messages API; the corrected
continuation will use canonical ticket GET. No application runtime code changed.
Windows .120 remained on its recovered PID with fresh status, no handoff/update.

Previous staging checkpoint, 2026-10-28 18:40 UTC: owner console acceptance passed;
temporary browser PIDs/ports independently absent after launcher Hold (no graceful
cleanup PASS). Windows .120 exact legacy runtime/safe-status checks passed; one
canonical start recovered fresh strict production WSS with unchanged authority,
selector and ACL. It remains 3.2.81, running, no staging handoff/update acceptance;
the earlier failure's cause is unproved. On .118, no actor/claim/material writes.
Immutable CI comparison qualified exactly 121 raw native web files for staging
fixtures only (119 exact, index/SVG CR-before-LF only, platform ordering difference).
CI receipts are preserved and production promotion is not approved. A subsequent
preflight TLS failure was reproduced without credentials: duplicate handlers use
default trust before the appended approved CA; original GET fails verification19,
one strict approved-CA handler succeeds. Minimal fixture-v4 source correction is
pending focused tests and short delta review; no global trust/runtime changes.
Next: owned actors, genuine consent/device flow, lifecycle, identity and BFF gates.

Previous owner checkpoint, 2026-10-28 17:32 UTC: the human confirmed the privileged
console opened; native read-only correlation matched one fresh selected-owner
console session after the launcher start. Exact roles, immutable identity,
password-only policy, zero stored credentials and business/native/TLS guards
passed. No session IDs or credentials were recorded. Direct UI automation could
not bind the separate private Chromium window; no such PASS is claimed. Bootstrap
remains needed by fixed-auth staging-client/pilot helpers, so retirement follows
their completion or reviewed auth replacement. Next: owned staging WSS and
synthetic requester/support lifecycle, then identity linking and BFF acceptance.

Previous owner checkpoint, 2026-10-28 17:28 UTC: the exact master-admin role was
assigned to the selected owner and passed independent native readback, with
password-only policy, immutable identity, groups/user, business/native/TLS guards
unchanged. Grant v2 passed 26 focused tests and delta review; the source-only v1
request-budget defect was fixed before deployment. A verified durable backup is
retained, restore untested. The reviewed isolated browser v2 is open for human
domain-password acceptance without MFA. User response is pending; no live
privileged console acceptance or bootstrap retirement is claimed. No replay.

Previous owner checkpoint, 2026-10-28 17:14 UTC: password-only policy v3 applied
and independently verified on the canonical service. The selected owner's TOTP
action and the added console ACR/browser requirement are removed, with zero
stored credentials and no administrative grant. Identity, domain password,
PKCE, audit, business policy and private entry remain verified. The prior v2
HTTP400 attempt is preserved; reconciliation proved no configuration changes.
Grant and human password console acceptance remain pending; bootstrap is retained.

Current user policy decision, 2026-10-28 16:53 UTC: the user explicitly rejected
MFA at the selected owner Keycloak console setup screen. Remove only the added
selected-user TOTP action and console MFA requirement; retain domain password
authentication, PKCE, audit, immutable identity, private console entry and business
client policies. Older mandatory-owner-MFA notes are superseded for this scope.
The human browser/tunnel were stopped and owned processes/ports verified absent.
Finish3 preparation and Nginx loopback deploy had passed independent verification;
no owner role or bootstrap retirement occurred. Password-only policy/grant/login
acceptance are the remaining owner stages. Do not reset or delete stored OTP.

Current owner stage, 2026-10-28 16:30 UTC: finish v2 imported the exact selected
owner without admin roles after durable backup; it held before TOTP queue because
the API returns Keycloak's virtual LDAP password descriptor. Readonly API/SQL
reconciliation verifies no required actions and zero stored credentials. Preserve
the imported subject and all consumed evidence; never replay/reimport/reset.
A new queue-only continuation binds both checkpoints and preserves all existing
configuration. MFA enrollment, loopback Nginx entry and bootstrap retirement
remain pending. Application SSO/WorkTime flags remain off.

Previous owner stage, 2026-10-28 16:09 UTC: checked cleanup v2/v3 restored the
master reference with business/native guards after durable backups. Prepare v4
applied the console MFA binding/GUID mapper, then held before provider enable or
owner import: Keycloak returns only one extra deprecated consentRequired=false.
Readonly reconciliation confirms exact other mapper fields/config. A qualified
four-hash checkpoint binds the whole current public console and consumed v4
receipts/context for a separate finish operation. V4 HOLD is immutable; no replay
or cleanup of the bound flow. Provider disabled; no owner grant/enrollment or
bootstrap retirement. Nginx unchanged. Windows private static launcher preparation
passed, including existing Chromium156, with no SSH/proxy/browser launched.

Previous owner stage, 2026-10-28 15:52 UTC: user-selected owner; native master
audit enabled with representations disabled and independently verified after a
durable backup. Owner prepare v2 is consumed/partial HOLD after disabled LDAP
provider creation because generated full-name/Kerberos mappers were unexpected.
Readonly reconciliation confirms disabled/eight children/no dedicated flow.
No import/admin grant/MFA enrollment/bootstrap retirement is claimed. Do not
replay v2. Review exact failed-resource cleanup, fresh minimal-mapper preparation,
loopback-only console deployment and human MFA as separate remaining stages.
Private native Nginx boundary proof passed, process stopped; live site unchanged.
Redacted receipts remain under the existing recovery-plan/semantic-drift-review
directory. Short delta reviews and focused checks replace repeated broad review.

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

Draft checkpoint: **2026-10-28 14:34 UTC / 19:34 Asia/Yekaterinburg**. This supersedes
earlier progress notes. Product implementation has received independent reviews;
all unchecked A–F acceptance gates above remain open. Technical private run8
reached `QualifiedUnreviewedDriftHold`; its exact final candidate field semantics
have now been approved for promotion preparation through a separate bounded Root
review. Public promotion and installed end-to-end SSO/WorkTime/notification
acceptance remain incomplete.

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
- Endpoint staging `.118` now runs qualified `62fb4c83efbea9e4acc19c779db034a80087d2f9`
  /`0042_worktime_companion` after Root's separately reviewed preflight, quiesce/
  fresh backup and explicit switch. Native runtime/schema and strict HTTPS checks
  passed. The user then explicitly authorized additive creation of the missing
  staging admin through canonical Argon2/AdminUser/audit; existing_accounts_modified=false.
  Genuine UI login and read-only dashboard/devices/updates/audit passed,errors0.
  Current tab3 is authenticated staging `/admin`; tab1 was closed by the user and
  production tab2 was untouched. Earlier invalid credentials remain historical
  without retry/reset/bypass. Owned WSS and mutating integration remain open;
  details follow the preserved preparation notes.
  Endpoint source HEAD is `bfd24febba974ce387227452950c88a9b1916582`, an eight-file
  v11 isolation update with 325 Root passes/one existing POSIX skip and independent
  source review. Four new uncommitted files now add pure `promotion_guards.py`,
  its37 tests and matching CODEMAP/recovery documentation. RED missing-helper
  failure and37 GREEN passed; peer review had no findings. Actual default CLI
  returned PureGuardsOnly, runtime_actions/apply_supported/switch_ready=false.
  The module validates fixed physical-cluster and exact idle catalogue states;
  native collector/executor binding remains separate. Four additional uncommitted
  files now contain the public-promotion entry/helpers and focused tests.
  V1 was rejected before installation: dynamic ExecStart PID/timestamp properties
  would prevent checked recovery after a normal stop. Later pre-consume refusals
  identified exact installer-relative link, omitted empty EnvironmentFiles with
  typed D-Bus proof, kernel /var/run socket alias and missing psql line framing.
  V5 passed native observe/preflight,63 focused tests and independent delta review.
  ONE Apply consumed and stopped KC, then held before backup/rename: wrapper143
  was reported failed/PID0. Reviewed original-only restart first refused the plain
  numeric ExecStart143 format before start; a second checked attempt started the
  original, then early acceptance held ServiceDatabaseOidInvalid. That startup
  cause remains UNKNOWN. Separate native read-only reconciliation passed three
  stable bindings to original16385, strict TLS, current full inventory/purpose
  allowance, unchanged candidate26068 and other five services/eight controls/assets.
  Subsequently V6 passed93 focused tests/independent delta review and fresh native
  observe/preflight. ONE Apply completed Promoted; V5 was not replayed. Independent
  native read-only postcheck and peer receipt reconciliation confirm service/OID26068,
  exact final inventory with only purpose housekeeping, strict approved-CA TLS,
  unchanged other five units/eight controls/assets and retained idle original16385
  with connections disabled. Fresh455755-byte backup has checksum/TOC/fsync with
  restore_tested=false; its SHA256 is dc51749e43029fb84590e5184fd9a0e12c795810cd290d60064cdb252abaf98c.
  Safe receipts: semantic-drift-review/root-public-promotion-v6-apply-result.json
  and root-public-promotion-v6-independent-postcheck.json; postcheck SHA256
  608ae4570b6a658e2f4f4fc463de9b1e4e292cc5d00f38266a5c0bd58bf54004.
  Owner/MFA, public synthetic AD and application checks remain open; promotion
  changed no owner grant or application flag.
  Three-source semantic v2 passed303 full-table comparisons and all22 bounded
  predicates. Root approved only the exact final candidate semantics; older raw
  qualification receipts remain unchanged. Dummy-cluster rehearsal v3 passed all
  six cases, followed by131 independent postcheck records; earlier v1/v2 failures
  are preserved. Read-only public preparation v2 passed explicit approved-CA TLS,
  exact current metadata/100 tables and the two-row server_config purpose guard.
  These observations do not replace fresh quiesced switch checks.
  The user selected the domain account as permanent SSO owner with mandatory MFA.
  Native strict LDAPS matched the immutable selected identity and enabled state
  with current Windows credentials; private directory values remain outside docs.
  No owner grant, MFA enrollment or bootstrap retirement occurred; public promotion
  is now verified as recorded above.
  Owner observer v2 source passed14 Root tests and3 transport privacy regressions,
  then independent review. ONE native observation passed22 requests: no selected
  owner conflict, one local master user, zero storage providers, enabled TOTP
  action, zero required profile attributes, zero enabled/unknown policies and
  console fullScopeAllowed=true. Fresh native LDAPS and actual service/OID26068,
  approved-CA TLS, six units/eight controls/assets were verified before/after.
  No explicit configuration/provider/user/role write is supported; bootstrap token
  authentication may change master auth sessions/events. The saved snapshot uses
  metadata allowlists; no fresh business invariant or post-auth full-final equality
  is claimed. Receipt reconciliation passed; owner preparation remains next.
  Safe receipts in semantic-drift-review: root-owner-observer-v2-observe-result.json
  and root-owner-observer-v2-sanitized-snapshot.json (SHA256
  a5caa38e22f27f693f8de1063913cbee7cefa1dbb7e35630244ea3100708c0aa).
  Prior SID contract fix
  `ef6d298ffcf6f42841d4d0533aea015e7004a365` remains committed.
  Earlier v8 source `2e720674` was used in run7 below; subsequent v10 narrow master
  proof is scoped separately. V11 source is committed/reviewed; its later run8
  technical qualification succeeded with an unreviewed-drift hold, as recorded below.
  Historical pre-Task2 preparation/readiness checkpoints (their HOLDs and old tab
  assignments are superseded for current runtime state by Task2 below):
  Candidate62 completed one offline installation with 33 dependencies, exact pip freeze `7efc907b`, pip-check
  and actual service-user Settings validation (staging DB/origin/artifacts,
  OIDC=false/WorkTime=false). Alembic head0042 and offline migration SQL passed;
  no database migration, application restart or live selector switch occurred.
  Existing3e source/env/units/PIDs/schema/flags/packages stayed unchanged, with
  16536801280 bytes available afterward. Genuine app-admin, active-work and live
  switch gates remain HOLD. Safe receipt under the staging evidence root:
  `stage-release-plan/task1-install-final-result.json`; validation freeze SHA256
  `a9a2969e98c6e6ec81e7ef095e6ff856055f6cbcad8d0fd19e59dde7e54b3e0c`.
  Root clarified that requiring app-admin before the 39→42 code/schema switch was this
  task's plan constraint, not a canonical runbook requirement. A proposed amendment
  for review and new `task2-ops-counts-v1` operator helper are source-only: they
  would collect COUNT-only repeatable-read read-only readiness from `.118`'s own
  DB before/after quiesce. No application readiness counts, deployment or amendment has executed;
  actual known/zero readiness states and review remain prerequisites to opening
  the switch gate. HTTP authentication, legacy UI login, SSO and integration
  acceptance still need genuine app-admin credentials and remain NOT RUN.
  Production tab1 is authenticated; staging tab4 is blank, with no reset/bypass.
  The helper passed72 Root source tests. A native PostgreSQL16 publicVALUES fixture
  passed OID-cast/COUNT behavior with no application rows or actual readiness counts
  read; it grants no deployment/cluster-identity approval. Safe result:
  `stage-release-plan/task2-ops-counts-v1/root-native-synthetic-fixture-result.json`.
  Actual identity observer source1d78 was installed through reviewed installerca31;
  its exact source/modes passed, but `--discover` returned `IdentityDiscoveryRefusedHold`.
  A one-shot bounded diagnostic705 located `protected_file:170` during
  `capture_service_before`; fixed lstat found root-owned legacy3e release
  directories0777/source files0666. Environment/unit paths were safe. No discovery
  retry, repair, app-row counts or deployment followed. Safe identity results:
  `stage-release-plan/task2-identity-discovery-v1/root-native-discovery-result.json`
  and `diagnostic-plan-v1/root-fixed-ancestor-metadata-result.json` in that leaf.
  Full readonly audit source for243 expected files (240Git+3Task1 assets) is frozen
  at `C:/Temp/endpoint-staging-legacy-permissions-20261027/source-freeze.json`,
  SHA256 `fe5f494eb5f6102564a81e4a8fda10272bd3e3681f4bb450e698cd1d1ea96232`;
  collector4e55 and26 tests have design review approval. Root's actual read-only
  audit `root-native-audit-result.json`, SHA256
  `faa21567d802aa2475c1e61d47435f91fe1d1b470e0e5bb7fb735dc091698141`,
  verified all243 source files with no missing/mismatched/unknown source paths.
  Exactly275 root-owned nodes require chmod:32 directories0777 and243 files0666.
  All60 opaque cache nodes already have correct0755/0644 permissions;4200 venv
  nodes were observed as metadata only. Source, selector, controls and service
  metadata stayed stable. No deployed code, SQL or private control contents were
  executed/read by that audit. Reviewed chmod-only repair completed at
  `2026-10-28T07:49:22.925375+00:00`:275 source nodes, caches60/venv4200 unchanged,
  all three writer scans zero. The preceding v1 snapshot refusal changed zero
  nodes: only `/etc` ancestor mtime/ctime differed. V2 accepts only the two exact
  reviewed timestamp pairs, before/after equal, with all other comparisons and
  original audit/target list retained. Its69 tests passed; executable freeze
  `4f12958a3aa07372cff6e998f06faa17984c0d4b6b1af7b6d340f7994f013e4a`.
  Root's reviewed post checker at07:49:53 verified all4535 nodes and555 journal
  files, including275 intent/done pairs. Source/selector/controls/PIDs stayed exact.
  Evidence under `C:/Temp/endpoint-staging-legacy-permissions-20261027`:
  `root-repair-v3-apply-result.json`, `root-repair-v3-reconcile-result.json`.
  Actual identity and same-postmaster binding now passed with PG16.15/schema39,
  uniform staging owners, nonsuperuser service role, one TCP5432 listener and one
  expected Unix socket on the same stable local postmaster. Native pre-counts:
  blocking/inflight/unknown/inconsistent0, enabled campaigns/live claims0;
  durable89 (82 context +7 steps), other DB backends6 before quiescence. Counts
  preserve queues and do not authorize application HTTP access. No code switch,
  quiesce or migration had occurred at that earlier readiness checkpoint.
  Current Task2 result: reviewed controller v3 freeze
  `c163728af0235b5e1481d225936fa3cf7246f46fdcdc99695632787b01e02f8e`
  passed22 focused tests, independent source review and actual native preflight,
  quiesce/backup, then a separate Root-approved switch. Preflight durable88 is a
  separate observation; fresh quiesce pre/post durable90→90 (83 context+7 steps)
  preserved queues with all bucket deltas0. Blocking/inflight/unknown/inconsistent,
  live claims/enabled campaigns and post-stop other DB backends were0.
  The new consistent Endpoint-only PG16 dump is11067144bytes, SHA256
  `14c91bd7b1f890da3b9412038ff0c42a0dcda07a53ab9cf4139aaa9a2c743c0a`;
  pg_restore-list, SHA, postgres0600 and private0700 checks passed. This new dump
  was NOT restored; earlier v6 restore receipts concern a different dump.
  Actual API215811/start_ticks78259783 and worker215868/start_ticks78260117 run
  UID999/GID988, executable `/usr/bin/python3.12`, cwd at the qualified62fb release.
  Same PG16 cluster, Helpdesk736/schema151/PID186923/ticks66070288, source/env/unit/
  site hashes and Root-accepted current Nginx213268/ticks77730265 remained unchanged
  across the upgrade. Historical Task1 Nginx119884 remains sealed. Root independently
  verified current Nginx UID/GID0, protected `/usr/sbin/nginx`, cwd/, stable captures
  and strict TLS before accepting that current pin; prior restart actor/cause is
  UNKNOWN, with no historical PID-continuity claim.
  Effective Settings retain operations API=true/module platform=true/module
  execution=false/OIDC=false/WorkTime=false; no client or feature enablement.
  The immediate post-upgrade snapshot independently verified schema42/71 public
  tables,19 newly owned tables and2 immutable triggers. At that historical point,
  both local admins had sso_migrated_at=NULL and confirmed identity, employee-session
  and WorkTime event/state rows were0. Strict CA/hostname HTTPS health200, all3
  Console files byte-exact, two admin401 and five disabled404 routes passed.
  The earlier browser tab1 login reload with `index-Dur28_-c.js` and
  `index-DPozMv6U.css`, blank fields/errors0, is a historical pre-login receipt.
  After the user's explicit authorization, the missing staging admin was created
  additively through canonical Argon2/AdminUser/audit, existing_accounts_modified=false.
  No existing-account reset, SSO grants or manually minted sessions were used.
  Genuine UI login PASS; dashboard/devices/updates/audit read-only PASS with19
  devices,7 releases and errors0. admin.created and the normal admin_session audit
  entries were visible. Some historical device username fields contain U+FFFD;
  they were neither corrected nor guessed. Current tab3 is authenticated staging
  `/admin`; tab1 was closed by the user and production tab2 remained untouched.
  The earlier rejected saved credential was not retried. No password/secret was
  read or recorded by this docs update. Owned WSS, mutating integration and
  SSO/MFA/A–F acceptance remain open.
  Admin receipts under `C:/Temp/endpoint-sso-staging-20261027`:
  `admin-create-authorized-result-20261028.json`,
  `admin-created-browser-acceptance-20261028.json`,
  `admin-console-readonly-acceptance-20261028.json`.
  Root's safe receipts under `C:/Temp/endpoint-sso-staging-20261027/stage-release-plan`:
  `root-task2-v3-preflight-result.json`, `root-task2-v3-quiesce-result.json`,
  `root-task2-v3-switch-result.json`, `root-task2-v3-postcheck-result.json` and
  `root-task2-v3-browser-readonly-result.json`. Public Keycloak promotion/MFA,
  AD-disable, semantic10+12 and real OS20-minute/notification gates remain open;
  no A–F checkbox is closed by this code/schema upgrade.
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
  One later fresh preparation passed actual execution and independent 21/21 checks:
  `keycloak_recovery_20261027_82e14168`, OID 23462, all 101 original table multisets,
  schema/ACL/sequences and original UUID/GUID/OTP exact. The catalogue grew from 7 to 8;
  both old20856/22159 forensic databases and all 29 historical trees were preserved,
  with exactly one valid new forensic backup. Preparation metadata is accepted,
  without semantic approval or private qualification. Safe independent receipt:
  `recovery-plan/fresh-candidate-after-run7/independent-live-reconciliation/independent-result.json`,
  SHA256 `78ecd95d47e2744eddaaa4a906e947bf0fad9effc3a82e3b073129ac2b4f3b5c`.
  ONE actual v9 master-only diagnostic then failed at `TokenConstructor` with
  `CandidateTokenMalformed`. Its bounded compact JWT/object, positive integer IAT,
  EXP>IAT, private18449 master issuer, admin-cli and remaining lifetime>=45s checks
  were true; `canonical_sid=false` and signature verification was not established.
  No realm GET, session inventory, purge, AD or browser phase was entered. All 8
  cleanup flags were confirmed independently at 05:57:42: no private processes/
  groups/listeners on the three private ports or candidate PostgreSQL connections;
  historical full 101-table inventories, source/config/public services/flags and original
  UUID/GUID/OTP stayed exact. New23462 is now MODIFIED forensic evidence, NEVER a
  pristine/retry candidate, alongside 20856/22159. No automatic retry occurred.
  Safe root result: `recovery-plan/master-token-probe-v1/root-one-master-probe-result.json`,
  SHA256 `6d8375c9367cbb0f7ba82bd7e6b3f63588aa8d04a8d3060774f0ebe187627b7a`;
  independent receipt: `recovery-plan/master-token-probe-v1/independent-readonly-reconciliation/independent-result.json`,
  SHA256 `0177dc85b03dfeea5dc8f82675eda50fc6876a7ab99b170b5b7c87513da61eab`.
  The SID boundary is narrower evidence than run7's unclassified purge refusal;
  it does not retrospectively prove that refusal's exact cause.
  Pinned upstream 26.8.1 commit `24ed1dadf3f246a555adb6d3d4a99e9b3003fb3b` generates
  18 cryptographically random bytes as 24 ASCII Base64URL characters without padding.
  The UUID-only local SID validator is a confirmed source contract defect.
  One stopped-DB aggregate found 18 master-bootstrap online IDs: all 18 canonical
  24-character Base64URL, UUID/other/null counts zero. No SID values/hashes/token claims were
  exported; those rows cannot be bound to the discarded prior JWT. Its actual SID
  format remains unbound. Safe aggregate receipt:
  `recovery-plan/master-token-probe-v1/stopped-sid-shape-metadata/result.json`, SHA256
  `774491373e3b94e55d6438a99914321dc3f4f5881b3f2ccbd4dd5e8ac90b60c0`.
  Source analysis is frozen under `C:/Temp/master-token-probe-v1/sid-source-analysis`.
  The subsequent narrow SID source fix is committed as `ef6d298f`; no scope/openid/
  lightweight configuration workaround was applied.
  Another fresh preparation passed independent 23/23 checks: candidate
  `keycloak_recovery_20261027_7175deb5`, OID24765, all 101 original table multisets,
  schema/ACL/sequences and original UUID/GUID/OTP exact at that preparation point.
  Catalogue grew8→9 and all three earlier forensic databases remained unchanged.
  Safe independent preparation receipt:
  `recovery-plan/fresh-candidate-after-master-probe1/independent-live-reconciliation/independent-result.json`,
  SHA256 `f09590caa6465065212ac25e443a894c3a9a733d3fb24c7d987a67685783badb`.
  ONE v10 native master-only diagnostic then completed its one login, one GET,
  exact fresh SID count=1 and all 6 inventory checks; all 8 cleanup flags passed
  independent reconciliation at `06:43:28.068110 UTC`. Canonical SID and all
  recorded structural guards were true, `signature_verified=false` retained.
  There was no AD/browser/purge/identity API/full-qualification/public-switch
  acceptance. Fourth24765 is now MODIFIED forensic evidence, NEVER a pristine
  candidate or rerun target. All four consumed databases must remain preserved.
  Root safe result: `recovery-plan/master-token-probe-v2/root-one-master-probe-result.json`,
  SHA256 `83af84118716f5caac5cf52bb942233319ca71649e2cd11dd517d00b87d25d82`;
  independent receipt: `recovery-plan/master-token-probe-v2/independent-readonly-reconciliation/independent-result.json`,
  SHA256 `39d0543e934d3a71c18ff65c66ed6bd4f707124704f06c70f69a09bb84b7da55`.
  The v11 source is committed/reviewed. Fresh-preparation v4 source freeze
  `58ed1210fc1d5e66f33de8f051491cee04a3d4be2cbeb5ebaa22460c7c29a18b`
  and wrapper `7df383659b3a3bcbf957ecfd9743a7ad9ef30a1bba63646a98e6feda4b27a360`
  passed109 Root tests and source review. It subsequently executed ONCE, preparing
  `keycloak_recovery_20261027_beb3f1f0`, OID26068, catalogue9→10, all101 original
  row multisets/schema/ACL/sequences and UUID/GUID/OTP exact before qualification;
  all four earlier forensic databases were preserved. Independent25/25 checks
  passed; receipt under `recovery-plan/fresh-candidate-after-master-probe2/independent-live-reconciliation/independent-result.json`,
  SHA256 `e47e0be1259bff205d50b69752e00355f3284c58243e3f500f8cbeb01089191b`.
  The earlier source-only closure remains preserved:
  `recovery-plan/fresh-candidate-after-master-probe2/source-freeze.json`.
  Run8 controller source passed262 tests by Root/reviewer; a three-character
  encoding correction is frozen as `d489902fe4034458ddc23391e14ae2e98fef2a7ffcab39fa305c8d78e45caaae`,
  parent integration freeze `fd833c319a9817e4e7fc44a3ac3e468791e29bcb832eca183d0dea49a9f1bc7b`,
  with executable pins unchanged. Actual protected installation verified three
  Windows buffers' ACLs/hashes; Root readonly pristine/archive/config/capacity
  preflight passed before ONE full native qualification. Status:
  `QualifiedUnreviewedDriftHold`, final17 canonical hash
  `056211bbe95f69ccaa138d5b9bba41d1f20b46146e0464d6e133800fe6121476`.
  Actual independent .19 reconciliation passed34/34 native checks and8 cleanup
  checks; local Windows private ACL/result bindings and zero process/handle
  observations passed. Same-token authenticated200→401 proof is present while
  the token remained unexpired; local `signature_verified=false` stays explicit.
  The nonce transcript was NOT independently reconstructed: qualification source
  pins and ordered receipts support only that provenance scope. The saved public checker source551556 and
  safe output9f141 were persisted from executed safe tool output, reconstructed
  rather than exact raw stdout; no native checker was rerun by that writer.
  Saved evidence freeze `81bb7907b53e2925f9cac2602af79c0e84b4a74fec19fe62497cec673d8f9f0d`
  under `recovery-plan/run8-root-gates/independent-live-reconciliation` preserves
  that limit. New `provenance-correction-v2.json` (`36803dfa`) and freeze
  `5276ea72` document cleanup-key normalization/counter tool-trace corrections;
  all v1 buffers and result values remain unchanged, with no native rerun.
  Candidate26068 is preserved
  post-qualification forensic evidence: not pristine/rerunnable and not promoted.
  Its10 changed tables and12 historical original/current tables remain semantically
  unreviewed. No public switch, MFA, AD-disable or real OS-idle acceptance is claimed.
  Semantic v1 was installed, but native inspection refused its schema pin;
  a bounded source-wrapper diagnostic exposed `NativeDatabaseOwnerOidSchemaMismatch`.
  A single repeatable-read metadata diagnostic using source `8cf455d9` confirmed
  default user/public context matches the exact historical golden, catalog-only
  context does not, and ONLY constraints deparser presentation differs. No
  baseline waiver, changed expected SHA, pairwise-fields or semantic approval.
  Safe result under `recovery-plan/semantic-drift-review`:
  `server-config-native-v1/root-install-plan/root-search-path-diagnostic-v2-result.json`.
  Semantic v2 adapter `f7a7229866dd846e7d93258dd4ea823ddfce8710466d6e508b8a9a12b8f0cb9e`,
  freeze `d3cc2d26a91d3c9795d78058f3d0336ab8eb28dda0da5a3ced2a2decca25aba6`,
  keeps catalog parse binding and CASE-dependent runtime deparser context. Fifty
  pure compiler/fake-runner tests were rerun by Root; independent installer review
  recorded 17 equivalent passes. Actual static install then
  validated all 5 protected source/support files' hashes and modes.
  ONE native `--inspect` completed with transport_exit=0/stderr_bytes=0. Original
  audit full101 rows and owner/ACL/schema binding are exact. Removed classified
  two `ExpirationRealmLoginFailure` occurrences, both meeting numeric-shape,
  timestamp-upper-bound and nonnegative-version checks. Added returned
  `SourceUnavailableHold` because its current targeted ledger does not match;
  `canonical_full101_historical_matches=false` is recorded separately. Native v2
  execution and its corrected deparser context are proved; Added's source-ledger
  hold is not a schema-pin or native-execution failure. No semantic approval,
  pairwise-fields proof, baseline waiver or switch approval follows.
  Actual safe receipts under `recovery-plan/semantic-drift-review/server-config-native-v2/root-install-plan`:
  `root-static-install-result.json` and `root-native-readonly-result.json`.
  Later historical Added scratch v3 matched BOTH sealed realm/server_config
  Counters exactly, then classified two Added `ExpirationRealmLoginFailure`
  occurrences with numeric/timestamp-upper-bound/nonnegative-version checks.
  Source35a1b114/freeze2b33b3c2 passed53 Root tests and independent delta review.
  One native run completed. Independent read-only postcheck found PG16 shut down,
  distinct system ID, no scratch PID file/process/socket/TCP listener, free recovery
  lock and unchanged six canonical units/controls/forensic metadata. All15 commands
  returned0;440 discarded stderr bytes have unknown semantics, not a warning-free
  result. V2's pre-initdb output-option failure and unrelated-process cleanup-scan
  refusal remain preserved. V3 changed only `--file=-` and membership-first scan;
  no historical Counter or input was replaced. Root's initial postcheck assumed
  zero stderr; its retained failure was corrected to the reviewed bounded-stderr
  contract with exact command metadata, without a lifecycle rerun.
  Safe receipts in `recovery-plan/semantic-drift-review`:
  `root-historical-v3-run-result.json`, `root-historical-v3-independent-postcheck-v2.json`
  and `root-historical-v3-postcheck-initial-assertion.json`. This proves narrow Added
  source availability/classification only. Pairwise fields/global semantic/full101/
  switch remain false. A separately gated new scratch is being prepared source-only
  for server-side original/historical field comparison; consumed v2/v3 are retained.
  The separate server-config pairwise gate subsequently PASSED: original and
  historical realm/server_config Counters matched together in one own PG16 DB.
  Both keys/three columns matched; only value/version changed, with both epoch
  values and versions advancing. One-step versions count0 does not prove a single
  writer invocation. Entry1e4fac98/base31de1ee6/freeze449768f3 passed24 Root tests
  and focused independent source/transport/receipt reviews. Independent shutdown,
  no-process/socket/port, lock, canonical-resource and both-backup-pin checks passed.
  All22 commands returned0;715 discarded stderr bytes remain semantically unknown.
  `root-pairwise-v1-run-result.json` and `root-pairwise-v1-independent-postcheck.json`
  prove only server_config_pairwise_proven=true; global semantic/full101/switch
  flags remain false. Next source-only work checks both full101 historical row
  multisets before reviewing remaining tables. Read-only archive type discovery
  found equal101-table/625-column layouts, five timestamp-without-time-zone columns
  and one OID column (`cluster_event.event_data`); both pinned cluster_event ledgers
  are empty. Safe discovery receipts: `root-full101-readonly-type-discovery-v3.json`
  and `root-full101-cluster-event-ledger-counts.json`. No archived DDL, SQL queries,
  restore or service actions occurred during discovery.
  The separate full101 availability gate then PASSED: actual archive preflight
  accepted both101/625 layouts (schema38555B/minimalDDL26640B each). One new own-PG
  run matched all202 original/historical row-multiset guards simultaneously, with
  exactly202 tables/1250 columns and empty OID-table checks. Freeze43bd5922 passed27
  Root tests plus focused independent source/transport/receipt reviews. Independent
  shutdown/no-process/socket/port, lock, canonical-resource and dump-pin checks passed.
  All22 commands returned0;715 discarded stderr bytes remain semantically unknown.
  Receipts: `root-full101-v1-preflight-result.json`, `root-full101-v1-run-result.json`,
  `root-full101-v1-independent-postcheck.json`. This establishes only
  full101_source_rows_match=true, not schema/ACL/global semantic/promotion approval.
  Both historical datasets are available for field review of all12 changed tables.
  The separate qualified-final export v2 subsequently PASSED for forensic26068:
  the whole inventory/schema/ACL/sequence JSON matched the pinned final golden
  INSIDE an exporting read-only PG snapshot, pg_dump used that same snapshot,
  and a fresh read-only comparison matched afterward. Dump454892B SHA
  `add83bd1224cd9edea3ee332b054ea236aef8d86d776cfe5e1bb82e665bdf69a`,
  protected context SHA401627a6, producer freeze9ea7d917;48 Root tests and focused
  independent source/transport/receipt reviews passed. Four new warnings matched
  the exact55-byte /dev/null password-file message; independent postcheck matched
  one more. Old715-byte discarded output remains UNKNOWN. Independent file/header/
  TOC/context, current forensic golden, zero-other-connection, own-client/backend,
  lock and canonical-resource checks passed. No JVM/restore/public switch followed.
  V1's pre-consume TOC refusal and Root's corrected checker-directory lookup are
  retained; no export replay or baseline replacement. Safe receipts:
  `root-qualified-export-v2-{preflight-result,run-result,independent-postcheck}.json`.
  Three-source v1 then restored all three pinned archives in its own PG16. All303
  row guards,303 tables/1875 columns and empty OID tables matched simultaneously.
  Freeze94ff2151 passed40 Root tests and focused source/transport reviews. Final
  original credentials/users/attributes/role edges and server_config remain exact.
  Basic-scope additions, LDAP retention, notBefore and exact seven source-defined
  realm defaults passed; historical identity pairing remains diagnostic only.
  Mapper rules and audit/event/session classification remain HOLD. Pinned
  canonical_mapper permits an absent false default on an existing mapper; a new
  bounded predicate proof must establish whether that explains the actual refusal.
  No original raw guard, receipt or baseline was changed. Independent postcheck
  passed:29 commands returned0, PG stopped, no owned namespace/sockets/locks,
  three dump pins and canonical resources unchanged.990 discarded stderr bytes
  remain UNKNOWN. Receipts: `root-three-source-v1-{preflight-result,run-result,
  independent-postcheck}.json`. V1 producer semantic/full101/switch flags stay false.
  V2 freeze537ec045 then passed55 Root tests and focused delta review. One separate
  native run matched all303 guards and all22 predicates,0 unknown differences.
  Diagnostics prove the one original mapper's source-permitted absent false
  default and two new exact-five mappers per side; all23 removed user/client pairs
  have closed local/flag/realm/user/client links,0 orphan/surviving/unsupported
  representations. Audit/events are append-only shape proofs, not actor/content
  attribution. Independent postcheck passed29 commands, PG shutdown,0 owned
  processes/sockets/locks, three dump pins and unchanged canonical resources;
  990 discarded stderr bytes remain UNKNOWN. V1 source/receipts stay immutable.
  Receipts: `root-three-source-v2-{preflight-result,run-result,independent-postcheck}.json`.
  Separate read-only current-vs-f92 observation found structure and100/101 tables
  exact; only two server_config rows differ. No DB writes/new baseline; client and
  backend gone. This snapshot cannot replace a fresh quiesced switch gate.
  Root decision `root-candidate-semantic-review-decision.json` (b4e09b05) approves
  exact sealed final field semantics for promotion PREPARATION; peer review
  reconciled all six evidence hashes and scope. All raw producer flags stay false.
  Isolated rename/rollback rehearsal, fresh current/candidate guards, full forensic
  backup and durable one-use journal still precede public switch. Public provider/
  MFA/AD-disable/application acceptance remains pending.
  Separate dummy rename rehearsal freeze0df32cb5 passed29 Root tests and focused
  source/transport review, then its one native run stopped in prepare_fixtures /
  UnclassifiedSqlClientStderrHold before all six cases. The consumed namespace is
  retained, never retried. Source inspection found superuser-only logging options
  also sent by the nonsuperuser dummy connection; the discarded failure bytes do
  not establish that as the old cause. Independent failure-only postcheck passed:
  9 commands, interrupted psql record8/stderr247, total412 discarded stderr still
  UNKNOWN, PG shut down,0 owned processes/socket/lock and six canonical resources
  unchanged. Receipts `root-promotion-rehearsal-v1-run-result.json` and
  `root-promotion-rehearsal-v1-failure-independent-postcheck.json`. V2 planning
  isolates old-versus-corrected role-option compatibility in a fresh namespace;
  no role privilege grants or public changes. Backup/quiesce/switch and permanent
  owner grants remain pending.
  V2 freeze7ea48bf2 passed49 Root tests and focused source/transport review. One
  native attempt passed exact old-options rejection/corrected-role connection,
  inherited none/panic/panic logging and unchanged role/catalog, then stopped at
  run_cases/OwnedUnixListenerAmbiguous, cases0. All six rename cases are unexecuted.
  Independent failure postcheck passed21 commands, one expected startup/code2,
  others0, PG shutdown,0 owned processes/socket/lock and canonical6 unchanged.
  Total1072 stderr bytes do not reconstruct or reclassify the earlier412 bytes.
  A metadata-only canonical /proc observation (0SQL) found one main-PID-owned
  flags65536/type1/state1 listener and0 connected pathname rows; it cannot bind the
  failed private snapshot. Primary Linux source distinguishes listening from
  connected pathname entries. Source-only v3 will retain FD ownership and add an
  actual held-client before/during/after proof. No reuse of consumed v2. Receipts:
  `root-promotion-rehearsal-v2-{run-result,failure-independent-postcheck}.json`.
  The human selected the permanent SSO owner; its unique enabled AD record matched
  the current Windows SID. Owner grants, MFA enrollment and bootstrap removal are
  pending; access identifiers/credentials are not included in this plan.
  Actual browser proxy run3 passed all 3 fake-owned literal127 loopback cases in
  44.818s under the original150s deadline; Node controller source SHA256
  `518fec7e27fe1eaf85cfdaaa7b54a079d1595e6462a6c574c33063fd3118aa65`.
  The owned job was empty before cleanup and cleanup was confirmed. First and
  second runs remain HOLD with1pass/2fail each. Safe result under the browser
  evidence root: `recovery-plan/browser-v2/owned-fixture-diagnostic-run3-result.json`,
  SHA256 `8a6b1fadaf2275f67c25ff0926da1a0eb3db94290feafbe76c136ab7251778b9`.
  This isolates browser transport behavior and proves no production TLS, AD/OTP
  or private Keycloak acceptance. Run7's partial original-browser success above
  does not itself qualify the private recovery flow; none of the five consumed candidates
  may be retried or reused as pristine.
  No guard relaxation or public switch follows from these observations.
  Run8 subsequently completed private runtime qualification and session purge as
  recorded above. Complete semantic drift review and a separately reviewed public
  database switch remain pending.
  Never re-enrol OTP, accept the replacement subject or run another AD window
  before completing that recovery.
  AD-disable investigation confirms source-level inclusive LDAP filtering,
  removeInvalid=false/NO_CACHE and upstream MSAD always reading UAC; live public
  configuration/AD-disable behavior remains unproved. Preserve UUID/OTP without
  account reset or OTP re-enrolment.
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
  diagnostic mutations were performed. Staging Endpoint's later user-authorized
  missing-admin creation and genuine UI/read-only acceptance passed, as recorded
  above; current tab3 is authenticated staging `/admin`. Owned WSS and mutating
  integration acceptance remain pending. Production update-admin authentication
  was available at the earlier user-login snapshot and has not been revalidated
  on October28. The historical saved staging test login was tried ONCE and rejected,
  then cleared; screenshot `staging-saved-login-rejected.png` is retained. Its
  credentials were not retried and no existing account was reset. No password or
  secret was read/recorded by this docs update; do not bypass current authorization.

Private redacted receipts are under `C:/Temp/helpdesk-sso-staging-20261027`,
`C:/Temp/endpoint-sso-browser-20261027`, `C:/Temp/endpoint-sso158-linux-20261027`
and `C:/endpoint-platform-wix-build/staged-3.2.158-9423d9c`. These are local evidence
locations, not portable release artifacts. See root PLANS.md for handoff.
