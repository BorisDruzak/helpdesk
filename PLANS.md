# 2026-11-06 Unified user administration

Goal: separate Users (profile/account/role/queues) from reference Registries.
Scope: Helpdesk admin frontend and atomic person/account access provider only.
Constraints: preserve existing dirty work; no dependencies, migration, production
deployment or live role grants. User explicitly requested implementation of the
unified card proposed in this chat. Existing checkout/branch reused.
Decisions: compact searchable list + Profile/Account/Permissions card; canonical
group editor remains within Users. Legacy access links redirect to Users.
Current State: local implementation complete. Unified Users card owns profile,
account, role and queue/group grants; Registries owns reference/device jobs.
Legacy redirects and compact person tools preserve advanced workflows. Clean
cards adopt operation results; conflicting drafts block saves pending reload.
Safe unique-login membership aliases preserve password/SSO grants without
changing ticket ownership or duplicating operators/approvers. Scoped reviewers
report no remaining actionable findings. GitNexus unavailable in this session;
bounded source/tests used; Query 5 and SQLAlchemy 2 documentation checked.
Next Steps: live authenticated staging acceptance/deployment is not performed.
Verification: isolated PG83 + saved-view3 + adjacent noDB48 passed; frontend80
focused tests, browser5 (1366/1920/390), TypeScript/Vite build and workspace
verification passed. Full frontend run1061 passed/5 failed; two stale sidebar
assertions fixed and rechecked, three failures outside touched surfaces remain
confirmed separately (requester role label and two support upload tests).
Handoff: docs/ADMIN_USERS_WORKSPACE.md and
docs/ADMIN_USERS_VERIFICATION_2026-11-06.md record usage, checks and limitations.

# 2026-10-27 SSO + Helpdesk + Endpoint + WorkTime

Latest checkpoint, 2026-10-27 05:30 UTC (10:30 Asia/Yekaterinburg): Helpdesk
`736f3ae8` has all 18 exact-revision CI layers green and four pinned-provider
cross-repository tests passed; staging `.118` runs schema151. Production remains
`6cca48e5`. Full six-scenario receipts for 736, an owned requester/support lifecycle
and the live Windows gate remain open. Endpoint production `62fb4c83`/schema0042
has SSO/WorkTime flags off; staging `3e3528fb`/schema0039 now has verified capacity
and still awaits genuine application-admin/active-work acceptance and a reviewed
live switch. Endpoint source HEAD `f4120e9e` commits the archive-permission producer
fix with 14 real tests; previous `44302b59` provides v8 namespace source `2e720674`,
used in run7 below. Staging candidate62 has 33 exact
dependencies, pip-check and actual service-user Settings validation passed with
SSO/WorkTime false, plus offline SQL through0042. Live3e/schema0039/PIDs remain
unchanged; candidate preparation does not close application deployment gates.

Windows158 source `9423d9c` has actual fresh read-only native READY evidence:
local processes stable for 98.508769s; the same authenticated Gateway session across
70.298344s of server samples advanced last-seen by 90.027236s. Receipt `ac83bb20`
and Endpoint documentation commit `118ff` retain the historical-WSS caveat and
source/IP-attestation limits. This does not close notification, 20-minute or
real-user SSO acceptance. ALT `.210` has native 158 packages; its authorized
singleton 158 rollout now reports COMPLETED/APPLIED at 03:58:58 UTC with post-restart
handshake confirmation and a new Gateway session. Normal UI at04:04 UTC now shows
COMPLETED/APPLIED1, errors0, working0; its later APPLIED screenshot is distinct
from the earlier assignment-only receipt. Actual bounded native acceptance now
verifies selected Core158/source9423 and all 98 manifest files; host processes
stable for 70.133513s, same Gateway280.288251s/last-seen270.008612s. Current protected
four files match across the on-host window ONLY; raw pre-OTA baseline is unavailable,
so historical exact continuity is unverified. Receipt `d6c3c706` and Endpoint
report commit `c9421b42` retain 20-minute/notifications/real-user SSO/crash-rollback
limits. Production update-admin authentication is
now available through the user's existing login; staging application admin remains pending.

Keycloak failed candidate OID 20856 retains the original UUID/OTP. Actual run3/v4 ended
in an unknown refusal; run4/v5 refused `PrivateRuntimeListenerNotLoopback`;
run5/v6 refused `PrivateRuntimeUnexpectedClusterSocket`. Those reconciliations
verified all 101 candidate tables unchanged. Later run6 reached the browser-cookie
gate, then refused `PrivateRpcReplyMissing` after changing seven tables in 20856;
that failed database is preserved and cannot be retried or reused as pristine.
Schema/sequences and UUID/OTP remain exact; browser positive/negative/revocation
and final17 acceptance proofs are absent. No semantic drift or cause is inferred.
Canonical PIDs/OIDs stayed unchanged, private processes absent and private ports
free. Narayana V3's isolated library probe PASSED: default `SocketProcessId`
opened one loopback listener, `MBeanProcessId` opened none and returned the native
PID. This does not attribute prior candidate sockets or qualify Keycloak runtime.
One actual fresh preparation and independent metadata review passed: candidate
`keycloak_recovery_20261027_2190f3d5`, OID 22159, all 101 original tables, schema/
ACL/sequences and UUID/OTP exact. Old failed20856 and all six old catalogue entries
were preserved (catalogue now 7). Preparation metadata was independently accepted;
semantic review/private qualification remain HOLD. Subsequent run7 recorded
positive original-browser initial and SSO callbacks, then RecoveryRefused /
`UnclassifiedRefusal` in `purge_restored_sessions_master_last` before any
`session-provenance-before.json`; exact cause UNKNOWN. OID22159 now has eight
changed tables and is forensic evidence, NEVER a pristine retry candidate.
Independent `OwnedCandidateStopConfirmed` cleanup/reconciliation found owned
PIDs347374/347618 gone, all private ports free, public services unchanged and
both candidate identities/original UUID/OTP exact. No purge completion, revocation,
negative-browser, final17 or public-switch acceptance follows. Browser proxy run3 passed all 3 fake-owned
loopback cases in44.818s with Node controller source `518fec7e`; first two HOLD
runs retain1pass/2fail each. The original150s deadline and owned cleanup held.
This is isolated browser transport evidence, not private Keycloak qualification.
Future recovery gates remain held; failed22159 and failed20856 must be preserved.
Audit DB 19553 matches all 101 ORIGINAL row multisets;
only relation-owner/database-ACL structural differences are accounted for.
The original/current 12-table semantic drift remains UNREVIEWED.

The user explicitly approved `.118` +10GiB. Fresh v6 capped backups ran 03:54:44–
03:54:51 UTC and both real PostgreSQL16.15 SCRAM restores completed at 03:55:57 UTC;
all nine artifact hashes/ACLs/provenance and owned cleanup passed independent
review. Root's one-shot absolute15103-extent Apply passed at 03:58:49 UTC. Independent
read-only reconciliation at 04:00:15 UTC verified LV and ext4 both 63346573312 bytes
(previously 52609155072), exact UUIDs, available 16672423936 bytes, unchanged
application source/config/PIDs and strict HTTPS. The consumed exact-command
marker is retained: no second Apply/retry. Old expired v5 evidence/lease were
preserved and not reused; production `.19` storage was not touched.
After staging candidate installation, last observed free space was 16536801280 bytes.

Production Endpoint62 had a P1 permission defect: source0666/directories0777
from its Windows-produced archive/runbook. Root's metadata-only repair completed
04:41:02 UTC; independent 04:42:29 verification confirms 373 nodes (299 qualified,
74 cache) root-owned0755/0644, 12 necessary cache ownership changes, 373 intent/
completion journal pairs and zero currently open writable descriptors. All 265
archive files' bytes/mtime/inodes, 5208 venv nodes, selector and service PIDs314437/
314438 stayed unchanged; strict TLS health200. No exploitation or historical
absence-of-writes claim. Immutable old archive `d6df0a87` is retained. The five-file
producer fix is committed as `f4120e9e999dd236dce7a47c53df98b84136edea` with
14 real regression passes. The immutable old archive was not repacked or redeployed.
Production Helpdesk6cca's audited0555/0444 release remains unchanged.
Windows `.120` remains untouched/HOLD except approved passive maintenance
collection; staging Endpoint application-admin credentials remain pending.
No account reset or authorization bypass. No handoff, claims, campaigns, real tickets or
diagnostic mutations were performed on `.120`. Keep all A–F live acceptance gates unchecked.

Next steps: diagnose the preserved run7 purge refusal read-only without cause
assumptions or retrying either forensic candidate; complete independent private
recovery qualification/semantic drift review under a new reviewed gate before any public
switch or new AD-disable window. Staging upgrade preparation proceeds under its
existing OS authorization and release gates; application-admin integration
acceptance remains unavailable after invalid credentials in staging tab3.
Keep active-work/live-switch gates held; do not reset or bypass authentication.
Complete the six Helpdesk receipts,
owned lifecycle, Windows gate and real installed SSO/notification acceptance.
Current evidence: `docs/superpowers/plans/2026-10-27-sso-worktime.md`. Preserve
unrelated files and retained failed/partial receipts. The task remains incomplete.

## Historical early implementation checkpoint (superseded)

The following initial observations and next steps are historical; the checkpoint
above governs current versions, publication, recovery and evidence freshness.
At that earlier checkpoint, reviewed product changes
were implemented; independent final security review found no P0/P1 and two P2
issues. The shared identity-service budget and paginated explanation queue are
now corrected with focused regressions. Helpdesk current focused PostgreSQL
38 passed, previous broader PostgreSQL95 passed; updated no_db identity/harness
51 passed. Full frontend890 passed/2 unrelated FormsBuilder failures, focused
file rerun5 passed; full no_db1686 passed/2 failures: new-table cleanup assertion
fixed and verified, unrelated subprocess-start timeout passed on focused retry.
These results are NOT a green full release gate. Workspace verifier passed.
Endpoint current PostgreSQL76 passed; UI68 unit/14 browser; native notification
source smoke returned Later. Keycloak import/bootstrap succeeded after reviewed
permissions/build-option/export-shape repairs; dedicated service now UP and
verified corporate-CA HTTPS discovery200. Clients remain disabled pending pilot.
ALT192.168.101.210 is accessible as osn-admin, WorkstationK11.4, Agent3.2.127,
active domain user session; local Windows Core149 still requires full Setup157.
Next: freeze candidate commits, full CI/release evidence, build/sign Windows/ALT157,
then separately deploy applications and run real AD/OIDC/device pilot. Do not
claim installed/published157 or completed live SSO/WorkTime acceptance yet.

Goal: implement the supplied six-stage A–F ecosystem spec with independent
subagent review and focused verification at each stage. User authorizes both
repositories, Endpoint server deployment, separate agent update, Linux test
machine and local domain workstation validation. No fleet rollout, bulk AD/GPO
changes, forced account migration or organization-wide personnel monitoring.
Design: docs/superpowers/specs/2026-10-27-sso-worktime-design.md. Execution plan:
docs/superpowers/plans/2026-10-27-sso-worktime.md.
Current State: Helpdesk starts at6cca48e5 on codex/ui-support-001 (includes main
plus20 existing fixes). Endpoint implementation is latest-main78d24e9 isolated
at C:/Users/admin-2/Documents/endpoint/.worktrees/sso-worktime-20261027 on
codex/sso-worktime-20261027; preserve original dirty outdated checkout.
Decisions: RegistryPerson is canonical; retain UiUser keys; exact issuer/sub
and canonical ADGUID require explicit confirmed binding; separate employee/admin
cookie sessions. No username-derived technical attribution; verified temporal
device/account mapping required. Authlib1.9.1, opaque BFF sessions, upstream
introspection failclosed, explicit MFA assurance and per-application grants.
Next Steps: finish logout observer attribution regression, freeze reviewed
Helpdesk/Endpoint feature commits, run release gates, configure isolated
Keycloak realm/LDAPS pilot accounts, deploy compatible applications and build
signed157 agent Foundation/Core. Then installed Windows/ALT acceptance.
Verification: initial GitNexus group status checked (Endpoint index1behind),
source identity reviews complete; DLP regression reproduced technical-admin
list/detail200 before explicit grant guard, then test passed after403guard.
AD-MAIN inventory0Keycloak/java and no sso/keycloakDNS. User instructed existing
KC check on admin-2@192.168.100.11, then separate .19 deployment if absent.
Infrastructure: corporate CA located on.5, pinned to approved publicCA. Generated
nonexportable3072RSA machineCSR onAD and issued exact AD-MAIN.sosnadmin.local
ServerAuth certificate serial1005; installed and refreshed LDAP cert without
reboot. Verified from.19 TLS1.3+chain+hostname. DNSsso->.19 inAD; user added
routerDNS, verified server/localresolution. Keycloak26.8.1 installed STOPPED,
independentPG16/keycloak5544online, configroot:keycloak0640, mainPG5432 and
Endpoint/Helpdesk services remainactive. Disk12GiB. Infrastructurecommits
132aa6e79e88a9d397d2b526647dca974b17ca95,
7bc49c160bef52d88b6c00d1c16d6d489c494aeb,
a99cf6e298ced146a898b1621231c28a358c26f7.
Verification: latest Helpdesk focusedPG95pass2deselected +actualprivateCA TLS;
Endpoint combinedPG71pass including concurrenttimesheet versions/immutability;
UI Endpoint68unit/14Playwright; Helpdesk67focusedunit/3Playwright. Independent
reviews reproduced/fixed stalepermissions/MFA/breakglass/refresh/logout, partial
coverage/history/annotations, DLPstringmodes/pureHRapproval, WindowsABI12/160.
Companion143pass6skip; addedleasefencing/presentauthorization/backlogprogress,
current schedules andfreshHelpdesk identity; nativeinstalledacceptanceremains.
Handoff: product code remainsuncommittedpendingfinalgates; broadEndpointtests
running (agentendpoint_broad_tests), observerlogoutfixhelpdesk_stage_a,
ADpilotprovisionhelperkeycloak_infrastructure. OriginaldirtyEndpoint untouched.
LocalPCactualCore149/installerprovenance79 requires signed157Setuppreflight;
buildPython312/PyInstaller6.22.3/WiX4available,codesigningcertprivatekeyinstore.
OldALTips.162/.70unreachable; user gives .210 own-admin, checkingpasswordSSH.
Context7quotaexhausted officialdocsfallback. No agentupdateorfleetrolloutyet.

# 2026-10-26 Full CI and publication

User authorized full isolated-PostgreSQL CI, fixes, commit and push after checks.
Branch codex/ui-support-001 was synchronized with its origin tip fee8268c.
Precommit gate runs in a dedicated local snapshot because bundle generation
requires committed/clean frontend inputs. The user branch remains uncommitted
until that gate passes; final exact-HEAD CI is required again before push.
First attempts stopped at clean-source guard and then exposed a launcher
UnicodeEncodeError under redirected legacy Windows output. Fixed outer CLI
stdout/stderr UTF-8; ASCII/CP1251 regression tests pass (runner18).
Full runs exposed Windows forced-checkpoint cleanup latency (176s;103s sync)
and raw disposable-DB credentials in pytest CI/JUnit diagnostics. Fixed: scoped
Windows DROP90/95s budgets; discarded cluster fsync/full_page_writes/synchronous_commit
OFF; redaction before output and structured report sanitization, with interrupted
child stopped first. Policy flags, short secrets, typed JSON/XML, SHA and paths
have regressions. Focused evidence: CI runner41, wrapper19, DB harness46+6,
actual role/concurrency9; independent review has no remaining findings.
Precommit snapshot a8c11aacc3bca3a9d54f68866e92178ecf63b2f8 passed18/18
fullgate:881 frontend,165browser without retry,304scripts,1660server no-DB,
1manual Endpoint module skip,6migration,375webAPI/384tickets/90observer/29runtime.
Green artifact validator accepted; no shared DBfallback; ownedcluster stopped
and removed. Documentation/evidence table refreshed. Publication procedure:
12 atomic Conventional Commits with per-area focused checks, exact-HEAD fullCI,
then normal push without history rewrite. Exact commit/files/check receipts and
final remoteSHA are recorded in artifacts/review-20261026-publication.json and
the final response. Preserve preexisting untracked scanner/design/tmp artifacts;
production/staging remain untouched.

# 2026-10-26 Isolated PostgreSQL acceptance and test review

Goal: configure repeatable local PostgreSQL, execute pending real concurrency/
role-change acceptance, review tests, and fix confirmed findings.
Scope: disposable loopback-only PostgreSQL16 in ignored .run; no system service,
production/staging connection, shared database or deployment. Runtime credentials
are generated per run, redacted and passed only through child environment.
Implemented: verified EDB16.15 runtime; scripts/run_with_local_postgres.py creates
and stops its owned cluster. Harness creates/drops pc_support_test_* via explicit
local TEST_DATABASE_ADMIN_URL. Current-user-only ACL handles Windows restricted
PostgreSQL token; control output uses a file to avoid inherited pipe EOF waits.
Test review fixes: real pg_blocking_pids observation replaces timing-as-proof;
reversed bulk concurrency; full cleanup and real HTTP200/403/401 for token roles;
strict browser API allowlist; stale catch/finally, ABA upload/send, draft-reset
coverage with five sensitive in-memory mutants.
Verification: PostgreSQL acceptance9 passed, expanded regression29 passed,
then final9 passed again using the completed process-tree wrapper. Two deliberate
in-memory PostgreSQL mutants failed as expected; normal sources stay unchanged.
Server no-DB1656 passed/1 skipped; scripts293; focused frontend68; browser5;
runner lifecycle16; inventory369 files/0 issues; workspace/diff checks passed.
Handoff: complete; all owned clusters stopped/deleted (run directory empty).
Keep prepared PG16.15 binaries in ignored .run for repeatable future runs.
Previous review changes/untracked work preserved; no commit/deploy.

# 2026-10-26 Project review and confirmed defect remediation

Goal: review the current Helpdesk project, fix reproduced defects, remove proven
unreachable legacy code, and verify the combined result. User authorized local
code changes. Preserve unrelated untracked files and deployed services.
Scope: server authentication/authorization, ticket lifecycle and attachments,
webapp session isolation and asynchronous ticket actions, retired module helpers,
project scripts and regression coverage. No dependency additions or deployment.
Constraints: current source and tests override the older indexed branch;
GitNexus group status is healthy for its tracked revisions. Context7 lookup was
attempted but its monthly quota is exhausted; use installed APIs/official docs.
Baseline: workspace verification passed; server no-DB 1542 passed/1 skipped;
frontend 847 passed; scripts 277 passed. Static F821 check found retired module
helpers plus a missing SQLAlchemyError import in inventory error handling.
Next Steps:
- [x] Fix stale token roles, DB cooldown/memory fallback and WS replay/delivery ACL.
- [x] Isolate query/mutation caches across authenticated identities.
- [x] Guard late upload/send results and retry failed read acknowledgements.
- [x] Fix assignment capacity/bulk lock order and attachment authorization/cleanup.
- [x] Remove unreachable module-administration and support-workspace code.
- [x] Replace quadratic email validation and prune generated verification inputs.
- [x] Review combined diff, docs/CODEMAP and regression/browser evidence.
Verification: server no-DB1655 passed/1 skipped; frontend877; scripts277;
fresh TypeScript/build;34 fixture browser cases; F821/static inventory0 errors;
workspace verification and diff-check passed. Independent review found no
remaining actionable issues. See docs/PROJECT_REVIEW_2026_10_26.md.
Handoff: local review/fixes complete; no commit/push/deploy. No configured
isolated PostgreSQL connection: real DB concurrency and role-change acceptance
authored but not run. Ambiguous upload commit retains blob for reconciliation;
WS per-frame authorization adds DB work. Production/staging were not changed.

# 2026-10-19 Unified queue and restored inspector

Actor: support/admin. Primary job: choose an appeal and work in chat. Secondary:
full-list navigation and contextual inspection. Archetype: list + conversation +
inspector, with drawer fallback. User explicitly requested one reversible queue,
full-list access/resizing and the retained right panel. Implement within existing
repositories, state, routing and inspector; retain roles, ownership, FSM/SLA,
capacity and closure policies. No production scope or data migration.
Implemented: TICKET_QUEUE_MODE, global staff access/candidates/notifications,
common new-ticket routing, partition command guards, mode projection/settings;
full-list header action, persisted pointer/keyboard resizing, shared rich inspector.
Checks: frontend847; server no-DB1542 passed/1 existing skip; build;13 fixture
browser flows at1366/1440/1920/390. PostgreSQL6 plus final focused5 passed
(unified/partitioned scope, active-role/load guards, concurrency, ownership and
common routing/auto-assignment policy). Final routing policy PostgreSQL/unit6
passed: retain priority, SLA and approval on new and existing tickets. Configuration
helper2 passed. Review:
source and docs checked; retained inspector move verified separately from its
small semantic changes. GitNexus tools unavailable; source boundaries verified.
Next:
freeze candidate, exact-SHA full CI, canonical staging deploy, installed acceptance.
Leave staging running. Preserve unrelated untracked work.

# 2026-10-19 Support Messenger and take availability

User selected reference 1 (Messenger) and authorized implementation, verification
and isolated staging deployment. Preserve canonical queue membership, assignment,
FSM, SLA, public/internal privacy, attachments and all additional tools.
Implemented: readable bubbles, sender/date/time hierarchy, anchored composer,
Ctrl/Command+Enter, scroll preservation, collapsed structured description; shared
server take availability and specific membership/capacity errors. No dependency
or migration. Existing admin is outside the affected queue; retain that policy.
Verification: no-DB server 1537 passed / 1 existing skip; frontend 846 passed;
PostgreSQL 3/3 (concurrency, persistence, queue/detail/command denial parity).
Next: finish responsive visual checks, freeze candidate, exact-commit full CI,
canonical staging release and installed browser acceptance. Leave staging running.

# 2026-10-19 UI-SUPPORT-001

Goal: everyday support queue, compact three-area ticket and clean conversation.
Scope: existing TicketListPage, typed support APIs and canonical workflow only.
Constraints: preserve FSM, audit, internal visibility, SLA and closure policies;
no dependencies, production deployment or real-ticket mutations. Preserve unrelated
registry branch and untracked work. User approved the reference-based approach.
Decisions: five simple filters, explicit take-in-work through status/in_progress,
public reply guarded by status/ownership under the ticket lock; advanced functions
remain reachable. Use existing state, mutations and design primitives.
Current State: implemented on codex/ui-support-001 from main 520b6218. Existing
advanced modes are retained; shared dialogs and typed mutations are reused.
Next Steps: frozen-candidate full CI, then draft PR. No production deployment.
Verification: workspace sanity and diff check pass; frontend suite 843 tests;
server no-DB 1532 passed, 1 existing skip. Fresh build and focused browser 13/13
cover simple 1366/1920/390, existing advanced modes and normal-shell navigation,
with synthetic fixtures. Source workflow PostgreSQL concurrency 3/3 passed through
an owned staging tunnel, now closed. The broad staging API/DB selection exceeded
its runner limit; its owned process was stopped and it is not counted as green.
No deployed service or real ticket is changed. Full CI must bind to the committed
candidate. Final regressions cover assignment permission and internal event tabs.
Handoff: task active through CI/PR; preserve unrelated untracked files.

# 2026-10-18 Build answer branches from an empty decision

Actor/job: an administrator starts with only a yes/no question connected to a
decision and builds a separate next step for each answer. Live staging reproduced
the dead end: target-first branch creation offered only the ancestor question,
which is a forbidden cycle. No answer editor appeared before a target existed.
Scope: show incoming question and typed answer outputs on the node and inspector;
create a new step plus conditional transition atomically, or connect an existing
target. Separate sibling creation from insertion into an existing transition.
Preserve existing rules/processing, bounded undo, cycle guards, unknown/fallback
semantics, canonical server execution and schema/API contracts. No dependencies.
Verification: live RED saved in an owned unpublished draft. GREEN: frontend832
(Studio191), fresh TypeScript/Vite build and eight fixture-browser cases at1366/1920,
including two-node startup, typed false, independent siblings, undo/redo, save/reload
and real answer/route-handle drag with processing metadata retained.
Independent review, exact-candidate staging acceptance and hosted CI remain in the
candidate receipt. Preserve user maps and leave authorized staging running.

# 2026-10-15 Connected question choices in condition rules

Actor/job: an administrator builds a question-to-condition route in the existing
Studio workbench and chooses the question's answer without technical identifiers.
Reproduced on staging in a separate unsaved synthetic map: the connected radio
question was available, but Add condition and changing its source seeded `exists`,
hiding the actual options. Selecting equality manually showed them immediately.
Scope: choice-aware initialization only on explicit add/source-change actions,
shared by edge and block-branch editors; preserve saved presence/nested rules and
canonical runtime semantics. No schema/API/permission or registry changes.
Verification: component and browser regressions reproduced RED. GREEN: Studio174,
fresh build and four browser cases at1366/1920 passed, including source switching,
typed booleans/multi-select and retained saved rules. Browser geometry assertions
wait for the existing sticky action bar to settle without relaxing their bounds.
Installed-staging acceptance and final CI belong to the candidate receipt.
Keep the user's open map untouched and leave the requested staging service running.

# 2026-10-15 Guided Request Studio schema v3

Goal: map-owned SLA profiles/directions, composite branch authoring and explainable
canonical processing, complete JSON/YAML v3 interchange, public catalog search.
Scope: one codex/guided-request-schema-v3 branch from e5080f5, isolated staging,
draft PR. Production, existing SLA/queue changes and real-service publication excluded.
Constraints: historical maps/sessions unchanged, no parallel policy/SLA runtime,
no client authority, preserve unrelated untracked files and user browser drafts.
Decisions: explicit defaults; selected branches assign processing in traversal order,
last explicit assignment wins with provenance; priority uses existing typed facts.
Current State: implementation and independent risk review corrections are in draft
PR #43. Candidate ab2b0b3 passed all 18 mandatory CI layers, including frontend806,
browser148 and legacy/v3 PostgreSQL APIs; its identical-tree PR merge was tested.
Installed staging confirms schema150 and strict TLS. Owned-draft YAML/JSON semantic
roundtrips, invalid queue paths, urgent/standard server comparison and specialized
unknown-answer fallback passed live. No service was published.
Live 1366 inspection exposed comparison-button overflow inside the inspector.
A local wrapping fix reproduced RED then passed browser1366/1920 and 10 unit checks.
Next Steps: pass final-candidate CI, install the final candidate, recheck the narrow
inspector on staging and stop the staging service. Keep runtime receipts separate.
Verification: RED/GREEN contract/runtime/search/authoring checks; backend noDB310,
frontend805, fresh build and browser7 passed. Disposable PostgreSQL unified/ACL7,
runtime/approval/policyhealth22 and migration150 operation1 passed. Workspace/diff and
machine-schema drift checks passed. Runtime manager case actually approves through
the existing support endpoint; invalid/ineligible managers use explicit fallback or block.
Handoff: spec/plan docs/superpowers dated2026-10-15; runtime/Studio/search ownership
separate. Exact-SHA CI/installer/browser receipts belong to the candidate evidence;
no production operation or real-service publication is authorized.

# 2026-10-14 Requester form regression

Actor: requester and admin using their own requester workspace. Primary job:
select a service, answer its published questions and create a request without an
agent when server policy permits. Separate debug tab preserves user drafts.
Reproduced staging bootstrap403 for admin despite requester workspace permission:
initial failures were hidden and periodic refetch showed the loading screen again.
Repeated schema normalization discarded explicit empty priority policy, adding
five questions to setup-help forms absent from converted maps. Also reproduce
frontend ignoring server-disabled profile completion gate. Fix these boundaries
with ownership, projection, loading/refetch and no-agent regression checks.
Staging deployment only. No automatic publication or rewrite of existing maps.
Checks: frontend48 and backend38 pass; build/workspace/diff checks pass. Isolated
PostgreSQL acceptance2 pass: admin no-agent actual create with foreign session/
ticket rejection, and user setup-help projection/preview without profile or agent.
Installer and real-browser acceptance follow the frozen commit.
Installed eaf7549f on staging: repeated bootstrap200 keeps answers; setup-help
fields match the map. Browser creates test T-000058 without profile/agent. Ticket
page revealed remaining403 on own consent reads; add two owner-scope regressions
and align those reads while retaining consent-decision role boundaries.

# 2026-10-14 Unified service scenario authoring

Approved model: direct Create service -> v2 map, one editable source, typed
processing facts into existing policies, JSON/YAML interchange, safe conversion
without deleting old forms or automatically publishing. Staging only; production
and Endpoint excluded. Spec/plan under docs/superpowers dated 2026-10-13.
Canonical server projection replaces independent template questions for v2;
historic v1 versions and pinned sessions remain executable. Migration 149 expands
the immutable version CHECK without rewriting rows. PyYAML 6 added for YAML.
Local regression: backend151 and frontend154 pass; build and workspace sanity
pass. Isolated staging PostgreSQL API4 pass, including actual ticket submission,
v1 session preservation, document no-side-effects and archived conversion replay.
Readonly review completed; material findings corrected with regression tests.
Installed on staging with schema149. Browser direct creation, pointer entrances,
inline naming, independent drag, conditions, resolution check/finish, delete/undo,
two entries, server processing (P1/P3 and SLA), confirmed publication (11 outcomes),
full-page preview and JSON/YAML zero-diff round-trip verified. Invalid YAML rejected.
Converted9 forms to drafts; existing8 maps retained; one unavailable source blocked.
No old published service auto-switched. Prior admin requester UI returned bootstrap403;
it was incorrectly interpreted as a profile gate (see requester regression above).
actual submission is proven in the isolated PostgreSQL API test with complete owner.
Browser revealed palette overlap, technical publication paths and key-order dirty
state; corrected with regressions. Exact-SHA installer receipts and final browser evidence are recorded under tmp/.
Current guide: docs/UNIFIED_SERVICE_SCENARIOS.md.

# In progress: 2026-10-13 Studio entrance connections and employee preview

Actor admin/auditor; primary job author one map in the existing workbench.
User asks Start-to-block connection = entrance, inspector employee-view tab and
full-page preview toggle. Base cc07b594; same feature branch/PR42. No new API,
schema, dependency or runtime evaluator. Preview is local and shares canonical
requester controls/content; server testing/publication remains authoritative.
Model creation/metadata/limit regressions reproduced RED then GREEN. Shared
requester29 tests and build pass. Browser5 cases pass at1366/1920/820: pointer
entrance creation, undo/redo, persisted contract, inspector/full-page preview,
local answers, Escape and isolated Ctrl+Z/Y. Review found inspector-remediation
and modal history defects; corrected with regressions and scoped re-review clear.
Full unit730 passed plus remediation2 passed; all126 browser fixtures passed.
Screenshots1366/1920 inspected; workspace sanity and diff check passed.
Production/scenario/policy/ticket publication excluded; staging update follows
canonical exact-commit installer once frozen and verified.

# In progress: 2026-10-13 Studio map-first workbench refinements

User browser feedback: root Studio opens the visual workbench immediately;
left Catalog/Blocks selects an offering/map in place; resizable explorer,
inspector and editor height; actionable missing-configuration hints; temporarily
hidden Forms/Policy Health navigation with canonical routes and permissions retained.
Actor: admin/auditor. Primary job: author the map. Secondary: select service and
check readiness. Workbench archetype remains explorer/canvas/inspector.
Base: 97902413e5fa114a81943009f358ebb6dc6cd52c, existing PR42 branch.
No API/schema/dependency change. No production or scenario/policy publication.
Sizes are browser preferences, not graph/draft/version mutations. Independent
review found catalog projection and selection/autosave/mutation races plus hint
navigation/settings access; all five corrected and independently re-reviewed.
Cold-load and multi-map discard RED reproduced. Final frontend unit: 131 files /
725 passed; TypeScript/Vite build passed; all 120 browser fixture tests passed,
including pointer resizing, browser preference persistence, hint inspection and
viewport containment. Screenshots at 1366/1920 inspected; scoped workspace sanity
and diff check passed. No backend change: previous full CI evidence remains tied
to the prior merge revision, not this refinement.
The canonical installer deployed 031f7e33 to isolated staging; backup/schema148,
exact bundle identity and authenticated real browser smoke at1366/1920 passed.
Live cold-load inspection additionally found the start node clipped after initial
height measurement at1280/1366. A measured-before-canvas mount fix reproduces
RED then GREEN at1280/1366/1920; focused10 units and fresh build pass. Extended
123 browser fixtures passed; independent scoped re-review has no findings.
Final full unit run725 passed; a cold lazy-module test timeout was diagnosed and
its bounded wait corrected without relaxing role/read-only assertions. Build,
workspace sanity and diff checks passed. Follow-up staging update remains next.

# 2026-10-13 Studio v3 usability refinement

Implemented against the three provided visual references in the existing Studio.
Compact new-map starter, executable simple/diagnostic/empty drafts, contextual +
insertion, real entrance nodes, progressive inspectors, result-side canonical
binding, readable viewport layout and actionable graph hints. Existing revision/CAS,
policy runtime, publication confirmation and role guards preserved. No production
deployment, real scenario publication, real tickets or Endpoint actions performed.
New browser fixtures: access authoring and diagnostic shared graph at 1366/1920/820,
6 PASS, including condition preservation, undo/redo and no zoom reset on save;
browser console/network clean. Focused backend contracts/runtime/readiness/entrances:
133 PASS. Final checks: 136 focused frontend/layout tests PASS; all 55 existing Studio
browser cases plus 6 new usability cases PASS across targeted runs. Final
TypeScript/Vite production build, scoped workspace sanity and diff check PASS.
All 6 browser-authored saved drafts passed canonical server DTO and DAG validation.
Local fixture servers stopped after checks. Evidence is local fixture evidence;
installed staging acceptance is not claimed. Reference PNGs are not server contracts.

# In progress: 2026-10-13 Guided Request Studio v3

Branch `codex/guided-request-studio-v3`, baseline `bb8c521faaf76eea01119f314f68fecdeb34cefb`.
Spec and plan: `docs/superpowers/specs/2026-10-13-guided-request-studio-v3.md`
and `docs/superpowers/plans/2026-10-13-guided-request-studio-v3.md`.
Goal: one map, multiple version-pinned entrances, contextual graph workbench,
canonical Helpdesk policies/approvals and requester catalog. Production, actual
scenario publication, real tickets and real diagnostic actions excluded.
Backend additive contracts/runtime and all-entry readiness implemented; no migration
(head 148). Safe partial admin simulation discloses unrelated errors without
weakening full publication validation. Archive-category dependencies now account
for draft/current/pinned entrances and release archived maps. Final review's
three P2 findings fixed (dynamic handles, multiline synonyms, approval save race).
Verification: full no-DB server 1375 passed/1 skipped; scripts 275 passed; baseline
frontend 711 passed, latest changed surface 129 passed; scoped workspace and all
six CI audits passed, mutation smoke 4/4 killed. Real pointer browser graph flows
passed at 1366/1920. Full fixture browser118 PASS; isolated Linux PostgreSQL/API36 PASS with
fresh migrations to148 and temporary role/database cleanup confirmed. Latest
full-width map sizing and viewport-contained inspector subset:10 PASS. Initial DB fixture illegally changed immutable published JSON;
fixed to insert replacement snapshots; failed/interrupted attempts preserved,
temporary roles/databases removed. No application service was started/stopped.
Final screenshots preserved and inspected. Remaining: frozen diff/commit and draft
PR with canonical CI. Existing group approval markers cannot expand to decision
actors; UI honestly exposes trusted manager/owner/lead and Registry account
selection. Preserve unrelated untracked files/prototype; stage only task files.

# Complete: 2026-10-12 Independent processing template creation

Fixed missing new-template creation from service authoring. Dedicated
/app/admin/forms/new reuses single-template canonical publication, explicit
confirmation and existing published rules; separate-tab creation and list refresh
preserve service values. Generated own keys and no shared-pack rewrite.
Frozen checks: 682 unit, 110 fixture browser, build/typecheck, scoped workspace,
diff and exact Semgrep passed; zero task findings/secrets. Independent review
findings closed. Exact 2f2a2ec9 CI38260933737 passed all18 canonical layers and
Endpoint contract job; installed identity/active staging verified.
Actual strict-TLS browser created/published one template, refreshed the preserved
service draft, created/published its bound service, rendered the new requester
form, answered existing common priority facts, and created/opened ticket T-000057.
Final requester path has zero browser/unexpected HTTP errors. Failed helper local
validation (omitted common facts) remains separate; resumed same owned records.
See docs/INDEPENDENT_TEMPLATE_STAGING_ACCEPTANCE.md for hashes/identities/limits.
User's service/scenarios/tabs preserved. Staging active; production excluded;
Sonar deferred. No backend/schema/dependency/Endpoint changes.

# Complete: 2026-10-12 Independent service creation and authoring clarity

Approved staging follow-up: standalone service creation/publication, optional
scenario authoring, clearer visible transitions and actionable simulation errors.
Implemented at 1f022cbd; corrected the stale advanced-disclosure test at 519cc296.
Frozen local verification: 678 unit tests, 106 fixture browser cases, fresh
build/typecheck, scoped workspace and diff checks passed. Independent source review
found no blockers. Exact 519cc296 CI run 38251065696 passed all 18 canonical layers
and Endpoint contract job. Exact security scan: zero task-file findings/secrets.
Installed 519cc296 staging identity and active service verified after acceptance.
Actual strict-TLS browser: created one service independently, published ordinary
form, created a scenario, reproduced/explained missing transition, repaired its
graph through UI, completed simulation, configured mandatory published policies,
published, completed self-resolution and created/viewed one synthetic support
request. Publication checked 161 outcomes. Final requester path: no browser or
unexpected HTTP errors. Interrupted helper stages resumed using the same owned
records; historical failed harness logs are retained, not relabeled as green.
See docs/INDEPENDENT_SERVICE_STAGING_ACCEPTANCE.md for identities and evidence.
Production untouched. Staging remains running by user request; synthetic demo
service/scenario and one test ticket retained for inspection. Sonar remains
explicitly deferred by user. No backend/schema/dependency/Endpoint changes.

# Complete: 2026-10-12 Unified request catalog follow-up

Approved bounded change: one offering card; requester mode separate from draft
status; selectable service categories including plain forms; dedicated offering
and settings pages; explanatory subcategory selection. Production excluded.
Backend RED reproduced duplicate total (3 instead of 2), missing root-category
filter and missing mode projection. GREEN: 31 catalog tests; 194 focused no-DB tests.
Frontend RED reproduced missing offering link and empty category explanation.
Focused components, settings navigation/pending-save and URL-context regressions
pass. Fixture browser: 33 passed across 1366, 1440, 1920 and tablet 820 widths.
Independent review findings corrected; no remaining blockers. Exact-source
PostgreSQL API validation at 86246512: 20 passed with temporary-role cleanup.
Full fixture browser regression: 106 passed after adapting the remaining legacy
scenario links to the dedicated offering page. An unavailable offering's detail
explains its publication/form prerequisite instead of claiming requester access.
The first CI run stopped at the fixture layer after three successful layers;
the corrected exact-head CI38239732745 passed all18 layers and Endpoint acceptance.
Installed candidate112bead8 passed four actual staging viewport checks:12 unique
services, complete root filters, separate pages, dirty guard and real category
options. No JS/application network errors; one telemetry request was cancelled
by test navigation. Staging remains active for user inspection; production untouched.
Evidence: `docs/UNIFIED_REQUEST_CATALOG_STAGING_ACCEPTANCE.md`. Sonar deferred.
No schema migration, publication, enablement or user-data rewrite is introduced.

# In progress: 2026-10-11 Guided Request Studio v2

Canonical plan: `docs/superpowers/plans/2026-10-11-guided-request-studio-v2.md`.
Execution ledger: `docs/superpowers/plans/2026-10-11-guided-request-studio-v2-progress.md`.
P10 catalog fidelity: human category paths, description, active version number,
latest scenario/draft timestamp and independent category collapse verified by
63 frontend tests, 2 owned PostgreSQL tests and 4 browser viewport checks.
Actual staging A–J and exact CI
remain open; P10 is IN PROGRESS.
P10 readiness covers finite multi-select policy combinations, graph-only numeric/
text predicates, and distinct omitted/unknown optional answers.
P10 publication result now includes target offering, immutable definition summary
and a catalog-validated requester deep link with isolated draft restoration.
P10 new-offering creation is inline with canonical profiles/templates and explicit
source-bound atomic catalog promotion; full staging/CI gates remain open.
Branch: `codex/guided-request-studio-v2`, specification baseline `507ee7154b947391d51148d3a8929b77983eb77e`.
P0 PASS: new domain/auth RED 13 failures + 2 legacy passes; existing PostgreSQL API 5,
no-DB server 22 and frontend 74 passes. Independent review and owned DB/tunnel cleanup complete.
P1 PASS: typed DTO/TS + migration147/storage; PostgreSQL10 and corrected FK/concurrency2,
DTO/reset42 and frontendwire1 pass; tsc, cleanup/inventory/workspace gates pass.
P2 PASS: canonical graph runtime, 80 domain/runtime/reset and 18 legacy form/preview
tests; frontend21, tsc and inventory pass. Independent review has no blockers.
P3 PASS: admin CRUD/RBAC/CAS/audit + pure simulation; PostgreSQL14 (9new+5legacy),
fast92, inventory/cleanup/workspace and independent review pass.
P4 PASS: catalog/five-step React shell, legacy form inventory, category filter
before pagination, CAS save/reload and unsaved navigation guard. Frontend39,
fast94, PostgreSQL2, browser3, build/inventory/workspace and independent review
pass; details/screenshots are in the execution ledger.
P5 PASS: selected block/field workbench, typed conditions and multi-role mappings,
safe graph edits, bounded undo/redo and responsive preview. Frontend59, fast94,
browser7, build/inventory/workspace and independent review pass.
P6 PASS: owner-scoped pinned sessions, typed steps/Back/TTL/replay, safe picker
choices and redacted audit; per-offering requester flow preserves legacy forms.
Fast106, frontend24, PostgreSQL3 plus audit rollback1, browser4, build/inventory/
workspace and independent review pass.
P7 PASS: canonical ticket preview/create, trusted facts and human summary,
owner/device gates, transactional session/ledger/audit and idempotent submit.
Fast217, frontend28, PostgreSQL3 plus final legacy regression9, browser8,
build/inventory/workspace and independent review pass.
P8 PASS: independent readiness, source-bound one-use confirmation, atomic version
publication and rollback into a new draft; canonical dry-run parity fixes.
Fast122, frontend61, PostgreSQL14 plus latest parity/calendar3, browser11,
build/inventory/workspace and independent review pass. Finite coverage limits
and remaining processing/UI acceptance gaps are explicit in the ledger.
P9 PASS: admin-only typed diagnostic failure simulation and full failure-branch
readiness; readable consent/fallback inspector and truthful result labels.
Unsupported pre-ticket attachments stay fail-closed. Backend78, frontend51,
PostgreSQL1 plus expanded side-effect repeat1, browser4 at all four viewports,
build/inventory/workspace and independent review pass. P10 remains required,
including actual A–J staging/CI and processing-selection/presentation gaps.
P10 processing increment verified: existing published policy choices now apply
through canonical registry references in dry-run and actual creation; complete
processing results use canonical OLA shape and truthful notification rules.
Fast142, frontend54, PostgreSQL legacy/new8 plus selected SLA parity1, browser4,
build/inventory/workspace and bounded independent review pass. Full P10 still
requires actual staging A–J, field/readiness fidelity audit and canonical CI/AC matrix.
No production deployment, live publication or Endpoint execution.

# Completed locally: 2026-10-11 Helpdesk tickets, requester chat and Russian quality UI

Goal: restore readable SLA/profile data and use the shared support shell for tickets;
separate requester ticket list from a full-height chat; localize the quality dashboard.
Approved bounded design: shared navigation/light default, dedicated existing detail URL,
fixed reply composer, secondary description/history view. No Endpoint changes or migrations.

Current state: implementation in the canonical checkout; independent review has no remaining findings.
Verification: 77 focused backend/domain/HTTP-adapter tests, 92 frontend tests and 16 browser
scenarios passed; typecheck/build and scoped workspace verifier passed. Browser evidence at
1366x768/1920x1080 and requester mobile is in artifacts/ui/2026-10-11.
Deployment has not occurred; DB-backed support integration and the production release
gate (exact-SHA CI artifacts, staging evidence and accepted release configuration) remain open.
Handoff: preserve unrelated Sonar/scanner files; publish/deploy only through the reviewed release workflow.

# Completed locally: 2026-10-02 Helpdesk Sentry Browser Observability v1

Approved spec and plan: `docs/superpowers/specs/2026-10-02-helpdesk-sentry-browser-v1.md`
and `docs/superpowers/plans/2026-10-02-helpdesk-sentry-browser-v1.md`.
Baseline `03e0cb1557b714b6f21fbc20c73f473625a459ca`; branch `codex/sentry-browser-v1`.
Runtime public config, React 19/Router tracing and positive payload projection
are implemented. Verification: 580 frontend tests, 70 server/static/backend
observability tests, 36 affected Playwright flows, production build, workspace
verifier, compileall and diff checks passed. Independent read-only review has
no outstanding findings; its same-origin ingestion cookie finding was reproduced
and fixed with credential/referrer omission. Real disabled browser load was
checked with clean console and no horizontal overflow. No production deployment
or Endpoint/Sentry-server changes.
Source-map upload remains deferred to internal CI/scanner infrastructure.

# Active: 2026-10-02 Post-Cutover Legacy Cleanup

Baseline `1818f1988306061e806aa5668347f4389a5b91ca`; candidate branch
`codex/post-cutover-legacy-cleanup`. Plan:
`docs/superpowers/plans/2026-10-02-post-cutover-legacy-cleanup.md`.
Remove fleet UNKNOWN controls and proven-dead scheduler/Agent/descriptors;
preserve Endpoint technical and Registry business authority, historical data,
and compatibility vocabulary. Discovered command-center local telemetry
fallback is removed under specification item 8. No production deployment.
Focused backend (17), fleet component (6), typecheck, Vitest (534), build,
workspace verifier and browser (4 tests, both target sizes) passed. Independent
review resolved unknown-as-offline aggregation and its regression assertions.
Exact-SHA canonical CI/Endpoint acceptance remain in progress.

---

# Active: 2026-10-01 Helpdesk Sentry Backend Observability v1

## Goal / Scope / Constraints
Optional backend Error Monitoring/aiohttp tracing only, following the supplied spec.
Start HEAD8167da2f915bfb2abff3c7f17489060d10a00192;
branch `codex/helpdesk-sentry-backend-v1`. No production deployment, Sentry server
changes, Endpoint edits, frontend SDK, database schema or secret publication.
Preserve the unrelated untracked scanner/config/scratch paths.

## Decisions / Current State / Next Steps
Plan: `docs/superpowers/plans/2026-10-01-helpdesk-sentry-backend.md`.
Central bootstrap and defensive error/transaction projection; existing environment
contract and immutable release identity. Official SDK2.71.0/API checked before
implementation. Test RED, implement, focused gates, independent security review.

## Verification / Handoff
83 focused tests passed, including28 Sentry regressions, auth/config and deployment
fixtures. Scoped workspace/compile/diff, safe-fixture security CLI and test inventory
(311files/0issues) passed. Independent read-only review: Spotlight issue fixed,
full-envelope privacy/outage/shutdown/import isolation verified; no remaining findings.
No actual ingestion/TLS, full release gate, push or rollout performed; intentionally
deferred to separately authorized publication/deployment. SENTRY_DSN runtime-only.

---

# Active: 2026-10-01 Admin Device & Inventory Endpoint Cutover v1

## Goal / Scope / Constraints

Execute the supplied coordinated cutover spec through Endpoint provider,
typed Helpdesk port/BFF, Registry overlay, UI replacement, runtime retirement
and exact-SHA/staging acceptance. Production deploy and table deletion are
excluded. Preserve unrelated scanner files and the integrated Sonar fixes.

## Decisions / Current State

Plan and source ownership matrix:
`docs/superpowers/plans/2026-10-01-admin-endpoint-cutover.md`.
Helpdesk starts at c935a532657786ae00ab9c9de1dbd34624b1b143 on
`codex/admin-endpoint-cutover-v1`; Endpoint starts at
4a8258deace4fa09becdc8e27e4d344d1d1767a7 on
`codex/admin-device-context-summary`. Provider commit
464405a659e615f8fed40fe9daac61a7297e30e8 merged by PR 39 into
73f1b9c83a7cc41063994314df36f4cdeca03cc9. Full Linux/PostgreSQL CI
36823442540: 1524 passed, 8 skipped; merge CI 36823884973 succeeded.
Fleet uses UUID pagination and three bulk reads without raw payload loading.
Provider display-name contract fix 38ddabe3c0badf09a033bb7523a89a7d2c5059a0
merged via PR 40 as 12c63655b491cd1fc328b05128414eefba4ee49c;
exact source full Linux/PostgreSQL CI 36825653896 succeeded.
Helpdesk pins exact published 38ddabe and OpenAPI SHA256
27425c76c95874606330ad282c66689b25e3bb95666d657cfe712e8e0d1ac137.

## Next Steps / Verification / Handoff

A–G implementation, final runtime review and live acceptance are complete on
35c67c4080979a2d583ba2b01e79db80b985304e. Exact full CI 36848506139 passed
all 18 layers with isolated PostgreSQL; real cross-repository contract 3 cases passed.
Trusted actual staging Windows verified expanded fleet filters, five completed
safe profile collections, actual history/hash/diff, exact Registry PC link across
different UUIDs, canonical preview/apply/admin audit with inventory number
preserved, OFFLINE on Agent stop and UNKNOWN on provider outage. Normal browser
console/page errors, retired and direct provider requests were zero. Both DBs,
releases/config hashes/scopes/Windows enrollment restored; all stage units stopped.
Draft PR39 targets frozen c935a532 starting base and excludes pre-existing Sonar
work. Production remains untouched except the approved read-only metadata audit.
Final delivery: verify the documentation and navigation labels freeze with its full exact-SHA CI,
canonical staging revalidation/restore and final 63-item report; no production deploy.

# Completed locally: 2026-10-01 SonarQube evidence remediation

## Goal / Scope / Constraints

Execute the source-verified [remediation plan](docs/superpowers/plans/2026-10-01-sonarqube-evidence-remediation.md)
under the explicit user `/goal` request. B1–B6 and D1–D5 are implemented locally
on `codex/sonarqube-evidence-remediation`, from baseline
`e9c9bf37dc26af98e9da91b7d424bc4efcee7990`. Preserve existing scanner artifacts;
no Git publication, deployment or Sonar mutation is part of this work.

## Decisions / Current State

Form edge cases, parent cancellation and related debt are corrected with
regressions. Form modules retain the facade; create retains trusted identity and
transaction ownership; workflow retains effect order. The extracted detail page
is a compatibility surface; the active router remains TicketListPage.
CODEMAP and testing docs describe the new boundaries and browser fixture.
The user selected local integration with `main` after acceptance. Scoped
implementation commits and a documentation commit capture the verified result;
remote publication and deployment remain outside this choice.

## Next Steps / Verification / Handoff

Final acceptance passed after independent review corrections: 140 backend
unit/contract checks, 529 frontend tests, 109 tests across final DB/API selections,
and 3 Chromium scenarios at both required resolutions. Temporary staging databases,
templates and roles were removed. Build, strict inventory/schema audits, metadata
parity, workspace and diff checks passed. Fresh results, commands, limitations
and cleanup are tracked in [evidence](docs/SONARQUBE_REMEDIATION_2026-10-01.md).
Contextual Sonar findings keep their source-verified rationale; unseen issues
are not declared fixed. No claim about deployed runtime or refreshed Sonar.

# Follow-up: 2026-09-29 requester refresh and support device presence

The production T-000004 lifecycle revealed two read-side defects: requester
messages/status did not refresh after operator actions, and support used retired
Helpdesk transport presence for an Endpoint-bound computer.

The working-copy fixes add visible-tab refresh and focus/reconnect refresh to
the requester queries, and a bounded read-only Endpoint presence port to support
snapshots. Provider failures remain unknown; legacy timestamps/version do not
substitute for authoritative presence. Regression tests cover current online and
offline state, mismatched identity, retired devices, provider timeout/403, invalid
or oversized responses, and missing inventory context. No schema change.

Local backend/frontend/build and real-browser fixture checks are recorded in
`temp/ticket-read-defects-fix-report.md`. Production is unchanged. Its current
Helpdesk credential returns 403 for the required `context.read` contract, so
permission provisioning and a fresh reviewed staging/release gate remain open.

# Completed: 2026-09-29 Requester Registration & Device Binding — First Wave

## Goal and scope

Deliver the supplied cross-repository registration/profile → Endpoint possession
code → RegistryPerson/device binding → requester devices → normal ticket closure
flow. Execute the detailed plan in
`docs/superpowers/plans/2026-09-28-requester-device-binding-first-wave.md`.

## Constraints and decisions

Staging acceptance preceded the user-authorized production rollout on 2026-09-29.
Windows is the live target; ALT binding acceptance is excluded.
Keep Helpdesk and Endpoint deployments independent. Preserve the pre-existing
local `AGENTS.md` edit. No legacy Agent pairing, browser-to-Endpoint credentials
or anonymous UI-user/device binding. Endpoint owns proof; Registry owns the
business relationship. Do not publish readiness from skipped tests.

## Current state and verification

The user confirmed local 3.2.78 tray code/display/copy/refresh/open on
2026-09-29. The remaining manual First Wave gate is closed. User-authorized
production rollout deployed independent Endpoint
`b0ccfe3c16f8ce5319b1203c72df4e432fa5e0de` (full PostgreSQL CI
36521813006: 1513 passed, 8 skipped) and Helpdesk
`ecb68704edd750e6deac3a495fb90d5a8f44465a` (accepted exact full CI
36473600061, schema 146, accepted webapp digest). Endpoint schema is
0036_device_binding; the canonical Helpdesk provider/OpenAPI pin is unchanged.
The local Windows package remains 3.2.78, with its original production enrollment.

Production browser acceptance passed registration, login, profile, native IPC
challenge, anonymous fragment/login return, authenticated redeem and immediate
primary-device display for `binding.production.260929.99ecb0` / ADMIN-2.
Registry read verification confirms role user, resolved RegistryPerson, one
active primary_user relationship sourced from endpoint_possession_proof and
exact Endpoint device `c450fc70-63e6-4c2b-baf6-7de79820d63f`.
Page exceptions: zero; raw code/password were never persisted. Four unused
attempt accounts were deactivated with the canonical audited user repository.
Production organization dictionaries were empty: isolated TEST ONLY department
and location were created through audited Registry operations for this fixture.
Real departments/locations remain an administrator setup requirement.

Fresh staging protected restore revalidated the accepted ecb/61acfde runtime,
closed bound ticket/diagnostic records and a new no-device outage ticket.
Staging was restored from its fresh 2026-09-29 baseline: schemas 0035/145,
original environment bytes/release links, all three services inactive. VM120
retains the previously restored 3.2.75/stopped baseline. Production services
and the local agent remain running for their authorized normal operation.
The agent retained one open authenticated session for over eleven minutes
following the combined Endpoint rollout; no new internal_error disconnect.

Canonical details: `docs/REQUESTER_DEVICE_BINDING_FIRST_WAVE_ACCEPTANCE.md`.
The following staging checkpoint is historical: exact ecb local/VM registration,
fixture conflict/admin review, no-device tickets, bound diagnostics, support
lifecycle and requester-confirmed closure passed before production promotion.

The following accepted-baseline checkpoint predates that live acceptance.

Current accepted Helpdesk staging/CI baseline is
`28bb0d72664152812f35ec62d1f6a77343a41960`; provider service/lock remains
`61acfde9401a51fc7e3006733721ee1c2be12b4b`. Endpoint Windows runtime source is
`0f5cc69fff8a603eb829189bf0ddfdccc26580aa`, package 3.2.78. The user authorized
updating the local workstation and a browser test. Local registration, native
IPC code, anonymous fragment/login return, primary binding and different-owner
conflict passed in a real staging browser; no ownership was silently replaced.
Bound ticket T-000036 exposed a missing idempotency key in the support launcher
(400 ENDPOINT_DIAGNOSTIC_REQUEST_INVALID, no operation created). The bounded
correction reuses the existing actor/ticket intent helper at all three callers.
Admin claim source projection and Endpoint replacement reason guidance/action
were corrected with failing-before-fix regressions. Fresh exact-SHA full CI,
accepted bundle deployment and repeated browser diagnosis remain required.
VM120 complete browser/diagnostic/lifecycle acceptance and original-state
restoration remain open. No production deployment is authorized.

Historical implementation checkpoints follow.

Endpoint runtime source is frozen at `731f271ad0ba1ba7a134ace45b6bc8771542f688`
and published as draft PR A #37. OpenAPI SHA256:
`e0161970a2f08dcc80fc333676319c2018065743d74f880da160404115b6cdec`.
Migration 0036 adds possession challenges and durable throttles. Frozen-provider
Linux/PostgreSQL 16 gate passed all 648 tests; Windows tests passed 369.
Canonical MSI build produced EndpointAgent-3.2.76-x64.msi, SHA256
`1806841273267058082678ac81c0b63442bc4ac794785d65e3ef2b8a6c233672`.
MSI installation/live acceptance remain unconfirmed. Provider candidate HEAD is
`61acfde9401a51fc7e3006733721ee1c2be12b4b`: subsequent changes bound CI to ten
minutes and fix shared test-harness disconnect/ASGI portal shutdown ordering.
OpenAPI/runtime bytes are unchanged. Current contracts: 428 passed; Gateway:
80 passed. Exact-HEAD provider dispatch 36397790108 passed all 648 tests.
Helpdesk lock now pins this candidate SHA and the unchanged OpenAPI hash.

Helpdesk implementation includes registration capability/disabled UX, memory-only
fragment capture, the typed redemption adapter, exact provider lock, Registry
mapping migration 146, ownership/idempotency/conflict handling, requester devices
and optional device selection through preview/create/diagnostic context. The
user's AGENTS.md remains unstaged. The release target branch is
`codex/helpdesk-process-model` (this remote has no main branch).

Helpdesk draft PR B #38 is published; source candidate before this checkpoint is
`0de166865f002967aabf82c1acd11be25a3432ef`. Verification: clean-source no-DB
export at 0de166865f002967aabf82c1acd11be25a3432ef: 895 passed, 1 skipped;
frontend 486 passed; complete browser fixture checks 31 passed; build,
compilation, contract lock and workspace verifier passed. Real PostgreSQL Registry,
concurrency, resolver and context checks: 23 passed. Ownership/admin approval:
4 passed; authorized on-behalf context and complete binding/no-device/bound-ticket
API checks: 2 passed. True provider/adapter/WSS acceptance passed in GitHub
contract CI. Full CI correctly rejected missing cleanup profile/table/count
fixtures; they are corrected, strict model-schema audit and 60 cleanup/harness
checks passed. Run 36396167011 passed migration schema (5) and ticket DB (372)
checks before being cancelled by the next revision. Final-pin CI 36397130080
passed contract acceptance but failed an existing Studio async-button timeout;
the test now awaits the preview request and exact confirmation button. A fresh
full CI is required on the new candidate. Fixture browser acceptance
is separate from real Windows acceptance. Reviewer found no remaining confirmed
blocker after cached-person status and explicit no-device context were corrected.

## Next steps and handoff

First Wave implementation, Windows acceptance and authorized production rollout
are complete. Preserve protected backups, the user's AGENTS.md edit and frozen
runtime provenance. Populate real organization dictionaries before normal
requester profile onboarding. TEST ONLY entries and the successful test account
are explicitly synthetic; its local-device primary binding remains active for
inspection. Draft PRs are published; deployment does not imply branch merge.
ALT live acceptance remains intentionally excluded.

The following candidate handoff is historical.

For the current candidate: obtain fresh canonical CI and accepted bundle;
repeat bound safe diagnostic/lifecycle and Admin source/reason UI checks;
complete the separate VM120 chain; restore staging databases/config/releases
and test enrollment, then stop staging services. Retain local package 3.2.78
as explicitly requested while restoring its original enrollment and stopped
service baseline. Protected backups and redacted checkpoint/runbook are in
the existing staging evidence; do not infer production telemetry unchanged.

The following earlier handoff is historical.

Accept provider CI and run fresh full canonical CI on the updated exact SHA lock.
Then deploy both reviewed independent staging services and run the complete
Windows/tray/browser/ticket lifecycle, fixture conflict and restore checks.
The approved runtime sudo/secret-input channel is pending and blocks staging
deployment; installed staging services and Windows enrollment remain untouched.
The disposable PostgreSQL cluster `/tmp/endpoint-binding-cxpOwN` was stopped
after automated checks; its SSH tunnel is also stopped. MSI 3.2.76 and its
canonical canary/preflight scripts are staged on Windows but not installed.
No production deployment and no ALT live acceptance are authorized by this task.

# Previous checkpoint: 2026-09-27 Helpdesk Production Readiness v1

Current accepted rollout (2026-09-27): frozen runtime candidate
`bd3090bd72633a83be5e5f83a894ac959306cf74` passed exact-SHA full CI
36316004862 (18 layers; one existing frontend timing failure passed the
same-SHA failed-job rerun). The accepted artifact, schema 145 and immutable
manifest bind fresh staging and production receipts under
`artifacts/release/bd3090bd72633a83be5e5f83a894ac959306cf74/`.
Staging T-000033 and production T-000003 completed all 17 business steps,
including requester reply/support visibility, real existing Windows 3.2.75
agent diagnostic terminal success, and requester-confirmed closure. Staging
T-000034 completed the core flow during actual Endpoint unavailability.
Quiesced production backup and actual isolated restore passed at schema 145.
Production runs the independent HTTPS/WSS Helpdesk release `bd309...-offline1`,
with one server process/worker/backend and zero restarts on this release.
Release/full, business/success and backup/restore markers are readable by the
Helpdesk account. Actual Tech Panel has zero blockers and two warnings:
inventory scheduler unknown and no configured minimum agent version.

All functional changes are merged and remote-verified in
`codex/helpdesk-process-model` at
`581bdd22d46ba92e2bd64fcc6d0504d125471cbe`; its tree equals the tested runtime
candidate. Subsequent documentation commits are not the deployed runtime SHA.
Production remains running as authorized. Helpdesk and Endpoint staging
services are stopped, temporary actors disabled and memberships removed;
Windows original protected production enrollment is restored.
The initial admin handoff exists only in root-owned mode-0600
`/etc/helpdesk/initial-admin-handoff.json`; rotate after first operator login.

31 historical risk dispositions are verified, five remain open/nonblocking
for the accepted v1 scope. SCALE-036 is explicitly accepted only for exactly
one active server process, worker and backend; any HA/scaling/topology change
reopens the blocker. A 72-hour post-rollout observation has not elapsed.
Packaging unit checks do not claim an actual MSI install/repair drill, and
HTTP facade replay checks do not claim agent ACK/crash replay acceptance.
The older checkpoints below are historical and superseded by this rollout.


Latest acceptance checkpoint (2026-09-27 10:20 UTC): exact candidate
`fbf415f96c11d28508bca7df43b502c31dbf5997` passed full CI run 36310079198,
all 18 required layers and the accepted immutable web bundle. Staging installed
that candidate at schema 145; its PostgreSQL backup and actual isolated restore
passed. Existing Windows 3.2.75 agent diagnostic completed successfully through
the actual browser, Helpdesk facade and strict HTTPS Endpoint API (T-000029;
safe diagnostic_v1 result available). The requester confirmed the solution and
the DB audit found no duplicate events/messages or high/critical integrity
events. A separate T-000030 completed the same business cycle during actual
Endpoint unavailability; its browser had no console/page/HTTP errors and real
WSS frames. The temporary outage override was removed and synthetic actors
disabled. Detailed redacted receipts are in artifacts/staging-fbf-*.

The browser correction is merged and remotely verified on
`codex/helpdesk-process-model` at
`8c4b35fc469b50af3f01caeffed53e8e2179c6f2`; its Git tree equals the tested
candidate tree. This does not grant the merge SHA exact-SHA production CI.
DNS now resolves helpdesk.sosnadmin.local to 192.168.100.19. Production remains
on its previous release, with its historical insecure bootstrap profile and
HTTP-only Helpdesk Nginx site; secure configuration/TLS preparation is not a
deployment claim.

Remaining release work: finish current-revision historical risk dispositions,
before issuing an accepted manifest. The user explicitly accepted SCALE-036
as open/nonblocking only for exactly one server process, one worker and one
backend. HA/active-active/multiple workers/scaling remain prohibited. The
production evidence gate now rejects missing or unsupported staging/production
topology and records the accepted target topology in the immutable manifest.
Eighteen new regression cases failed before implementation; 42 release policy
tests now pass. This is a release gate, not a continuous runtime ownership
monitor or an HA correctness claim. Freeze a new SHA, require exact-SHA full
CI and renew staging acceptance before production. Then use the
canonical independent Helpdesk production release/configuration procedure,
verified production backup/recovery and HTTPS/WSS/business/Windows checks.

Scenario A checklist remains partial: the fresh cases proved support messages,
requester visibility and confirmed closure, but a separate requester reply
followed by support visibility (steps 9/10) still needs final-candidate evidence.
Do not promote the whole business smoke from these partial receipts alone.
Pinned Endpoint packaging/updater regressions: 52 passed locally; this is not
an actual MSI install/repair/upgrade claim. After validation, Helpdesk staging
and Endpoint staging API/worker are stopped; Windows agent is Running with its
original protected production enrollment restored. The scoped single-instance
risk disposition is explicitly approved and recorded in the historical
registry; changing topology automatically fails the release gate again.
No database ownership guard or runtime HA mechanism has been implemented.

Windows live diagnostic follow-up: the existing Windows 3.2.75 staging agent
is enrolled to the supported Endpoint provider. T-000028 mapping verification
returned 200, but the browser run returned 400: the client omitted the required
caller idempotency key. Separately, the empty Endpoint parameter schema exposed
an erroneous `type` input. The UI now retains actor/ticket-scoped intent keys
across uncertain responses and reloads, clears only the accepted key, and
renders no fields for empty object schemas. Both regressions failed before the
fix; 17 diagnostic tests, production web build and workspace verification pass.
No schema or provider contract change is required. This follow-up invalidates
the previous frozen candidate for final acceptance: new exact-SHA CI, staging
Windows completion and release evidence remain required. Production is not yet
deployed; the existing multi-instance blocker remains open.

Server-event retry races: two real PostgreSQL cases pass in 552.75 seconds.
Both retries complete a negative preliminary SELECT before insertion; the
existing revision-132 indexes still preserve one event for event_id and
message_id. The temporary role/database/tunnel were removed. This closes the
concurrency evidence gap locally; exact final-SHA CI acceptance remains required.

Diagnostic actor length: a real isolated PostgreSQL regression on revision
144 failed with StringDataRightTruncationError for a valid 100-character
support login. The facade stores the login in a 36-character diagnostic
session column. Revision 145 and the ORM widen that column to 100 without
truncating attribution or changing authorization. Fresh-migration PostgreSQL
verification passes all three cases in 590.02 seconds, including both existing
durability cases; temporary role/database/tunnel cleanup was verified.
Push CI for 3317ec678e866c1ce0fcd8b50eff967cb2400d30 was strictly accepted
across 18 layers. Its reviewed historical-risk dispositions are 24 verified,
nine open and three unverified; full release acceptance remains blocked.

Endpoint operation durability follow-up: two new PostgreSQL regressions pass
in 563.45 seconds. A failure after local link insertion rolls back operation,
diagnostic session/step and link before any remote request. A simulated worker
exit after remote create leaves its committed lease and replay key; a separate
worker reclaims after expiry and reuses the same key. The provider is a stub
implementing the published idempotency contract, so this does not prove real
Endpoint/Windows delivery. Temporary role/database/tunnel cleanup was verified;
Helpdesk staging was independently confirmed inactive with MainPID=0.
Current-source event/chat boundaries passed six checks, and the overlong-login
boundary passed one check. Real Windows and full release acceptance remain open.

Runtime database logging follow-up: a configured-engine regression reproduced
bound SQL parameter disclosure in formatted errors. The runtime engine now
enables hide_parameters=True. This changes error/log representation only;
SQL execution, pool options and transaction behavior remain unchanged.
The combined 43-case focused suite and workspace verifier pass. New exact-SHA
full CI remains required before release acceptance.

Security logging follow-up: a synthetic IntegrityError regression confirmed
that a UI-user creation conflict logged SQL parameters including password_hash.
The repository now emits a constant conflict message after rollback and raises
the existing ValueError without displaying the underlying exception chain.
Duplicate-login refusal and authorization behavior are unchanged. The combined
39-case focused suite and workspace verifier pass. New exact-SHA CI is required
before release acceptance.

CONSENT-021 current-boundary follow-up: failed operation transitions were
ignored for approval/denial (two unit failures). Missing/changed subjects were
also silently accepted (six further unit failures). The service now raises
safe OPERATION_STATE_CONFLICT/409; the browser handler rolls back the decision
and ticket event. Eleven consent unit cases and the combined 38-case suite
pass. The real PostgreSQL CAS-conflict/retry suite passed two cases in 556.84
seconds after correcting an oversized fixture device ID to a UUID. The initial
fixture failure is retained separately. Both runs verified temporary-role
absence and zero residual owned databases. Full new-SHA CI/live/risk acceptance
remains pending; no Endpoint configuration or production operation changed.

ACCOUNT-033 compatibility follow-up: CI 36288251203 for 535ab028 failed
two existing unregistered-requester emergency/profile-optional cases. The
correction keeps an authenticated actor with no resolved person and no
person claim unlinked. A new unit case failed before the fix; the focused
identity/initialization/idempotency suite passes 27 cases. Five real
PostgreSQL cases passed in 637.01 seconds, covering both failing controls
and foreign-ID/unavailable/retry regressions. Temporary role absence and
zero residual owned databases were verified. New full CI/live/risk proof
remains pending; the previous red CI artifact is preserved, not accepted.

ACCOUNT-033 current-boundary repro: legacy create with a forged
browser_no_device person ID persisted a foreign requester and emitted a Customer
History event. The two-case isolated run had one pass/one fail in 544.32 seconds;
temporary role cleanup was verified. The working-copy fix verifies server
identity before assigning any requester/person/context fields, rejects mismatch
with rollback/403 and converts identity lookup failure to typed rollback/503.
Seven new no-DB cases initially failed; the combined 26-case suite now passes.
Three direct create-flow fixtures now supply real verified UI-login identities.
Seven expanded PostgreSQL cases, including history, unavailable/retry and normal
requester/on-behalf controls, passed in 667.59 seconds; temporary role cleanup
was verified. New exact-SHA CI/live proof remains open.

CREATE-011 was published as f5f85ecc5b8c5dd4adabf20f77ac727c1312b1aa.
Its first full CI failed at the no-DB harness test's historical 169-table count;
migration 144 correctly adds table 170. The focused cleanup/idempotency suite
passes 57 cases after updating count/order and asserting web_support coverage.
Local full no-DB coverage had 838 passes and one separate guard failure caused
by an ignored old pc_agent/dist build; no pc_agent Python source is tracked.
The clean CI guard passed before the cleanup-count failure. Preserve that
local build and the guard; do not report the local full run as passing.
Follow-up c68bbaec0877c4cab7ec4790a05c5ae7a2a52f37 passed full exact-SHA CI:
18 effective layers and all 25 idempotency cases passed in the downloaded,
strictly validated artifact. The identity correction above requires its own
new exact-SHA CI; live acceptance and full risk closure remain open.

CREATE-011 working-copy implementation adds actor/key/payload hashes and a
ticket link through forward migration 144. The canonical requester POST now
requires an Idempotency-Key, reserves it in the ticket transaction, rechecks
current ticket access on replay and rejects changed bodies/deleted-ticket
tombstones. The browser persists account/intent-scoped pending keys through
failure and refresh; a conflict allows an explicit separate intent. Initial
PostgreSQL coverage passed eight cases in 688.17 seconds with fresh migrations
and verified temporary database/role/tunnel cleanup. That run used the earlier
optional-header wrapper; mandatory-key validation and removal of the redundant
wrapper followed it. Twenty-five focused no-DB checks, 39 frontend checks,
TypeScript/build and all 19 requester Chromium fixture cases pass. The expanded
PostgreSQL run completed with 18 passes and one incorrect test expectation:
the form/device preflight legitimately returns 403, not 400. Only that test
expectation changed; its two parameter cases then passed in a fresh isolated
database in 549.35 seconds, covering all 19 selected cases across the runs.
Temporary role cleanup was verified after both runs. Final exact-SHA CI and
live staging acceptance are still required; this is not risk closure.

HISTORY-023 was reproduced during CREATE-011 authorization preparation:
`RequesterIdentityResolver.get_ticket` searched only the latest 300 tickets.
The working-copy correction shares the existing access predicate with a direct
ID/code query. Three no-DB regressions reproduced the bounded lookup and now
pass; the 21-case lookup/reference suite passes. Two isolated PostgreSQL checks
passed in 537.96 seconds: an old ticket after 301 newer requests and
neutral/legacy authorization, including revoked active identity. Temporary
database/role/tunnel cleanup was verified. The published HISTORY-023 commit
`5a02c89be3a7f9d905db26786542f15bc1be5dc1` passed full exact-SHA CI with 18
effective layers and all five lookup cases. CREATE-011 implementation is
described above; this prerequisite alone does not close that risk.

Latest live checkpoint (2026-09-27; historical for subsequent changes): candidate
`4536db17a341a8d3d6f03af61017b95349c4f47c` passed full exact-SHA CI,
canonical staging installation, backup/restore and requester/support core
cycles T-000017/T-000018, including a real Endpoint adapter outage. Temporary
overrides were removed, synthetic accounts disabled and Helpdesk staging stopped.
This proves core behavior only; full Windows integration and risk closure remain
incomplete. The original June 25 audit was recovered and all 36 retained risk
definitions mapped. CREATE-012 was reproduced on that candidate: mandatory
routing/SLA/OLA exceptions were swallowed. The working-copy fix now returns a
safe 503 after transaction rollback. Unit regressions and eight isolated
PostgreSQL API checks passed; temporary test database/role cleanup was verified.
TEST-040 requester fixtures now follow valid closure states; all 17 browser
fixture scenarios passed. Earlier CI/live evidence does not accept a subsequent SHA.

The separate public-create route also reproduced CREATE-012/CREATE-013:
required initialization errors were swallowed and token issuance followed the
ticket commit. The next bounded fix issues the public session and constructs
the response in the caller's transaction. Five unit regressions failed before
the correction; six isolated PostgreSQL checks passed afterward, including
rollback after session insertion/serialization and successful public authorization.
Temporary test database/role/tunnel cleanup was verified.

SUPPORT-025 command-center/summary failure regressions reproduced false 200
empty responses; the bounded fix returns safe 503 and shows unavailable UI
states instead of empty-task/zero-summary claims. A refetch failure preserves
cached tasks with a warning. Twelve server checks, nine component checks,
TypeScript/build and a controlled real-browser degradation scenario passed.
SUPPORT-026 malformed `limit` is fixed for support queue/summary; other
historically listed handlers still need current-condition verification.

WORKFLOW-016/017 were reproduced in the current handlers: take-in-work ignored
assignment rejection and queue mutations swallowed required OLA failures.
The bounded correction rolls back these mutations before a safe error response;
mass queue changes preserve earlier successful items and roll back the failed
item. Eleven HTTP regressions failed before the fix; the focused no-DB suite
passed afterward. Fifteen isolated PostgreSQL checks passed: failure leaves
status, assignment, queue, timers and events unchanged; a mixed mass action
keeps the earlier successful item. Normal status/queue controls also passed.
Temporary database/role/tunnel cleanup was verified. Published b9cb055 passed
all 18 full CI layers, but these newer workflow changes still require their
own exact-SHA CI and live acceptance.

CREATE-014 was reproduced with two cases: a display name alone satisfied
emergency `contact_required`. Preview/create share the corrected check; seven
focused contact regressions passed, preserving profile phone/e-mail and
explicit contact fields. This is not proof of contact deliverability or live
acceptance. The combined focused no-DB suite passed all 22 checks.

WORKFLOW-015 was reproduced: a stale `from_status` reached policy execution.
The working-copy correction locks/refreshes the row before side effects and
maps stale explicit transitions to a safe 409. Automatic reply transitions
choose their target under the lock and skip unavailable/duplicate fallbacks.
Review also identified `autoflush=False`; locked reads now explicitly flush
pending same-transaction writes before refresh. Twenty-six focused no-DB checks
passed. The expanded isolated PostgreSQL run passed six checks: competing
different/same-target transitions have one winner and one status event, a
pending assignment survives with autoflush disabled, and normal reply, wait
ledger and quality-reopen controls succeed. Temporary database/role/tunnel
cleanup was verified. All 36 original conditions are now preserved in the
historical registry with the audit hash/line provenance and unchanged statuses.
No current-SHA release acceptance is claimed from these focused results.

Windows integration is independently blocked: Endpoint staging release
`1c96bdc18bc05fc7730435d12da730b8bbb42502` differs from the verified locked
provider `abdd5c7ef596bc54277e74ca96cc929a43e07049`, and the Windows test VM is
currently connected to production Endpoint. See the runbook's unresolved staging
provider boundary. Endpoint remains unchanged; no production acceptance was run.

Production Readiness v1 baseline:
`f2ad220f04e72a86eff00ea13f59a32dcd615b42`

Branch: `codex/helpdesk-production-readiness-v1`. Full exact-SHA CI and live
staging gates are required. See the active implementation checklist below.
Prior cutover evidence is historical and does not waive readiness gates.

# Historical: 2026-09-03 Helpdesk / Endpoint legacy cutover

## Goal

Complete the cross-repository cutover in
`2026-09-03-helpdesk-endpoint-legacy-cutover-plan.md`: Endpoint Platform is
the only endpoint-agent control plane; Helpdesk retains ticket/process and
browser UI responsibilities only.

## Scope and constraints

- Execute the E1–E4 and H1–H5 atomic release train, preserving the Endpoint
  headless runtime and the managed Remote Assist module source.
- Keep the legacy Helpdesk schema as non-runtime historical residue; no
  destructive schema drops or automatic downgrades.
- Produce exact-SHA, contract-digest, package-digest, targeted-test and
  real-agent release evidence.  The historical full suite is intentionally
  not a gate.
- Existing user changes outside this isolated worktree are out of scope.

## Current state

- The accepted Helpdesk baseline is
  `origin/codex/helpdesk-process-model` at
  `a5f1d2311406f6565460aa31cc9708d469479601`. It includes both the plan
  baseline and the required UI-removal commit
  `e88022956e4670278d151d0af1238f806b1a231a`.
- The isolated integration branch is `codex/legacy-cutover-integration`.
  It has not been merged or pushed. Its current fixes remove stale admin
  rollout metadata, align the browser capability test, make parallel-layer
  completion ordering deterministic, clean `registry_person_identities` in
  the `registry_access` test profile, and project primary-device presence
  through the supplied state provider with a safe `unknown` fallback. It also
  physically removes the legacy local `run_tool`/GUI-agent debug surfaces,
  `/ws_ui_test`, and the local UIA agent harness; those absences are guarded
  by `test_endpoint_diagnostic_cutover_guards.py`.
- A user-authorized full CI diagnostic run is still executing on frozen
  commit `5cee2bd2ecdbaf2a6a8c4acf33162aab644aa2b9`. It predates the two
  latest cleanup/presence fixes and is therefore evidence for further
  diagnosis, not release acceptance for the current branch.
- The current Helpdesk lock was verified against the clean Endpoint `main`
  checkout at `22060e2bd3eae9fff874a64d01d80d18be9ff576`: the raw Git-blob
  OpenAPI SHA-256 is `2982924427c731b83cfbd203e2fc86533c6e7b0fb4ec234cacd2d96f838fc04f`.
  Windows checkout CRLF conversion must not be used as contract-digest
  evidence.
- The local Helpdesk deletion gate passed on the integration worktree:
  45 no-DB cutover/route/boundary/resolver/static-page tests are green;
  `python -m compileall -q server scripts`, `npm --prefix webapp run build`,
  and `python scripts/verify_workspace.py --workspace .` are green. Static
  legacy matches are limited to retained migration history and
  negative-test/audit assertions; active runtime imports are absent.
- The Endpoint `main` cancel-contract check is green locally: 189 contract
  and operation-route tests passed, generated contract artifacts are current,
  and `python -m compileall -q endpoint_contracts endpoint_server pc_agent`
  passed. This is local contract evidence only; it does not substitute for
  immutable package or real-agent canary acceptance.
- The Endpoint headless-boundary subset also passed with a JUnit result of
  59 tests, zero failures, errors, or skips. It covers the excluded GUI,
  Helpdesk client and legacy WebSocket surfaces alongside the supported
  headless lifecycle and verification entrypoints.
- The current local ALT package subset produced 104 passes and 14 expected
  platform skips (POSIX ownership/FIFO checks, Linux assembly/harness, and
  RPM inspection). The obsolete plan reference
  `pc_agent/tests/test_linux_release_bundle.py` is absent; its current
  coverage is in `tests/build/test_linux_headless_artifact.py`,
  `tests/deploy/test_alt_agent_bundle_install.py`, and
  `tests/packaging/test_alt_rpm_contract.py`. The skipped checks remain
  required on the approved ALT worker before release acceptance.
- The Endpoint Windows package/runtime test directory passed locally with 128
  tests and zero failures, errors, or skips. The required dedicated-VM MSI
  installation, service, reconnect and rollback canary is still outstanding.
- Immutable package bytes have now been independently verified without an
  installation: the staging ALT RPM built from
  `572f3a0249bd4a49035cc97177279fbbf1e90068` is
  `endpoint-agent-3.2.38-alt3.x86_64.rpm` with SHA-256
  `78abe5ecf63fe594aef2eddd4b25657236ff5231413d7996bbb8d9ebd541950c`;
  `rpm -K`, metadata and the forbidden legacy-payload scan are green. The
  locally retained `EndpointAgent-3.2.38-x64.msi` has SHA-256
  `1b377298939121c5e669d90ad91606a627ff073e5ac1bfc0bd0bbe82ad7c4b90`,
  matching its sidecar's same source revision and initial-runtime tree hash.
  Neither package was installed or published by this verification.
- A read-only preflight on the approved ALT staging host confirmed that
  `endpoint-agent.service` is active but none of
  `ENDPOINT_AGENT_DEPLOYMENT_ENVIRONMENT`, `CANARY_ENVIRONMENT`, or
  `CANARY_APPROVED` is configured. The marker-bound staging canary therefore
  remains fail-closed; no remote configuration, service, or test data was
  changed.

## Next steps

1. Let the frozen CI run finish and use its exact tracebacks to identify any
   remaining defects; rerun only the relevant targeted DB layers on the
   current commit after the parent-owned tunnel is free.
2. Reconcile the prepared Endpoint cancel/headless release train with the
   final Helpdesk contract lock, generated artifacts and targeted gates.
3. Do not merge either integration branch until targeted gates, package
   evidence and the approved real-agent canaries satisfy the cutover plan.

# Helpdesk Bug Remediation and Live Detection Master Plan

## 2026-09-27 Production Readiness v1 — active

Production Readiness v1 baseline:
`f2ad220f04e72a86eff00ea13f59a32dcd615b42`

- Branch: `codex/helpdesk-production-readiness-v1`, based on fetched remote
  default `codex/helpdesk-process-model`. Earlier accepted/deployed revisions
  below are historical evidence, not the current RC identity.
- Scope: release/security/database/CI/live staging readiness only. Endpoint is
  read-only. Windows live acceptance only; ALT acceptance is excluded.
- Production deployment is not authorized by this task. Stop after verified
  staging acceptance and frozen RC evidence; no readiness claim with open gates.
- Preserve the user's pre-existing `AGENTS.md` edits outside task commits.

### Repo-grounded implementation plan

1. Baseline/current audit: update this section and extend current-head risk
   validation around `known_bug_registry.current_head.json`; historical
   fixed-local records never become current verification automatically.
2. Provider lock: establish deployed Endpoint SHA using read-only release
   evidence, then update `integration/endpoint_contract.lock.json` and run
   `scripts/validate_endpoint_contract_lock.py` plus adapter/contract/boundary
   suites. Unknown provider SHA blocks integration acceptance.
3. Security: update `deploy/helpdesk/helpdesk.env.example`, Nginx template,
   host installer and `server/config.py`; add a secret-free standalone config
   preflight with regression tests for cookie/HTTP/bind/proxy policy failures.
4. Database: add verified custom-format backup and isolated restore drill to
   existing deployment/migration entrypoints; reuse Tech Panel marker paths.
   Test backup/verification failure prevents migration and restore cleanup.
5. CI/artifacts: extend canonical workflow and
   `scripts/release_candidate_preflight.py`; require full exact-SHA CI,
   exact-SHA web bundle, lock, current risk audit and required staging evidence.
6. Live staging: real requester/support browser lifecycle, persisted database
   and audit checks using synthetic accounts, then safe Windows Endpoint
   diagnostic and reversible dependency degradation. No mocks replace gates.
7. Operations/manifest/runbook: reuse `server/tech/snapshot.py`, existing release
   and backup/restore/smoke markers; document strict TLS, production commands,
   code/schema/restore rollback and the post-deploy 72-hour pilot checklist.

Migration impact: requester idempotency requires revision 144; preserving full
diagnostic actor logins requires revision 145. Neither migration removes data.
The consent-delivery investigation below requires no further schema change. Deployment
impact: unsafe configuration and missing backup/evidence become fatal before
migration. Rollback impact: symlink rollback is insufficient after incompatible
schema changes; no automatic Alembic downgrade or Endpoint rollback.

### Consent delivery follow-up — current investigation

- Frozen checkpoint `8989e7afdb67b02e7bc0364e17e861346a3e1158` passed exact-SHA
  full CI, canonical staging install/schema 145, backup/isolated restore, real
  requester/support core, core continuity during an adapter outage and Tech Panel
  identity/DB/dependency checks. It is still not production-ready: Windows
  staging alignment and blocking/unverified risks remain open. Staging is stopped.
- Real isolated PostgreSQL reproduced a reconciler claim before consent approval.
  A separate no-DB regression reproduced approval of a historical orphan. The
  second PostgreSQL case initially failed on a missing required fixture field;
  that fixture failure is preserved separately and is not behavioral evidence.
- The correction limits claims to delivery/cancellation states and requires a
  pending durable Endpoint link before approval. Denial, requester scope, event
  rollback and Endpoint-only execution remain intact. Boundary docs are updated.
  Focused no-DB checks passed (38 tests), as did all four real PostgreSQL
  recovery/orphan/CAS cases (616.64 seconds). Waiting/denied/unknown states were
  not claimed. Temporary test role, databases and tunnel were removed. The
  provider is modeled here; this is not actual Windows/agent acceptance.
  A clean tracked snapshot with current consent files also passed all cutover
  guards and consent no-DB cases (28 tests); ignored local packaging is preserved.
- A changed candidate must obtain its own exact-SHA CI and current staging proof;
  the accepted 8989 artifacts remain evidence for 8989 only. Endpoint is unchanged.

### Initial verified checkpoint

- Fetched default baseline: `f2ad220f04e72a86eff00ea13f59a32dcd615b42`.
- GitNexus group status: all three indexes/contracts current, zero commits
  behind, no missing repositories. No manual sync was run.
- Open PR #2 is historical documentation, not readiness implementation.
- Last GitHub evidence is Endpoint contract workflow only; full CI is unproven.
- Existing bug registry is historical (`fd232bb9...`), with P0/P1 live evidence
  pending. Current readiness is **BLOCKED**, not production-ready.
- Production provider identity, live staging, TLS, backup/restore, Windows
  operation and degraded acceptance remain unverified.
- `scripts/production_readiness_audit.py --refresh-source
  known_bug_registry.current_head.json --commit <full-sha> --audit
  artifacts/release/<full-sha>/risk-audit.json` creates a current-SHA audit with
  all historical dispositions unverified. Re-run without `--refresh-source`
  after supplying actual verification; unresolved high-priority records fail.
- Workspace scanner now prunes dependency trees and other worktrees before
  descent. Focused scanner/risk tests and scoped workspace verification passed.

### Provider re-lock checkpoint

- Production symlink (read-only SSH) points to
  `/opt/endpoint-platform/releases/endpoint-platform-abdd5c7ef596`.
- Exact revision: `abdd5c7ef596bc54277e74ca96cc929a43e07049`. Compared 207
  deployed source/config files with raw Git blobs: zero digest mismatches.
  53 non-shipped tool/test/frontend-source files were absent; no manifest or
  Git metadata was present in the deployed immutable release.
- Raw canonical OpenAPI SHA-256:
  `cc1a47c8343091c0bef5942e9a0f5254f7d73cf07d02063ae24a21eedf34d8f1`.
- Exact clean provider checkout validator passed. Consumer contract/HTTP/port/
  cutover no-DB run: 66 passed, 1 failed. The failed boundary test scans local
  ignored `pc_agent/dist` packaging dependencies left from an older checkout;
  this is not green boundary acceptance. Re-run from clean committed source.
- DB/provider/Gateway/Windows/live compatibility remains required; re-lock
  alone is not integration acceptance or production readiness.
- Staging SSH and Windows VM SSH work. Staging sudo requires runtime approval
  credentials; no password was retrieved, stored or printed. Live DB gates
  are pending the approved secret channel.

### Security checkpoint

- Production env/Nginx templates now require HTTPS/WSS, secure cookie, explicit
  loopback and proxy policy. Host installer validates external root-owned TLS
  material. Runtime/deploy/systemd share the same transport policy.
- 31 config/deployment tests, 7 no-DB auth tests, example-env validation and
  scoped workspace verification passed. These are local checks, not deployed
  TLS/browser acceptance; production configuration was not changed.

### Database safety checkpoint

- Production migration entrypoint now requires exact packaged release identity
  and verified custom backup before Alembic. Deployment stops Helpdesk writers;
  failed backup/migration leaves them stopped for reviewed recovery.
- Restore helper validates backup digest/size, uses a random isolated database,
  compares restored pre-migration schema revision and cleans up on failure.
- 22 focused backup/migration/deployment tests and workspace verification
  passed. Real PostgreSQL backup/restore, migration and fresh-DB CI remain
  unverified pending runtime credentials. No production migration ran.

### CI and artifact checkpoint

- Added `Helpdesk production readiness` workflow and mandatory aggregate job
  `production-readiness` (GitHub branch protection requires administrator action).
  It runs canonical full CI and the existing real provider contract workflow.
- Production preflight requires exact-SHA full CI/web metadata, secure config,
  current risk audit, clean pinned provider and actual staging acceptance.
  Only successful validation creates an immutable bounded release manifest.
- Web typecheck/production build passed locally using Node 24.15.0 and
  pnpm 10.33.0. Build metadata/digest checks are covered by focused tests.
  Full CI/live staging evidence is not yet green.
- Clean-checkout full CI on `933c9669...` passed workspace/build, 454 web unit
  tests, fixture E2E and inventory/risk/contamination/coverage/mutation audits.
  Scripts collection failed on the `server` module/package name collision.
  Shared policy moved to `shared/production_security.py`; full scripts layer
  must be rerun. Clean-checkout Endpoint boundary run: 67 passed.
- After moving shared policy, full local scripts collection passed: 241 tests.
  This does not turn the earlier exact-SHA full CI red artifact green.
- Real staging HTTPS login page rendered in Playwright; console 0 errors and
  0 warnings. Synthetic login, ticket flow and Windows/degraded flow remain
  unverified; no runtime credentials are present in the named environment inputs.
- No services were started/restarted/stopped during read-only discovery; the
  pre-existing active staging service was left in its original state.
- Remaining implementation/live gates: full business-flow automation, real
  backup/restore and provider acceptance, Windows/degraded acceptance, actual
  operational release/schema/dependency evidence and final green manifest.
  No accepted release manifest has been fabricated.

## 2026-08-31 Staging secure admin-session access

- **Goal:** make the isolated Helpdesk staging admin login usable through the
  approved HTTPS origin without weakening the `httpOnly; Secure` session
  cookie, and prevent direct HTTP access from misleading future operators.
- **Scope:** only `osn-admin@192.168.101.118` staging. Production and the
  Endpoint repository are excluded.
- **Status:** `root-cause-confirmed` (auth/account-session + deployment
  configuration).
- **Evidence:** the staging login endpoint accepted the account and created a
  UI session, while browser access through `http://192.168.101.118:8666`
  returned to the login form. The TLS listener presents a certificate for
  `helpdesk-staging.sosnadmin.local`; the hostname resolves to the staging
  host and the same login page opens there with no browser console errors.
  The direct `:8666` listener remains externally reachable even though the
  versioned deployment template requires loopback application binding behind
  Nginx.
- **Root cause:** a secure cookie cannot be persisted by a browser on the
  direct HTTP origin. This is not a credential failure and must not be
  “fixed” by disabling secure cookies.
- **Fix policy:** keep secure cookies enabled; publish the HTTPS FQDN as the
  sole admin origin, bind the application port to loopback, and have the
  staging Nginx vhost redirect HTTP to the FQDN. Apply the environment/unit/
  Nginx change only through the reviewed staging release procedure, then
  verify a fresh browser login and the absence of an external `:8666`
  listener. Root privilege is currently required for those staging resources.
- **Blocking impact:** this blocks the real locked Endpoint acceptance and
  ALT/Windows staging canaries because the required admin browser session
  cannot be established safely through the current direct HTTP endpoint.
- **Latest verification:** the administrator successfully opened the legacy
  admin workspace through the HTTPS FQDN. The Endpoint Recipes screen then
  returned the fail-closed state
  `endpoint_module_external_service_token_missing`; no Endpoint recipe
  operation was created and no canary was started.
- **Next steps:** obtain approved staging-operator execution for the
  environment/systemd/Nginx change and the temporary scoped Endpoint module
  credential/feature configuration, run the browser login regression through
  the HTTPS FQDN, then resume the locked acceptance and canary sequence.

## 2026-08-31 Product webapp staging cutover

- **Goal:** serve the product React `/app/admin` route from the immutable
  Helpdesk staging release, keeping `?legacy=1` only as a rollback escape.
- **Status:** `implementation-verified-locally`; the release archive now builds
  the bundle from an exact Git commit snapshot and packages it under
  `webapp/dist`, so dirty local files cannot diverge from the released server
  source.
- **Verification:** archive-layout regression plus exact-commit/dirty-worktree
  regression passed; static cutover handlers passed.
- **Remaining gate:** commit, push and reviewed staging deployment through
  `scripts/deploy_helpdesk_release.py`, followed by the configured cutover
  flags and a browser check at `/app/admin`. Deployment needs the approved
  staging-operator privilege; no manual staging patch is permitted.

## 2026-08-31 Fixture-builder release-gate baseline

- **Goal:** restore a truthful, executable critical-behavior fixture pack so
  the full CI release gate can validate its test references.
- **Scope:** Helpdesk test-data pack and its audit regression only; no runtime,
  route, database, Endpoint Platform, staging, or production change.
- **Root cause:** `critical_behavior_v1.json` still named five tests from the
  retired local Knowledge runtime and UI. The strict fixture audit failed on
  base `2d355954`, proving the defect predates the immutable webapp release.
- **Decision:** keep the product webapp release as separate PR #26 and replace
  the stale references with the current external-Knowledge boundary contract
  tests. The pack therefore validates fail-closed external-port behavior,
  removal of local lookup/fallback, and documented redacted historical
  projections instead of claiming a removed local Knowledge UI.
- **Verification:** targeted audit regression and strict fixture audit are
  green. Re-run the full isolated CI on the release PR after this separate
  baseline PR merges.

## 2026-08-28 Endpoint Read-only Capability Batch v2 — Helpdesk

- **Goal:** consume the Endpoint-owned versioned capability catalog through a fail-closed typed port, project only bounded capability-specific evidence, replace the Endpoint Recipe Workbench allowlist with the catalog, and freeze fully replaced legacy network-module rollouts only after real ALT and Windows acceptance.
- **Scope:** Helpdesk PR-HD1 (`codex/module-capability-projections-v2`), PR-HD2 (`codex/module-workbench-capability-catalog-v2`) and PR-HD3 (`codex/legacy-module-freeze-v1`). Endpoint Platform is read-only in this session; production is excluded.
- **Constraints:** Browser calls only Helpdesk BFF. No shared database/FK, DeviceOutbox, ToolService, Helpdesk WebSocket, legacy fallback, dual dispatch, raw service name, raw result, code, command, path, URL or credential may cross this boundary.
- **Decisions:** Closure PR #23 merged as `4fc93772`; all three Helpdesk branches start at that SHA. HD1/HD2 wait for Endpoint PR-EP1/EP2 contract merge SHA and an updated immutable lock. HD3 implementation/freeze waits for successful ALT and Windows canaries.
- **Current State:** HD1 is implemented locally against the immutable provider
  lock: `integration/endpoint_contract.lock.json` pins Endpoint
  `dcd2d5287fa53b7ae61d582344d231d7384599c9` and OpenAPI digest
  `dce611029f974a0442d0f04b7d4f54fa805b1e73f9831edf0f1f8c955a4a74b5`.
  Succeeded operation-detail projections require the provider-authoritative
  `expected_step_count` and complete zero-based child sequences. The
  fixed `GET /api/v1/module-capabilities` adapter accepts only the six locked,
  fail-closed DTO descriptors and the authenticated typed BFF is web-only
  (there is deliberately no `/api/admin/endpoint-modules/capabilities` alias).
  Its closed result projector writes `endpoint_module_result_snapshot_v2` while
  retaining existing v1 snapshots and historical evidence unchanged.
- **Next Steps:** execute HD2 against the typed BFF, followed by real
  acceptance, canaries and HD3. Do not enable endpoint execution before those
  separate gates.
- **Handoff:** preserve the fixed catalog route and provider lock; do not add a
  generic proxy, browser-to-Endpoint call, catalog mock, hardcoded capability
  authority, ToolService/DeviceOutbox/legacy-WebSocket fallback or dual dispatch.

## 2026-08-27 Module Platform Canary Closure v1

- **Goal:** close the staging-only Module Platform canary: merge the 15 Endpoint
  canary fixes into Endpoint `main`, harden Helpdesk reconciliation, deploy both
  mainlines, run one published ticket recipe, prove the exact cross-repository
  invariants, then restore flags and revoke the scoped service credential.
- **Scope:** Endpoint and Helpdesk staging only (`192.168.101.118`), with the
  designated ALT and Windows agents. Production `192.168.100.19` is excluded.
- **Constraints:** no direct Endpoint operation creation from the acceptance
  runner, no shared database/FK, no DeviceOutbox, ToolService, legacy WebSocket,
  dual dispatch, fallback, raw credential, or raw agent-output evidence.
- **Decisions:** retain newly deployed mainline releases after closure; rollback
  restores only temporary module flags and access. Credential revocation is
  verified before the root-only token file is removed. Evidence is redacted and
  copied from staging to the operator workstation outside Git.
- **Current State:** Endpoint `main` is now `59b1e7e` after a conflict-free
  merge of exactly 15 canary commits; full CI passed `1970 passed, 36 skipped`.
  Helpdesk lease/retry/monotonicity hardening and its focused suite (`30
  passed`) are ready. At the time of this historical canary record, its
  provider lock pinned that Endpoint SHA; it is not the current shared
  `integration/endpoint_contract.lock.json` value, which is recorded in the
  2026-08-28 HD1 state above. Local real-provider acceptance is fail-closed by
  its stale Windows `example.test` DB-tunnel setting and moves to isolated
  staging rather than using a fallback.
- **Next Steps:** merge Helpdesk hardening into its default mainline, deploy
  both verified SHAs to staging, then run the one ticket recipe and close the
  rollback, credential, backup, and acceptance-document gates.
- **Verification:** required commands and evidence schema are in
  `docs/superpowers/plans/2026-08-27-module-platform-canary-closure-v1.md`.
- **Handoff:** do not claim closure until the repeated reconciliation has zero
  delta, credential revocation is proven, and the off-host manifest digest is
  recorded in the final Helpdesk document.

## 2026-08-26 Endpoint Module Platform v1

- **Status:** Endpoint EP1 is complete locally: typed contracts, independent
  server/agent policy foundations, bounded agent primitives, a closed runtime
  registry, default-false feature gates and safe capability discovery
  projection. EP2 is now executable locally behind its default-false Endpoint
  gate: immutable published recipe versions expand only on Endpoint into
  durable parent/child operations; Gateway WSS delivers one typed primitive at
  a time, accepts safe typed child results, stops on failure, and expires every
  pending child at the parent deadline. HTTP pull never materializes these
  commands. No production flag, migration, deployment, or Helpdesk-native
  execution path has been enabled.
- **Goal:** move declarative module ownership/execution to Endpoint while
  retaining the legacy Workbench/runtime until explicitly migrated.
- **Constraints:** no Endpoint direct browser call, shared DB/FK, DeviceOutbox,
  ToolService, legacy WebSocket, dual dispatch, automatic fallback, arbitrary
  code, or production deployment.
- **Decisions:** Endpoint is canonical for recipe/module lifecycle and commands;
  Helpdesk is canonical for actors/tickets/facade/evidence. The exact boundary
  is `docs/segmentation/MODULE_PLATFORM_BOUNDARY.md`; legacy classifications
  live in `docs/segmentation/LEGACY_MODULE_MIGRATION_MATRIX.csv`.
- **Current Helpdesk boundary:** commits `4f1a82db` and `53e3041b` add a
  separate frozen `EndpointModulePort`, default-false composition and a typed
  HTTPS catalog/version/operation adapter. It does not retain recipes or use
  diagnostics, ToolService, DeviceOutbox, legacy WebSocket or an automatic
  fallback. Commits `71d4592c`, `4b49fe22` and `73606573` add the forward-only
  local operation-link schema and nullable-device facade exception; they have
  not been applied to any database. Revision `142` unifies that temporary
  staging schema into the established `EndpointOperationLink` lifecycle and
  removes the unused second table. The module reconciler remains default-off
  until both external port and explicit `ENDPOINT_MODULE_EXECUTION_MODE=endpoint`
  are set; it stores only safe completed results and creates one idempotent
  `endpoint.module.recipe` evidence record. The authorized Module Workbench
  BFF now exposes admin authoring/version lifecycle and support ticket-run
  routes through that port; it keeps the legacy Workbench separate, gives
  auditors metadata-only access, and creates the local facade using only the
  server-owned ticket mapping. The legacy Admin shell now has a separate
  `Endpoint recipes` subtab that builds only declarative allowlisted recipes
  and uses only the BFF; it does not expose `user_function_body` or any
  legacy module API. Real-browser and cross-repository acceptance remain
  pending.
- **Next steps:** complete Endpoint compatibility/lab-evidence wiring, then
  execute staged browser and real-agent acceptance for the already-wired
  Helpdesk reconciler, audit/ticket evidence projection, RBAC and browser
  workbench.
  Keep legacy paths isolated; no endpoint-native BFF fallback or dual dispatch
  is permitted.
- **Verification:** Helpdesk Windows acceptance is already in mainline at
  `62b734ddf5b65a9978524c1c0af31bdf9ad53d2d`. Endpoint contracts and server
  policy foundations passed `tests/contracts tests/operations` (335 passed,
  4 skipped) before Gateway contract expansion; the refreshed Gateway contract
  suite passed (280 passed). The current EP1 capability/configuration gate
  passed 391 tests with 1 skipped, and the agent-policy runtime/transport gate
  passed 49 tests. No Module Platform runtime or canary verification has run
  yet. The current Endpoint module Gateway/operation suites passed 40 tests;
  Gateway child-delivery/result/reconnect coverage passed separately. Full
  canary and Helpdesk browser verification remain pending. The new Helpdesk
  port/adapter boundary passed its targeted contract/HTTP suite (46 passed)
  and `python scripts/verify_workspace.py` completed locally without errors.

> For agentic workers: execute this plan task-by-task. Keep this file as the active source of truth, update it after each meaningful checkpoint, and store detailed proof under `artifacts/live/<run_id>/`.

## 2026-08-26 Endpoint Operations cross-platform real-agent acceptance

- **Status:** ALT and Windows real-agent staging canaries are accepted after
  rollback; the canonical Windows record is
  `docs/verification/WINDOWS_HEADLESS_AGENT_CANARY_ACCEPTANCE.md`.
- **Accepted transport boundary:** Endpoint Operations transport is accepted
  cross-platform for the bounded `context.diagnostic.collect` slice. The
  command reached agents only through the Endpoint Gateway WSS path; Helpdesk
  performed no legacy agent, `DeviceOutbox`, or `ToolService` dispatch.
- **Runtime facts:** the successful Windows diagnostic ran against Helpdesk
  `80ed96e79fad1fad80093c8107b44a9ba0addfe1`; post-canary strict-CA tooling is
  `b338b5886b1069bffc92edf4990b090fda5987c3`. Both canaries are staging-only
  evidence and do not authorize a production change.
- **Retained components:** the legacy agent runtime, legacy `/ws`,
  `DeviceOutbox`, and agent account-session paths remain. Their deletion is
  explicitly deferred until their individual cutover prerequisites are met.
- **Not completed:** consent migration, Remote Assist migration, legacy agent
  `/ws` deletion, `DeviceOutbox` deletion, and agent account-session deletion.
- **Next package:** typed read-only Endpoint capabilities; do not expand the
  operation/command scope before its separate contract and acceptance evidence.
- **Operator action:** encrypted off-host archive of the Windows protected
  evidence is pending. Record its archive SHA-256 outside Git before claiming
  evidence archival complete.

## 2026-08-20 Helpdesk co-hosting on Endpoint Platform production host

- **Status:** clean Helpdesk baseline deployed and running on 2026-08-20.
- **Goal:** deploy Helpdesk as an independent production service on
  `osn_admin@192.168.100.19`, next to (but isolated from) Endpoint Platform.
- **Confirmed decisions:** create a fresh Helpdesk PostgreSQL database and only
  a new administrator; migrate no Helpdesk data; do not register or preserve
  legacy agents; agents will use a future replacement auth/connection method.
  Keep Helpdesk and Endpoint as separate repositories, databases, service
  users, systemd units, release trees, runtime directories, and Nginx vhosts.
- **Endpoint contract:** use only the existing HTTPS Endpoint Operations API
  with an explicitly enabled feature and a separate scoped service identity.
  No direct Endpoint import or database access is permitted.
- **Bootstrap constraint:** the initial IP-only access is temporary and
  network-restricted. The final production gate requires a DNS name, trusted
  TLS certificate, `REQUIRE_HTTPS=true`, and `REQUIRE_WSS=true`; insecure
  transport is never the steady-state design.
- **Deployment record:** immutable release
  `fb203b6026dde49a2673f0126a7a727d597aebe4` is active at
  `/opt/helpdesk/current`; Alembic revision is `136`. The dedicated
  `helpdesk-server.service` and `helpdesk-control.service` are enabled and
  active, bind only to loopback, and are exposed through the restricted
  temporary IP bootstrap at `http://192.168.100.19:8080`. The fresh database
  has no UI users or devices; no legacy Helpdesk data or agents were copied.
- **Verification record:** focused deployment tests (19 passed), documentation
  link check, Helpdesk API/Nginx smoke (200), Nginx syntax, service enablement
  and Endpoint service health passed. `verify_workspace.py` did not complete
  in the available local run and is not counted as a passing gate.
- **Remaining gates:** create the initial administrator, obtain the separate
  Endpoint service credential and acceptance, then complete FQDN/TLS/secure
  cookie cutover and the new agent connection/auth rollout.

## 2026-08-17 Helpdesk Endpoint Integration v1

- **Status:** implementation completed locally and merged into
  `codex/helpdesk-process-model`. Focused endpoint, standard PostgreSQL and
  workspace-verifier gates passed; no deployment or production migration ran.
  The full CI baseline remains blocked by four pre-existing non-Endpoint
  DB-cleanup-profile audit gaps.
- **Goal:** implement exactly one external vertical slice,
  `endpoint.context.diagnostic.collect` → Endpoint
  `context.diagnostic.collect`, without Helpdesk WebSocket/DeviceOutbox agent
  dispatch.
- **Starting baseline:** `062703ab291645123e01d3732939c1dfebe43339` on
  `codex/helpdesk-process-model`; current Alembic head at planning time is
  `134`.
- **Decisions:** Endpoint Platform owns endpoint-agent operations/control
  plane; Helpdesk owns tickets, diagnostics, UI, local facade `Operation`, and
  safe evidence. Endpoint refs/correlation are opaque and non-authorizing; no
  cross-service imports, DB FK, automatic fallback, or dual dispatch.
- **Default state:** Endpoint unavailable and diagnostic execution `legacy`.
  `endpoint` mode is explicit, fail-closed, asynchronous, and reconciles
  external operations into safe local diagnostics.
- **Constraints:** legacy agent `/ws`, `DeviceOutbox`, runtime/tables and
  `/ws_ui` remain. No production deployment/migration, service credential
  change, test-agent action or agent rollout is in scope.
- **Next steps:** before any deployment, rehearse migrations on the release
  candidate and validate the four allowed HTTPS Endpoint API routes against an
  integration fixture or approved Endpoint Platform environment. Keep
  `docs/segmentation/HELPDESK_ENDPOINT_RESIDUAL_INVENTORY.md` current whenever
  a residual component's ownership changes.
- **Verification gate:** Endpoint contract/adapter/device/link/reconciler/
  provider/cutover guard tests; affected diagnostics/operations/ticket/API/
  `/ws_ui`/migration suites; workspace verifier and diff check; browser
  evidence plus webapp build only if the UI changes.
- **Handoff:** accepted boundary:
  `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`; approved design:
  `docs/superpowers/specs/2026-08-17-helpdesk-endpoint-integration-design.md`.

## 2026-08-09 Helpdesk segmentation milestone (PR-0 / PR-1 / PR-6)

- **Completed locally:** ownership ADR/API target, neutral domain ports, AST import guard, ticket/support/problem/Registry detachment, and removal of the in-process Knowledge runtime, routes, UI, agent client, local AI runtime, content packs and active ORM mappings.
- **Current behavior:** `KnowledgePort` is explicitly unavailable (`knowledge_unavailable`) with no local DB/HTTP fallback; removed local Knowledge paths return normal `404`; ticket creation, routing, support work and closure remain available.
- **Retained history:** all old Alembic migrations and physical Knowledge/AI tables, `ticket_kb_links` rows and sanitized legacy `knowledge_attempts` remain untouched and read-only. No schema migration, data deletion, deploy or remote mutation was run for this milestone.
- **Evidence:** focused port/import-boundary/ticket/support/problem/Registry/removed-route tests, Python compilation, default collection and webapp build are recorded in the task reports under `.superpowers/sdd/2026-08-09-helpdesk-segmentation-pr0-pr1-pr6/`. DB-backed subsets have a documented local timeout and are not claimed green.
- **Next gates:** PR-7 may add a versioned external Knowledge API adapter only after service/auth/scope/redaction acceptance. PR-11 may delete retained schema only after acceptance, with a separately reviewed forward-only migration, backup/rollback plan and no local fallback restoration.

## 2026-08-10 Registry retirement decision

- **Confirmed ownership:** `ui_users`, Helpdesk web sessions and RBAC remain
  Helpdesk-owned. Local `registry_*`, device-registration, account/pairing
  data and Registry-linked ticket/consent FKs are retirement targets only
  after a RegistryPort external cutover.
- **Required sequence:** PR-2 immutable refs/snapshots; PR-8 local adapter and
  import boundary; PR-9 external Registry API with shadow-read acceptance;
  PR-11 forward-only schema deletion with clone rehearsal, backup/restore
  rollback and a maintenance window. Alembic downgrade is explicitly excluded.
- **Design record:**
  `docs/superpowers/specs/2026-08-10-registry-retirement-design.md`.

## Goal

Build a reliable bug remediation and live detection loop for the helpdesk system. Already-known P0/P1 defects from the deep audit must be verified against current `HEAD`, fixed with regression coverage and real evidence, then the stabilized system can be used for broader live bug hunting.

The intended release state is:

- all known P0/P1 bugs are verified-fixed, verified-non-product, or explicitly accepted as release-blocking known limitations;
- every live bug found later is recorded, triaged, deduplicated and routed into a remediation wave before any fix work starts;
- all 17 critical behavior scenarios pass with exact-context live evidence;
- release gates reject shallow, stale, mismatched or missing proof.

## Current State

- **Status:** active master plan reset on 2026-06-26 after user review of the previous `PLANS.md` structure.
- **Branch at plan update:** `codex/helpdesk-process-model`.
- **Scope classification:** cross-cutting. The plan spans webapp, server APIs, PostgreSQL, Observer, Protocol V3/agent runtime, live tooling, CI and release gates.
- **Plan source:** rebuilt from the uploaded deep audit, live bug-detection plan, remediation/observer plan and the latest restructuring request.
- **Primary rule change:** broad live bug hunt is deferred until static-confirmed known P0/P1 defects are remediated or explicitly dispositioned.
- **Audit drift note:** the deep audit reviewed an older GitHub `HEAD`; Phase 0 must verify every deep-audit ID on the current local tree before code changes.
- **Release state:** not assumed green. Treat current release readiness as unknown until Phase 0 records exact commit, deployed commit, schema head, CI state, Observer baseline and live evidence readiness.
- **Latest remediation checkpoint, 2026-06-26:** Phase 1 code slices fixed `ID-001`, `ID-002`, `CLAIM-003`, `AGENT-AUTH-004`, `PAIR-005`, `SESSION-006`, `EVENT-007`, `EVENT-008`, `CHAT-009`, `CHAT-010`, `CLOSE-018`, `PUBLIC-AUTH-034`, `AUTH-029`, `ACCOUNT-033` and adjacent `AUTH-030` locally. Focused automated/no-DB regression checks and direct helper assertions are green where runnable, migration `132` is the Alembic head, and `known_bug_registry.current_head.json` records all 41 IDs. P0/P1 release disposition remains blocked until live/stand evidence is collected where required.

## Stop Conditions

Stop implementation or live execution and update this plan before continuing when any of these occurs:

- Broad live bug hunt is requested while any static-confirmed P0/P1 known bug is neither verified-fixed, verified-non-product, nor explicitly accepted as a release-blocking known limitation.
- Exact context is unknown: local commit, deployed commit, branch, schema head, environment or release run id cannot be proven.
- A run exposes cross-account access, cross-device access, public-token bypass, auth/session confusion, role confusion or unredacted secret leakage.
- A required evidence layer is missing for a P0/P1 fix or release-gate scenario.
- Browser/API/DB/Observer/agent evidence disagree on the same outcome.
- New active critical/high Observer events appear during a fix or live run.
- Data contamination invalidates a run marker, ticket marker, device marker or cleanup proof.
- Stand/deployment state is manually patched outside project release/deploy/runtime scripts.
- Multi-instance deployment is requested while process-local outbox/session delivery risks remain unresolved.

## Known Defect Registry

The deep audit IDs below are the initial known-defect registry. Current `HEAD` status is intentionally conservative until Phase 0 writes `known_bug_registry.current_head.json` with one of: `open`, `reproduced`, `not-reproduced`, `already-fixed`, `blocked`.

| Bug ID | Priority | Group | Current HEAD status | Fix status | Regression test | Verification | Release blocker |
|---|---:|---|---|---|---|---|---|
| `ID-001` | P0 | identity/account boundary | reproduced on current HEAD | fixed-local, live-evidence-pending | `test_requester_identity_does_not_link_by_unverified_email_alias`; `test_effective_identity_does_not_link_by_email_alias_without_ui_login` | focused pytest green; live/API/DB evidence missing | yes, until live evidence |
| `ID-002` | P0 | identity/account boundary | reproduced on current HEAD | fixed-local, live-evidence-pending | `test_ui_users_repo_rejects_case_variant_login` | focused pytest green; Alembic `130 -> 131` green; live evidence missing | yes, until live evidence |
| `CLAIM-003` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_requester_public_ticket_claim_is_single_winner_under_race` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `AGENT-AUTH-004` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-green | `test_handshake_rebind_keeps_token_on_original_device_when_fingerprint_mismatches`; `test_handshake_rebind_uses_expected_original_token_binding` | no-DB handshake pytest green; live/stand evidence missing | yes, until live evidence |
| `PAIR-005` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-green | `test_registration_pairing_pickup_waits_for_deliverable_session_before_consuming`; API contract updated in `test_registration_pairing_approval_surfaces_confirmed_binding_to_agent`; agent gate compatibility tests updated | no-DB pairing FSM pytest green; focused pc_agent pytest green; DB API pytest attempted but fixture hung locally; live/stand evidence missing | yes, until live evidence |
| `SESSION-006` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-partial | `test_approved_login_request_session_token_survives_worker_restart_until_first_poll`; `test_account_session_delivery_no_db.py` | direct helper assertions green; compile green; local pytest runner hung before result; live/stand evidence missing | yes, until live evidence |
| `EVENT-007` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ticket_events_repo_no_db.py::test_get_events_orders_timeline_by_created_at_before_agent_seq` | no-DB pytest/direct regression green; compile green; live/stand evidence missing | yes, until live evidence |
| `EVENT-008` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ticket_events_server_idempotency_unique_indexes_are_migrated`; `test_add_event_treats_server_idempotency_unique_conflicts_as_duplicates` | no-DB pytest green; Alembic head/history green; DB-backed migration contract hung locally | yes, until live evidence |
| `CHAT-009` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_support_send_message_rejects_unknown_visibility_before_db`; `test_chat_message_unknown_visibility_is_hidden_from_requester_timeline` | no-DB API/projection pytest green; DB-backed endpoint pytest hung locally; live/stand evidence missing | yes, until live evidence |
| `CHAT-010` | P2 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_support_send_message_rejects_long_message_id_before_db`; `test_web_support_message_retry_rejects_same_message_id_with_different_payload`; `test_requester_ticket_message_rejects_long_message_id_before_db`; `test_requester_ticket_message_retry_rejects_same_message_id_with_different_payload` | no-DB endpoint pytest green; DB-backed retry happy-path pytest hung locally | no, unless release-impacting |
| `CREATE-011` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-012` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-013` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-014` | P2 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `WORKFLOW-015` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `WORKFLOW-016` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `WORKFLOW-017` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CLOSE-018` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_public_ticket_session_rejects_terminal_ticket_even_if_not_revoked` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `TOOL-019` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `MODULE-020` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `CONSENT-021` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `PLAYBOOK-022` | P2 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `HISTORY-023` | P1 | history/context | open, verify in Phase 0 | not-started | required | missing | yes |
| `HISTORY-024` | P2 | history/context | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `SUPPORT-025` | P1 | support/admin truthfulness | open, verify in Phase 0 | not-started | required | missing | yes |
| `SUPPORT-026` | P2 | support/admin truthfulness | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `INSTALL-027` | P1 | installer/update | open, verify in Phase 0 | not-started | required | missing | yes |
| `INSTALL-028` | P1 | installer/update | open, verify in Phase 0 | not-started | required | missing | yes |
| `AUTH-029` | P1 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ui_users_repo_failed_attempts_are_atomic_across_stale_sessions` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `AUTH-030` | P2 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_session_register_rejects_login_longer_than_db_limit` | no-DB registration pytest green | no, unless release-impacting |
| `TOKEN-031` | P2 | pairing/session delivery | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `ASSIGN-032` | P2 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `ACCOUNT-033` | P1 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_unverified_other_account_does_not_resolve_declared_person` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `PUBLIC-AUTH-034` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_public_ticket_authorize_rate_limits_invalid_code_attempts` | no-DB handler pytest green; live/stand evidence missing | yes, until live evidence |
| `PAIR-035` | P2 | pairing/session delivery | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `SCALE-036` | P1 | scaling/protocol risk | open, verify in Phase 0 | not-started | required | missing | yes |
| `PROTOCOL-037` | P1 | scaling/protocol risk | open, verify in Phase 0 | not-started | required | missing | yes |
| `TOOL-038` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `TEST-039` | P0 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |
| `TEST-040` | P1 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |
| `RELEASE-041` | P0 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |

## Current Implementation Mismatch

These gaps must stay visible so existing scripts are not mistaken for completed live-proof infrastructure:

- browser runner = probe-only;
- operation lifecycle = malformed-outbox placeholder;
- native agent = connected-state placeholder;
- evidence pack lacks `stand`;
- validator is structural, not a full semantic pack validator;
- fallback live credentials still exist in browser script.

## Immediate Guardrails

- Keep `WEB_SELF_REGISTRATION_ENABLED=false` until `ID-001` and `ID-002` have live evidence and migration audit is clean.
- Do not run broad live bug hunts until Phase 2 is green.
- Do not run multi-instance server deployment while process-local DeviceOutbox/session state remains an active risk.
- Treat release as blocked until all 17 critical scenarios have passing `pc_client.live_evidence.v2` manifests and exact release summary.
- Maintain the fail-closed guard for unknown chat visibility before broader chat refactoring.
- Make public-session verification depend on ticket state as defense in depth.
- Reject high-risk dispatch when `tool_call_started`/outbox transaction is not persisted.
- Make support UI distinguish DB outage from an actually empty queue.
- Create or update bug records for all deep-audit IDs before changing implementation.

## Done Criteria For Already Known Bugs

For each known bug, `verified-fixed` requires all applicable evidence below:

1. Pre-fix proof on current `HEAD` or a documented `not-reproduced` / `already-fixed` disposition.
2. Regression test that fails before the fix or a documented reason why red-first proof is impossible.
3. Small code fix with no unrelated behavior change.
4. Focused green tests for the touched layer.
5. Negative and concurrency tests for auth, account, workflow, idempotency, ticket state, public-token, operation or session-delivery bugs.
6. Observer checker update or Observer assertion where the defect affects integrity, security, lifecycle or release evidence.
7. Real UI/API/DB evidence and agent evidence when the agent participates.
8. Clean run marker, cleanup proof and no cross-test contamination.

## Known Bug Remediation Waves

Phase 1 fixes follow this order. P2 items in the same area may be fixed in the wave when they are cheap, directly adjacent or needed for a clean P0/P1 proof, but they do not block starting the next P0/P1 slice unless Phase 0 promotes them.

| Wave | Area | IDs |
|---|---|---|
| A | identity/account/session/public access | `ID-001`, `ID-002`, `AUTH-029`, `AUTH-030`, `ACCOUNT-033`, `CLAIM-003`, `CLOSE-018`, `PUBLIC-AUTH-034`, `AGENT-AUTH-004`, `PAIR-005`, `SESSION-006`, `TOKEN-031`, `PAIR-035` |
| B | ticket create/event/timeline/workflow | `EVENT-007`, `EVENT-008`, `CHAT-009`, `CHAT-010`, `CREATE-011`, `CREATE-012`, `CREATE-013`, `CREATE-014`, `WORKFLOW-015`, `WORKFLOW-016`, `WORKFLOW-017`, `ASSIGN-032` |
| C | tool/operation/consent/module | `TOOL-019`, `MODULE-020`, `CONSENT-021`, `PLAYBOOK-022`, `TOOL-038` |
| D | history/support/admin | `HISTORY-023`, `HISTORY-024`, `SUPPORT-025`, `SUPPORT-026` |
| E | installer/update | `INSTALL-027`, `INSTALL-028` |
| F | scale/protocol/test/release assurance | `SCALE-036`, `PROTOCOL-037`, `TEST-039`, `TEST-040`, `RELEASE-041` |

## Phase 0 - Baseline and Current-HEAD Verification

**Goal:** verify the known audit findings against current local `HEAD`, record release context and determine whether stand/data are safe enough for remediation.

**Work:**

- Bootstrap UTF-8 and rebuild stale context:
  `.\scripts\bootstrap_shell_utf8.ps1`
- Run intake and focused context:
- Record exact local commit, deployed commit, branch, expected schema head, actual schema head, environment and release run id.
- Collect a read-only DB report for:
  case-colliding UI logins, UI accounts without verified `ui_login`, ambiguous person-to-web-account links, closed tickets with active public sessions, consumed pairings without account session, approved login requests without deliverable secret, duplicate event/message IDs, `in_progress` without assignee, queue/OLA mismatch.
- Run baseline Observer integrity scan and record active/suppressed critical/high/error events.
- For every deep-audit ID, verify current `HEAD` and write a row to `known_bug_registry.current_head.json`.
- Assign each ID status: `open`, `reproduced`, `not-reproduced`, `already-fixed`, or `blocked`.
- Sort P0/P1 IDs by fix order and copy that order back into this plan.
- Create or update bug cards for IDs that reproduce or remain open.

**Exit criteria:**

- `known_bug_registry.current_head.json` exists.
- All 41 IDs have a current `HEAD` status.
- P0/P1 bugs are sorted in implementation order.
- False positives and blocked-by-stand/data items are explicitly marked.
- The stand is either cleared for remediation evidence or marked blocked with exact blocker reason.

## Phase 1 - Remediate Already Known P0/P1 Bugs

**Goal:** close already-known P0/P1 defects before searching broadly for new live defects.

Broad live bug hunt starts only after all static-confirmed P0/P1 known bugs are either verified-fixed, verified-non-product, or explicitly accepted as release-blocking known limitations.

For every bug in this phase:

`pre-fix evidence -> regression test -> fix -> focused tests -> DB/API/UI verification -> Observer assertion -> status verified-fixed`

### Wave A - Identity / Account / Registry

Minimum order:

1. `ID-001` - fixed locally, live evidence pending
2. `ID-002` - fixed locally, live evidence pending
3. `AUTH-029` - fixed locally, live evidence pending
4. `AUTH-030` - fixed locally by adjacent login-length alignment
5. `ACCOUNT-033` - fixed locally, live evidence pending

Required direction:

- Introduce `normalized_login` or a functional unique index on `lower(user_login)`.
- Normalize login before auth lookup and token subject creation.
- Remove fallback web-account resolution through email, Windows login or AD identity.
- Add durable verified web-account-to-person link.
- Route email/AD matches through claim/conflict flow.
- Align login max length across DTO, handler and DB.
- Make failed-attempt increments atomic.
- Migration must detect collisions, quarantine ambiguous accounts, backfill verified links and fail preflight on unresolved P0 collisions.

### Wave B - Claim / Public Session / Pairing

Minimum order:

1. `CLAIM-003` - fixed locally; live evidence pending
2. `CLOSE-018` - fixed locally; live evidence pending
3. `PUBLIC-AUTH-034` - fixed locally; live evidence pending
4. `AGENT-AUTH-004` - fixed locally; live evidence pending
5. `PAIR-005` - fixed locally; live evidence pending
6. `SESSION-006` - fixed locally; pytest fixture/runner evidence pending
7. `TOKEN-031`
8. `PAIR-035`

Required direction:

- Use row locks or conditional updates for public ticket claim.
- Keep agent token, fingerprint and rebind checks in one transaction.
- Enforce device-scoped token max count with advisory lock or serializable transaction.
- Verify public sessions against revoked, expiry, ticket ownership and terminal-state policy.
- Make close/revoke atomic or enforce deny-by-closed-state defense in depth.
- Model pairing states as `created -> browser_confirmed -> awaiting_approval -> approved_pending_delivery -> delivered -> consumed`.
- Do not consume before a deliverable session exists.
- Enforce one active pairing per device/purpose.
- Use a durable encrypted one-time token envelope.
- Make delivery claim atomic with `delivered_at IS NULL`.
- Prove polling works across workers and restarts.

### Wave C - Create / Chat / Timeline / Workflow

Minimum order:

1. `EVENT-007` - fixed locally; live evidence pending
2. `EVENT-008` - fixed locally; DB-backed migration/live evidence pending
3. `CHAT-009` - fixed locally; DB-backed endpoint/live evidence pending
4. `CHAT-010` - fixed locally; DB-backed retry/live evidence pending
5. `CREATE-011`
6. `CREATE-012`
7. `CREATE-013`
8. `WORKFLOW-015`
9. `WORKFLOW-016`
10. `WORKFLOW-017`

Required direction:

- Add `Idempotency-Key` support for ticket create, messages, close/feedback/reopen, run tool/playbook, consent decision, assignment/status/queue mutation.
- Add durable idempotency storage with actor/scope, request hash, `in_progress/completed/failed`, response snapshot, TTL and unique scope/key.
- Add DB constraints for event/message IDs and agent event uniqueness.
- Use `ON CONFLICT` for server event insert paths.
- Separate agent replay ordering from UI timeline ordering.
- Add monotonic `timeline_seq` or robust keyset pagination.
- Add cursor pagination for ticket/event/history APIs.
- Convert routing/SLA/OLA side effects to durable outbox/reconciliation, not silent success.
- Ensure unverified accounts cannot receive `requester_person_id`.
- Add or enforce `tickets.version`.
- Use CAS for status mutations.
- Row-lock assignment/load policy.
- Enforce `in_progress -> assignee required`.
- Keep queue/OLA changes transactional or visibly pending.

### Wave D - Tool / Operation / Consent / Module

Minimum order:

1. `TOOL-019`
2. `MODULE-020`
3. `CONSENT-021`

Required direction:

- Canonical transaction order: `operation + tool_call_started + device_outbox + observer correlation -> commit -> sender dispatch`.
- High-risk tools fail closed.
- Preserve initiating actor attribution and store service principal separately.
- Require idempotency for tool/playbook runs and consent decisions.
- Add `approved_pending_dispatch` plus recovery worker for consent after dispatch outage.
- Show module owner conflict before run.
- Remove legacy execution paths or route them through the unified service.

### Wave E - Support/Admin Degradation

Minimum order:

1. `SUPPORT-025`
2. `SUPPORT-026`

Required direction:

- DB outage returns explicit `503` or `200 degraded=true` with stale timestamp.
- UI shows a visible degraded/error banner and retry action.
- UI must not show zero counts as trustworthy when a source is incomplete.
- Query values are typed and bounded.
- Permission matrix is enforced for auditor/support/admin mutations.
- Invalid internal-note visibility fails closed and preserves draft text.
- Partial operation state is explicit if retained.
- Raw IDs remain secondary metadata.

### Wave F - Agent Installer/Update

Minimum order:

1. `INSTALL-027`
2. `INSTALL-028`

Required direction:

- Add update journal with phases and durable rollback marker.
- Use temp file, flush/fsync and atomic replace for `current.json`.
- Backup/restore DB for failures after verify/publish starts.
- Use SQLite online backup API.
- Add crash recovery for each intermediate phase.
- Formalize installer/portable deployment, signed artifacts, install/uninstall/repair contract and data directory ACL.

**Exit criteria:**

- Every static-confirmed P0/P1 ID in Phase 1 has status `verified-fixed`, `verified-non-product`, or `accepted-release-blocking-limitation`.
- Regression tests and evidence links are recorded in the defect registry.
- No new high/critical Observer event remains active after remediation.
- No release-blocking known bug is hidden behind a live-tooling gap.

## Phase 2 - Verify Known-Bug Fixes End-to-End

**Goal:** prove the system still works after known P0/P1 remediation and before new-bug discovery begins.

Required smokes:

- requester registration/profile/device-link smoke;
- requester create/chat/close smoke;
- support queue/status/message smoke;
- tool/consent smoke;
- admin registry/observer smoke;
- no P0/P1 regressions;
- no new high/critical Observer events.

**Output:**

- `known_bug_fix_verification_summary.md`;
- P0/P1 fixed bugs verified;
- system smoke green;
- list of skipped checks with explicit reason, if any.

## Phase 3 - Harden Live Bug-Hunt Tooling

**Goal:** make live evidence machine-verifiable before trusting broad scenario results.

Likely files:

- `scripts/run_live_behavior_suite.py`
- `scripts/live_evidence_pack.py`
- `scripts/validate_live_evidence.py`
- `scripts/build_live_release_summary.py`
- `webapp/scripts/live-browser-scenarios.mjs`
- `test_data_packs/critical_behavior_v1.json`
- `scripts/test_validate_live_evidence.py`
- `scripts/test_build_live_release_summary.py`
- `scripts/test_run_live_behavior_suite.py`
- `docs/LIVE_TESTING_DEBUG_RULES.md`

Work:

- Add `stand` surface support to evidence scaffold and release scenario handling.
- Add action-level browser runner support for form fill/select, ticket create, chat, internal/public support notes, status, assignment, queue changes, run tool/playbook, consent approve/deny, close/feedback/reopen, history/context/report/Observer pages.
- Add forensic browser output: screenshot, DOM assertion, console/page errors, failed network requests, target API request/response digests, server request IDs, idempotency keys, trace IDs and redaction summary.
- Add DB assertion output with redacted query digests for tickets, ticket events, operations, device outbox, registry bindings, account sessions, public sessions, SLA/OLA and history projections.
- Add Observer assertion output for trace list/detail, required root kinds, span/result consistency, integrity before/after and new critical/high/error deltas.
- Add agent assertion output for SQLite, action trace, logs, launcher/update files and UIA state.
- Extend manifests with `required_evidence`, `evidence_coverage`, `expected_outcomes` and `assertions[]`.
- Harden validator so a manifest fails when a required layer or expected outcome lacks a passing assertion or artifact.
- Remove live fallback credentials; live mode must fail unless credentials are explicitly configured.
- Ensure release summary rejects shallow manifests even when commit/environment/schema match.

**Exit criteria:** a shallow manifest for any critical scenario fails validation, and `canonical_stand_release_gate` can be scaffolded and summarized like the other scenarios.

## Phase 4 - Live Bug Hunt Execution

**Goal:** execute real domain actions to discover new bugs after known P0/P1 remediation and live-tooling hardening.

**Historical stand origin for this archived phase:** `https://example.test:9443`

Rule: new bugs found in this phase are not fixed immediately inside the bug-hunt wave. First create or update a bug card, assign priority/layer, link it from this plan or a registry, then route it into the next remediation wave.

Before every run:

- Create a unique `release_run_id`, for example `live-20260626-<commit7>-stand`.
- Create a unique scenario marker: `test_marker=<scenario_key>-<timestamp>-<short_uuid>`.
- Put the marker into safe ticket/message/custom-field/operation metadata and artifact names.
- Confirm target accounts/devices/forms: requester with completed profile and Windows primary agent, requester with Linux primary agent, incomplete-profile requester, no-primary-agent requester, support, admin, lab Windows agent and lab Linux agent.

First high-yield runs:

1. `requester_support_admin_session_switch` with session revocation and role switch.
2. Self-registration hijack attempt using a login equal to an existing Registry email.
3. Case collision: `Alice` vs `alice`.
4. `real_account_device_linking` with delayed admin approval and server restart.
5. `requester_support_chat_roundtrip` with message retry and internal-note typo.
6. `admin_publish_requester_create` with double-click create and network retry.
7. `support_queue_status_after_routing` with concurrent status/assignment.
8. `tool_run_approve_deny_timeout` with late approve after timeout.
9. `module_playbook_canary` with duplicate playbook idempotency key.
10. `windows_linux_vm_agent_runtime` with restart/replay pending command.
11. Closure flow: resolve, public token, requester confirm close, old public token denied.
12. History cutoff: requester 301st ticket and old affected-person history.

Pass/fail rules:

- `fail` if a required layer is missing, browser/API/DB/Observer disagree, new critical/high/error Observer event appears, unexpected suppression appears, auth/account boundary is unclear, secrets leak into artifacts, cleanup is missing, replay creates duplicates, stale data lacks run marker, or commit/schema preflight mismatches.
- `blocked` if the stand is unreachable, deployed commit/schema head is unknown, required agent is offline, test account is missing, DB tunnel is unavailable, Observer scan is incomplete or contamination invalidates results.
- `pass` only if every required layer and expected outcome has a passing assertion, manifest validates, Observer canary passes, cleanup passes or is not applicable, no critical/high/error delta appears and exact release context matches.

## Phase 5 - New Bug Intake, Triage and Plan Update

**Goal:** convert live-findings into an ordered remediation backlog instead of mixing discovery and fixing.

Every live bug creates or updates:

- `artifacts/live/<run_id>/bugs/<bug_id>.md`;
- `quality/active_risks.json` if P0/P1 or release-blocking;
- this plan's bug registry row or a linked registry row;
- test refs once a regression exists.

Bug intake format:

```yaml
bug_id:
source_live_run:
scenario_key:
priority:
primary_layer:
status:
release_blocker:
regression_test_required:
observer_checker_required:
fix_phase:
```

Triage work:

- classify new bugs;
- deduplicate against known IDs and prior live cards;
- assign priority and owner/candidate owner;
- list impacted scenarios;
- define required evidence;
- decide stop/release blocker status;
- add to remediation backlog;
- route to Phase 6 or defer with explicit reason.

## Phase 6 - Remediate Live-Found Bugs

**Goal:** fix the live-found backlog created in Phase 5.

Work:

- Pull the next P0/P1 or release-blocking item from the triaged backlog.
- Capture pre-fix evidence from the source live run.
- Add regression coverage and Observer checker/assertion where required.
- Fix with the smallest correct change.
- Run focused tests, negative tests and live/API/DB/Observer verification.
- Update `quality/active_risks.json`, bug cards and this plan.

**Exit criteria:** all Phase 5 release-blocking live bugs are verified-fixed, verified-non-product, deferred with explicit release limitation, or still blocking release.

## Phase 7 - Repeat Live Hunt and Regression Matrix

**Goal:** rerun fixed scenarios and add exploratory coverage without losing exact-context discipline.

Work:

- Rerun all scenarios that produced Phase 5/6 bugs.
- Rerun the 17 critical behavior scenarios.
- Add exploratory variants for identity/session, cross-role search, public links, concurrent workflow, tool consent timing, agent restart/replay and report/history boundaries.
- Confirm all new bugs follow Phase 5 intake before any fix work starts.
- Update regression matrix with scenario, bug id, test ref, evidence ref and current status.

## Phase 8 - Observer/Test Layer Expansion

**Goal:** make integrity gaps visible and prevent future shallow tests.

New or expanded Observer checker sources:

- `observer.identity_boundary`: `ui_login_case_collision`, `web_account_person_link_missing`, `web_account_person_link_ambiguous`, `external_identity_granted_without_verification`, `unverified_account_ticket_person_link`.
- `observer.registration_sessions`: `pairing_multiple_active`, `pairing_consumed_without_session`, `approved_login_request_secret_missing`, `account_session_delivery_duplicate`, `account_session_device_mismatch`.
- `observer.ticket_integrity`: `ticket_create_side_effect_incomplete`, `ticket_in_progress_without_assignee`, `ticket_queue_ola_mismatch`, `closed_ticket_active_public_session`, `ticket_multiple_terminal_events`, `ticket_event_duplicate_id`, `ticket_message_duplicate_id`, `ticket_timeline_non_monotonic`, `requester_history_projection_incomplete`.
- `observer.tool_lifecycle`: `tool_dispatched_without_started_event`, `operation_outbox_missing`, `tool_actor_attribution_mismatch`, `consent_approved_dispatch_missing`, `operation_terminal_result_missing`, `playbook_duplicate_execution_key`.
- `observer.agent_update_integrity`: `update_journal_incomplete`, `publish_failed_without_db_restore`, `current_pointer_invalid`, `handshake_version_not_confirmed`, `rollback_version_not_confirmed`.
- `observer.support_degradation`: `support_workspace_source_incomplete`, `support_empty_success_on_backend_error`, `support_summary_stale_without_banner`.

Test layer expansion:

- Unit/property: login canonicalization, profile field policy, FSM, idempotency request hashing, visibility enum, timeline cursor, update journal recovery.
- PostgreSQL integration: functional/partial indexes, row locks, CAS, two-session barriers, rollback, old-baseline migrations and partial migration retry.
- Multi-process: two server workers, approval on worker A and poll on worker B, outbox sender ownership, restart recovery.
- Protocol/agent: token validity, fingerprint mismatch, ACK after persistence/duplicate/no-op proof, malformed context NACK, terminal result replay, duplicate command handling and agent SQLite state.
- Fault injection: before/after DB write, after commit before HTTP/WS response, before outbox, after consent commit, during update pointer replace and during public token issuance.
- Load/boundary: 301 requester tickets, 1001 affected-person tickets, 501 mixed events, 2001 support tickets, 10k chat messages and malformed query values.
- Security: cross-account, cross-device, cross-queue, auditor mutation, support/admin permission matrix, self-registration abuse, public code throttling, CSRF/session cookie policy and redaction.
- Mutation smoke: login normalization, verified-link check, fingerprint check, CAS, public-session closed-state check, visibility validation, start-before-dispatch, event conflict handling and pairing one-time delivery CAS.

## Phase 9 - Release Gate

Release candidate is allowed only when:

- known bugs are fixed, verified-non-product or explicitly accepted as release-blocking limitations;
- new live bugs are triaged;
- no open P0/P1 bugs remain outside accepted release-blocking limitations;
- all 17 critical behavior scenarios have `status=pass`;
- exact-context live summary passes;
- `python scripts/verify_workspace.py` is green;
- plain full `python scripts/run_ci_suite.py` is green on the frozen commit;
- fresh migration and supported old-baseline upgrade are green;
- real-backend Playwright is green;
- fixture drift audit is green;
- Windows installer/update VM matrix is green for agent release changes;
- two-worker/restart suite is green;
- live summary matches commit, deployed commit, environment, release run id and schema head;
- Observer baseline/delta/canary are green;
- no new active critical/high integrity events exist;
- no unexpected suppressions exist;
- public token is revoked/denied after closure;
- `TD-015` or equivalent multi-instance risk blocks horizontal scaling until actually resolved.

## 17 Critical Behavior Scenarios

| Scenario | Surface | Required live action |
|---|---|---|
| `requester_support_admin_session_switch` | requester | Login as requester/support/admin, switch sessions, verify no prior account data, revoke session and deny access. |
| `real_account_device_linking` | admin | Create/lookup pairing, confirm registration, approve binding, verify requester device view and agent state. |
| `requester_support_chat_roundtrip` | support | Create ticket, send requester/support messages, retry message, verify DB/timeline/no duplicates. |
| `admin_publish_requester_create` | requester | Admin publish form, requester select form, create ticket, verify form version/policy snapshot. |
| `support_queue_status_after_routing` | support | Create routed ticket, verify queue/status/SLA/OLA in UI/API/DB. |
| `requester_support_admin_search_visibility` | requester | Search as requester/support/admin, verify ACL and no support-only leak. |
| `requester_feedback_support_qa` | support | Resolve ticket, submit feedback, reopen, verify QA view privacy. |
| `admin_problem_support_link` | admin | Create similar tickets, generate problem candidate, link evidence, verify restricted field redaction. |
| `admin_change_approval_workflow` | admin | Create change, override risk with reason, approve/reject, rollback/PIR evidence. |
| `bounded_provider_canary` | support | Run diagnostic provider, verify evidence chain, versioned output and redaction. |
| `module_playbook_canary` | admin | Install module, live-test, set preferred, run playbook, verify step order and rollback evidence. |
| `tool_run_approve_deny_timeout` | operation_lifecycle | Real consent-required tool approve/deny/timeout/late decision/cancel. |
| `windows_linux_vm_agent_runtime` | native_agent | Restart/reconnect/replay/update rollback on Windows and Linux agents. |
| `non_production_remote_assist_session` | support | Request Remote Assist, requester consent, session start/end, artifact access and audit. |
| `admin_support_trace_drilldown` | admin | Trigger known traces, verify spans/redaction/integrity no business mutation. |
| `browser_totals_against_seeded_pack` | reports | Compare browser report totals with API and DB aggregates. |
| `canonical_stand_release_gate` | stand | Verify deployed commit/schema/service health/rollback markers/exact live summary. |

## Commands

Use these as the default command set, narrowing by phase where appropriate.

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/verify_workspace.py
```

Dry-run browser scenarios:

```powershell
python scripts/run_live_behavior_suite.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --surfaces requester,support,admin,reports `
  --dry-run `
  --json
```

Dry-run agent/operation scenarios:

```powershell
python scripts/run_live_behavior_suite.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --mode agent-operation `
  --surfaces native_agent,operation_lifecycle,protocol_v3 `
  --dry-run `
  --json
```

Validate one manifest:

```powershell
python scripts/validate_live_evidence.py `
  --manifest artifacts/live/<run-id>/manifest.json
```

Build exact release summary:

```powershell
python scripts/build_live_release_summary.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --live-root artifacts/live `
  --commit <release-commit> `
  --environment stand `
  --release-run-id <release-run-id> `
  --expected-schema-head <schema-head> `
  --output artifacts/live/release-summary.json `
  --markdown-output artifacts/live/release-summary.md
```

Preflight release candidate:

```powershell
python scripts/release_candidate_preflight.py `
  --workspace . `
  --commit <release-commit> `
  --environment stand `
  --expected-schema-head <schema-head>
```

## Source Map

Sources analyzed:

- `C:\Users\admin-2\Downloads\helpdesk_deep_audit_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_live_bug_detection_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25 (1).md`
- `C:\Users\admin-2\.codex\attachments\47589abc-25dd-491b-a1e2-521ee6a533c3\pasted-text.txt`

The two remediation files are byte-identical by SHA-256, so they are counted as one unique remediation source.

Start from these files when implementing or verifying the deep-audit defect groups:

- Identity/session: `server/requester/identity_service.py`, `server/web_api/session_handlers.py`, `server/app/repos/ui_users_repo.py`.
- Registration and pairing: `server/app/repos/registration_repo.py`, `server/registry/browser_pairing_service.py`, `server/registry/account_session_service.py`.
- Agent auth and tokens: `server/websocket/agent_handshake.py`, `server/app/repos/auth_tokens_repo.py`.
- Ticket create/events/workflow: `server/tickets/create_flow.py`, `server/app/repos/ticket_events_repo.py`, `server/tickets/workflow_service.py`, `server/tickets/side_effects.py`.
- Public access: `server/tickets/public_access.py`, `server/tickets/public_ticket_handlers.py`.
- Web requester/support APIs: `server/web_api/requester_handlers.py`, `server/web_api/support_handlers.py`.
- Tools and operations: `server/tools/service.py`.
- Customer history: `server/customer_history/projection_service.py`.
- Agent update and packaging: `pc_agent/launcher/installer.py`, `pc_agent/build_windows_release.py`, `pc_agent/build_windows_release_v2.py`.
- UI tests and fixture drift: `webapp/playwright.config.ts`, `webapp/tests/fixtures/support_fixture_server.py`, `webapp/tests/requester-workspace.spec.ts`.
- Quality/live contracts: `quality/active_risks.json`, `test_data_packs/critical_behavior_v1.json`, `docs/TESTING_RULES.md`, `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `server/docs/OBSERVER_LAYER.md`.

## Handoff

Next recommended execution slice:

1. Run Phase 0 as read-only baseline and create `known_bug_registry.current_head.json`.
2. Update the per-bug lifecycle table with Phase 0 statuses and sorted P0/P1 order.
3. Start Phase 1 Wave A from `ID-001` / `ID-002`; do not run broad live bug hunt yet.
4. After known P0/P1 fixes, produce `known_bug_fix_verification_summary.md`.
5. Only then harden live tooling and execute broad live bug hunt.

Do not append chat transcripts or raw logs here. Store detailed evidence under `artifacts/live/<release_run_id>/` and link concise results back into this plan.


### Production Readiness v1 — live admin polling regression

Live current-candidate Tech Panel exposed recurring 404/console errors from shell polling of retired /api/web/admin/connection_requests. Remove only the shell legacy enrollment polling/entry; preserve ticket notification count and backend retirement boundary. A new component regression failed before the fix. Existing a534 staging/CI evidence remains historical for that exact SHA; the next commit requires its own full CI and new browser recording. Endpoint dependency status is not yet visible in Tech Panel and remains an operational acceptance gap.


### Production Readiness v1 — bounded Endpoint operational signal

Existing Tech Panel Runtime now includes Endpoint dependency read health using the canonical typed adapter and one saved ticket mapping. No new HTTP contract, health target, operation, agent dispatch, or monitoring subsystem. Without mapping, availability remains unknown; API read success cannot substitute for Windows acceptance. Regression coverage checks failure isolation, bounded projection, and missing-target behavior. New exact-SHA CI/live evidence remains required.

### Production Readiness v1 — current risk remediation checkpoint

The original deep audit was recovered from
`C:\Users\admin-2\Downloads\helpdesk_deep_audit_2026-06-25.md` and all 36
retained risk definitions were mapped to the current candidate evidence.
On candidate `4536db17a341a8d3d6f03af61017b95349c4f47c`, CREATE-012 was
reproduced by fault injection: routing/SLA/OLA exceptions were swallowed.
The bounded fix now stops required initialization, and both create HTTP routes
roll back before returning a safe 503. Three unit regressions failed before
the fix and passed afterward. Eight isolated PostgreSQL API checks passed:
three injected stages across both create routes leave no ticket or initial
events, while two normal creation controls succeed. Temporary database, role
and SSH tunnel were removed. TEST-040 was separately corrected and all 17
requester browser fixture scenarios passed; fixture results are not live acceptance.
The accepted 4536 CI/live evidence remains historical for subsequent changes.
Full CI and staging acceptance must be repeated on the next frozen SHA.
Other risk dispositions and the isolated Windows/provider gate remain open.

### Production Readiness v1 — public create atomicity

`/public_api/tickets/create` now rolls back required routing/SLA/OLA errors,
public-session issuance errors and response serialization errors together.
`AuthService` accepts an internal caller-owned session; `AuthTokensRepo`
flushes in that mode without committing. Standalone public authorization
retains the previous owned transaction. Five no-DB regressions failed before
the fix and passed afterward; six real PostgreSQL checks passed. Retry
idempotency remains a separate CREATE-011 requirement. Full next-SHA CI/live
acceptance and Windows/provider alignment remain pending.

### Production Readiness v1 — explicit support read degradation

Support command-center/workspace-summary exceptions return `DB_UNAVAILABLE`/503.
Queue/summary malformed limit values return `VALIDATION_ERROR`/400. Six
server regressions failed before the correction; the focused server suite
passed afterward. Component regressions initially exposed misleading empty
task/zero-count states; all nine checks pass with explicit unavailable labels
and cached-data retention on refetch failure. A current built-bundle browser
fixture run passed, with only the controlled 503 responses/resource errors,
no unexpected responses or page exceptions, and a screenshot inspected for
Russian text. These are focused regressions, not next-SHA live acceptance.

### Production Readiness v1 — consent conflict presentation

Candidate 2df69b1e passed its exact full CI, contract artifact and isolated
backup/restore. Its actual staging orphan-consent approval returned 409 and
rolled back consent/event/operation state correctly, but the requester ticket
page incorrectly displayed the solution-confirmation error. A bounded UI fix
uses consent context and safe delivery/state-conflict messages. Three component
regressions failed before the change; all 93 requester tests pass afterward,
and the frontend build/workspace checks pass. Fresh candidate CI and actual
browser acceptance remain required. The synthetic orphan was denied through
the browser and all three temporary accounts were disabled; staging was stopped.

Admin cutover 2026-10-01: final 2cf828af full CI and actual Windows/browser staging accepted and restored. The user subsequently authorized merging all cutover and seven Sonar commits into main; PR 39 now targets main. Pre-merge review reproduced accepted Python-only conditional/comment regex groups and a bounded mirrored validation fix adds publication, saved-form and browser regressions. Fresh candidate full CI and main integration are the remaining gates. Production deployment/data deletion remain excluded.

2026-10-12 Endpoint tools workspace: approved catalog/parameters/result/passport and
six-profile collection workflow implemented in an isolated task branch. Context
now orders requester, Endpoint computer and agent before collapsed Observer details;
critical error counts remain visible. Account/workspace preferences independently
collapse navigation and the ticket list; search/selection persist and hidden list
controls unmount. Functional PostgreSQL gates passed for admission, leases,
permissions and retained evidence; frontend unit/type/build checks passed. Browser
screenshots and runtime acceptance remain pending. Staging deployment must wait for
Guided Request Studio147 to merge into main, then attach unreleased148 to that
accepted migration chain. No production or staging service was deployed by this work.

Guided Request Studio v2 P10 fidelity: inline category creation reuses existing
category CRUD in the purpose step; category save selects the new node without
losing scenario edits, including edits made while its API response is pending.
Wizard navigation and scenario actions are disabled while the category form is
open. Component RED/GREEN and typecheck pass; browser validation is in progress.
Full P10 actual staging A–J and canonical CI remain open.
Inline category final browser gate: 4 viewports PASS (10.1s), no console/network
errors or body overflow. Independent review and deferred-response regression
pass; Chromium /v HTML patterns fixed. Full P10 remains in progress.

Guided Studio P10 sections/preview fidelity: named sections are now rendered in
requester/simulator/selected-step preview through a shared display-only renderer.
Group titles use additive bounded DTO metadata, preserve old keys and validate
consistency; the builder assigns/renames groups by title. Preview uses existing
requester controls; full-branch preview opens server simulation. Reviewer found
missing simulator unknown-answer controls; RED/GREEN and browser now verify
explicit null. Server 146 PASS; frontend 72 PASS; owned PostgreSQL selected-policy
publication/session/ticket creation 1 PASS (67.70s); 32-question browser all four
viewports PASS (10.9s); build/typecheck PASS. Full P10 remains in progress.

Guided Studio P10 staging: candidate 8fd099ee installed with schema 147 and a
verified pre-migration backup. Strict HTTPS synthetic login/catalog and installed
catalog at three required desktop viewports pass. Original exact-SHA CI failed
one simulator test; one unchanged-SHA diagnostic rerun is underway. Synchronous
unknown checkbox snapshots prevent reading mutable DOM in deferred updates;
null/omission tests and focused 21/full 650 frontend checks pass, build and scoped
workspace pass, review has no blocking findings. Original CI RCA remains unproven.
Actual printer A-J, final exact-SHA CI/security/Sonar and full acceptance remain open.

P10 exact CI 47012713 passes 650 frontend tests and Endpoint contracts; the full
gate exposed a stale cleanup count/prefix. RED reproduced 171 versus 173;
focused harness GREEN 42 passed after preserving exact Studio runtime entries.
Owned staging pilot draft configured through the wizard; readiness checks 192
outcomes and correctly blocks missing closure/visibility registry policies and
draft categories despite Health=ok. No publication/tickets; staging stopped.

P10 instruction escape: explicit current-result equality to review grants the
server-projected support action without claiming acknowledgment. Required facts
and canonical submit checks remain enforced; old graphs retain their behavior.
RED 8 / GREEN 8, focused backend 107, full no-DB 1279 and frontend 25 pass;
full frontend 654, build/typecheck and 12 requester fixture browser cases pass. Independent review
has no blockers. Actual installed acceptance and final quality gates remain open.

P10 raw-SQL concurrency regression: accept only PostgreSQL cycle constraint or
deadlock abort, preserve exactly one commit and exact tree shape, then retry the
losing edge after winner commit and require 23514. Independent review PASS;
canonical isolated PostgreSQL persistence suite 9 PASS (773.26s), including
147→146→147 legacy sentinel preservation. Temporary DB/role cleanup confirmed.
Final exact-SHA CI remains required before candidate installation/publication.

P10 J publication correction: blocker actions select the source block and focus
the missing transition target, or open and focus the relevant processing policy
after registry loading. Navigation leaves the draft unchanged. Four RED tests
confirmed the missing actions; focused GREEN and installed acceptance are
recorded in the progress ledger. Full P10 acceptance remains open.

P10 routing availability correction: a policy's nonempty queue ID could pass
readiness even when its target was absent/inactive. Match IDs against active
queues in the locked publication snapshot; scenario preview refreshes and share
locks the current queue, and submit repeats this guard. Actual scenario creation
checks its routed queue before downstream initialization/playbooks, covering
interleaved routing-policy changes. Four RED tests; focused 39 and full backend
no-DB 1285 PASS for the initial guard; three PostgreSQL checks PASS. Additional
boundary RED 2/GREEN 14 and interleaved PostgreSQL RED confirmed the remaining
race. Final focused 54 and full no-DB 1287/1 skipped PASS; nine PostgreSQL
scenario/publication/legacy-create regressions PASS (274.81s), scoped role absent
and no residual owned DBs. Independent review, workspace and diff checks PASS.
Latest exact-candidate CI and installed A–J remain required.

P10 long requester page: actual eacd57c5 tablet D exposed Continue below the
viewport; A/B/C UI and DB passed but do not accept D or a later candidate.
Separate native disabled fieldsets keep actions sticky while questions remain
in document flow. The new-request shell uses horizontal clip for both canonical
and trailing-slash URLs, avoiding an intermediate vertical scroll ancestor.
Longform browser RED reproduced the missing primary action. Exact candidate CI,
fresh installed pilot and final cleanup remain required. Sonar is deferred by
the user's explicit instruction; no Sonar PASS or production admission is inferred.

2026-10-12 Endpoint tools staging preview: user authorized immediate test deployment
before Guided Request Studio merges. Dedicated codex/endpoint-tools-staging-preview
combines the installed Guided2f2a2ec with the reviewed tools candidate; unreleased148
follows147. Preserve staging data and services for inspection. Main/production
publication and live Agent execution remain separate acceptance steps.


# 2026-10-13 Studio live authoring bug fixes

Reproduced on installed staging in a separate browser tab without changing the
user's map: deletion confirmation hidden below the inspector, decision rules
only accessible via arrows, entrance following its question, and first-step
controls obscured by expanded guidance. Added visible deletion dialog with
explicit detach/redirect, inline decision/check branches and fallback, independent
entrance geometry, stable legacy layout on deletion, visible unset start marker,
start navigation, larger labeled connection handles, first-step fit and a page
selector in preview with a link to canonical server simulation. No client evaluator.
RED regression checks for deletion/conditions became GREEN. Focused Studio unit
checks: 114 PASS. Browser authoring/geometry/preview/simulation-focus checks: 22 PASS
at 1366/1920/820 and 1440 where applicable. TypeScript/Vite build, scoped workspace
verification and diff check PASS. Live staging verification remains required
following the reviewed staging installation; production/publication excluded.


Live server follow-up: a true decision branch reached a ticket result but the
canonical template required impact_scope/work_continuity. The old handler hid
this behind generic VALIDATION_ERROR. Simulation now separates reached route
from blocked processing; explicit canonical required-question import preserves
conditions and still requires the existing server form/policy checks. No
requester/publication guard changes, catalog writes or real ticket creation.
# Catalog restoration from supplied references — 2026-10-13

- Scope: admin section → optional category → service; one full-width compact
  list with resizable tree/inspector. Maps have their own administration tab.
- Reuse canonical Offering/RequestTemplate/policy paths. Multiple named entrances
  remain separate catalog services backed by one shared map/type. Preserve CAS,
  active published snapshots, drafts, and existing route creation/testing.
- Implemented inline section/category/service editing, category/search metadata
  validation, shared-entry creation, four inspector groups, global Catalog return,
  and removal of the duplicate map-library Catalog tab.
- Verification: focused frontend/backend checks and fixture browsers at
  1366×768, 1920×1080, and 820×1180; exact results and staging evidence recorded
  in the task receipt after the canonical staging installer completes.
- Staging only; no production/Endpoint changes, automatic catalog publication,
  schema migration, or real ticket submission.

# Catalog navigation follow-up — 2026-10-13

- Remove the separate maps tab; open linked maps directly from the service inspector.
- Repeat ordinary forms and named scenario entrances in the section/category tree;
  fetch unfiltered pages independently of center filters and retain CAS/dirty guards.
- Keep form, new-map and shared-entrance creation under `Создать услугу`.
- Validation: focused Studio unit/build/browser checks and staging UI checks;
  exact results and installed identity recorded in the task receipt under `tmp`.
- Scope: staging only; no requester ticket creation or catalog publication.

# Studio processing navigation — 2026-10-14

- Reproduced on staging service `123555`: policy remediation focused the right
  selector inside general Start settings, making its purpose and destination unclear.
- Separate service-processing inspector; requested control first, highlighted and
  focused, explanatory text for eight kinds, accurate server-inheritance wording.
- Preserve canonical policy references, server readiness checks and draft data.
  Repeated remediation, preview exit, unavailable registry and selection are covered.
- Staging only; no automatic policy selection, service publication or database change.
  Focused tests/build/workspace and installed browser results recorded in the task receipt.

# Studio closure and visibility rule editing — 2026-10-14

- Existing Forms workspace policy controls are a read-only preview; direct Studio
  actions now open the reusable real closure/visibility fields in a modal.
- Existing registry publish endpoint, generated internal code, no inherited scope
  target; edited shared rules become separate copies, preserving extra config.
- Explicit review, publish rule, apply to service draft, save/test/publish service.
  No second policy store/engine or automatic service publication.
- Checks cover both kinds, registration/assignment separation, error/dirty/read-only
  behavior and canonical resolver proof that unbound rules do not alter inheritance.
- Staging browser acceptance and exact release identity recorded in task receipt.

# 2026-10-15 Studio rule clarity and answer branches

Scope: Russian names and per-field accessible explanations for inline closure/
visibility rules, readable result/field choices preserving canonical values and
legacy extras. Existing Forms Builder callers retain their prior controls.
Decision/check branches open immediately; choice branches begin with equality
against an answer, and map question cards show their type. Canonical runtime
remains unchanged. Own staging draft only; user map drafts and active rules excluded.
Checks: frontend181 and runtime53 pass, including v1/v2 select/radio routing to
mail/VPN instructions and fallback. Final build/workspace and exact-SHA staging
browser acceptance follow. No schema, policy engine or storage changes.

# 2026-10-15 Collapsible branches and chained decisions

Bounded Studio UX: independent branch disclosures with human condition/target
summaries, expand/collapse all, automatic opening of a newly added branch. Pure UI
state does not edit scenario data. Remove redundant outer route disclosure.
Allow inserting decisions into existing edges while preserving condition,
priority, processing facts and former continuation as the new fallback. Existing
cycle guards and canonical server execution remain unchanged. No migration/API.
Browser reproduced prior insertion refusal in a fresh owned draft; the earlier
verification map has user changes and is excluded from further writes.
Checks: Studio155 and server runtime65 pass, including chained decisions with
select/radio, fallback and Back/change-answer in v1/v2. Final build/workspace and
exact-SHA staging browser acceptance follow in task receipt.
Browser follow-up found sibling React keys colliding between block editor and
route editor after decision insertion. Give route instances a separate key
namespace; add switching regression. Final Studio suite156 pass after repair.


# 2026-10-15 Studio publication to main

Publish the accumulated Studio implementation, versioned user guide and archived
interactive prototype without operational scratch files, credentials or caches.
Align unit and browser fixtures with the approved single service/map model:
catalog map titles, explicit map opening, category creation in the catalog,
processing navigation, entry labels and service creation without a form wizard.
Keep legacy diagnostic safety, template publication confirmation, auditor access,
dirty guards, complete simulation answers and immutable-version workflows covered.
No runtime behavior, production/staging deployment or Endpoint operation changes.
Checks: full unit suite792 passed in hosted CI; local no-DB server1452 passed,
1 skipped; scripts272 passed; required fast audit layers passed. Full fixture,
migration/DB and exact-SHA workflow results are recorded in the publication receipt.

# 2026-10-27 SSO, WorkTime and agent pilot — historical handoff

This handoff records the earlier `bd4f41df` documentation checkpoint. It is
superseded by the current checkpoint at the top of this file and Current evidence
in the linked execution plan. In particular, the backup/restore success below
is historical: the two-hour freshness TTL and old parent lease expired and were
not reused. The approved fresh v6 storage cycle has since completed, as recorded
in the current top checkpoint; no second resize is authorized by this history.

Goal/scope: deliver the supplied two-repository SSO/Helpdesk/Endpoint/DLP/WorkTime
specification in reviewed stages. The user authorizes separate server and signed
agent deployments, Windows domain-PC and ALT tests. No fleet, GPO, bulk account
migration or organization-wide monitoring rollout.

Current state: Helpdesk736f3ae8 has all18 exact-revision CI layers green, staged
schema151 and4 pinned-provider cross-repository acceptance tests passing. Earlier
business/WSS/backup receipts are retained under their actual revisions; all six
current deployment receipts and an owned mutating lifecycle remain open.
Production Helpdesk release gates remain open. Endpoint production62fb4c83/
schema0042 is healthy with SSO/WorkTime disabled. Native signed Windows3.2.158 is installed and READY; ALT
Foundation/UserSensor3.2.158 is installed, selectedCore156 awaits singleton OTA.
Core158 canary and signed ALT kit are published without rollout targets. Windows
Setup158 is not the administrative delivery default. Three-client provider/MFA/
refresh checks passed, but AD-disable testing exposed deletion of the imported
pilot subject/OTP by the enabled-only LDAP filter. The pilot is re-enabled;
reviewed retention/MSAD source fixes await private recovery qualification. The
original subject/OTP metadata is verified in a separate restored candidate;
public Keycloak is unchanged and application flags remain off.

Next steps: qualify and independently review private Keycloak recovery before
any public database switch or further AD-disable test. Query-safe Nginx logging
is verified on both hosts; the Helpdesk application logger is staged736 only.
Bounded staging backups and both real off-host restores now pass. Independent
reconciliation accepted nine artifacts, source/dump bindings and private ACLs;
the actual v5 final verifier confirms unchanged apps and strict TLS health.
The proposed test-only `.118` root-LV expansion awaits user approval: LV/ext4
remain 52609155072 bytes and no resize/attempt marker exists. Production `.19`
is outside the storage proposal. Earlier guard refusals are preserved.
Windows120 remains on original81/production origin with handoff not started and
Windows gate not_run. Await valid existing Endpoint admin credentials through a
private channel, then finish current deployment gates, application identity-link/
revocation checks, singleton Core158 update and measured-return notifications.
Keep real failed/partial receipts; never substitute fixture evidence for live gates.

Verification/handoff: see docs/superpowers/plans/2026-10-27-sso-worktime.md for
commit/deployment and private redacted evidence locations. Preserve unrelated
local files and original dirty Endpoint checkout; work only in the approved
Endpoint sso-worktime-20261027 worktree. Mandatory independent subagent reviews
continue at each gate. The task is not complete.

## Helpdesk phase-one UX — 2026-11-02

Scope: preserve registration, existing profiles and question/SLA semantics;
remove MFA for every Helpdesk role and manual resolution-code prerequisites;
automate processing preview and created-ticket opening; simplify support entry
and ordinary resolution/closure; add four common Studio maps.

Baseline: `9a79f6cfba8cfe37649a62e0077a82ff8637ac9f`, branch
`codex/ui-support-001`. Source changes and per-task review are implemented;
integrated review, isolated PostgreSQL, browser fixtures and exact-release
staging acceptance are complete. Runtime candidate:
`fb7d326c7e568f616d2829ec0c7a1bd318cc6f0e`. No production deployment or push.
Registration remains controlled by its existing flag. Unknown AD identities
must be explicitly linked; never infer roles or ownership from a matching login.
The user explicitly selected a new `admin-2` administrator; canonical exact-AD
binding and real password-only browser login passed without changing old accounts.

Verified: final full frontend947 tests; last layout35 focused tests; actual
browser35 cases; isolated PostgreSQL49 integrated and3 catalog tests; build,
TypeScript, workspace verification and reviews. Four maps and closure1.0.2
published canonically, preserving old24 versions/40 drafts/65 ticket snapshots.
Seven owned live Other/Studio tickets66–72 passed creation, support start/reply,
public result and atomic code-free closure; requester result and voluntary rating
passed. Final network173 responses without failures and warning/error logs empty.
Exact runtime/source digests, strict TLS health200 and serviceactive verified.
Staging remains running as explicitly requested; temporary viewport was reset.

Next pilot preparation: decide registration/provisioning policy, complete real
profiles/identity links, review historical test catalog and synthetic operator
roster before real employee traffic. No bulk deletion or production change.

Tracking: `docs/superpowers/plans/2026-11-02-helpdesk-phase1.md` and
`.superpowers/sdd/2026-11-02-helpdesk-phase1/progress.md`. Preserve unrelated
preexisting entries and distinguish fixture evidence from actual staging gates.
Final acceptance: `docs/UX_PHASE1_ACCEPTANCE_2026-11-02.md`.


## Support follow-up — 2026-11-02

User comments exposed legacy active tickets without owners and invisible public
messages in long SLA-heavy histories. Fixed in committed/deployed runtime
`376b46c012160473fe2ebc40a0185784f692e487`:
`fix(support): require self-claim and show recent conversations`.

Status-preserving self-claim is explicit and validates expected ownership/scope
under lock. Resolution requires the current assignee for administrators too.
Public/private conversation reads filter before LIMIT and select the latest
window; History keeps diagnostics. Old replay ordering and stored events remain.

Verified:90 focused backend noDB,6 real isolated PostgreSQL,76 frontend and15
support browser cases; TypeScript/build, workspace verification and review pass.
Real admin support browser: T7 claim assigns admin before exposing resolution;
T60 restores old messages and shows a new reply immediately and after reload.
Final164 network events without failures, warn/error console empty; exact SHA,
13 source digests, TLS health200 and serviceactive verified. Staging left running.
No production deployment, push, role/schema/dependency change or Endpoint action.
Report: `docs/UX_SUPPORT_FOLLOWUP_2026-11-02.md`; evidence in task tmp directory.

## Requester onboarding — 2026-11-04

- Goal: guided employee registration with completed profile, generated login and a ready requester home; ticket creation remains a separate explicit action.
- Scope: Helpdesk staging only, keep running; one shared 30-department catalog; archive exact synthetic choices and retain historical links.
- Decisions: ФИО → отдел и контакты → пароль, ipetrov/ipetrov2; no required location; no AD account/employee import or privilege grant.
- Current State: server/UI implementation and migration152 verified locally. Frontend160 files/955 passed, latest focused11 passed; current build and browser5 passed. Original extended DB60 passed/2 obsolete-fixture failures, corrected with focused chat1 and current DB4 green129.59s; all temporary DB roles cleaned. Signup DB5 and catalog DB1 passed; noDB/API87 passed. Final independent review clean.
- Review fixes: package catalog outside ignored runtime data, strict anonymous schema, exact pending-payload replay, actual-login password validation, and contact edits retaining an existing archived department.
- Completed: commits d4a5b8774900502721180938c1988cdf30e7361a, fc3117756335c045894db9bdefa79b97184115b9 and deployed app 153dc3faf16f2759469c84758f131d58a4f538ca. Fresh backup, migration152, audited 30-department publication and repeat no-op verified. Live signup201/user-only, complete persistent profile, home before manual ticket form, zero ticket POSTs and browser errors. Final service active/health200, source21 digests match, OIDC initiation no MFA request; fresh AD credential login not repeated. Staging remains running.
- Next Steps: complete; acceptance receipt docs/UX_REGISTRATION_ACCEPTANCE_2026-11-04.md. No production deploy or push.
- Handoff: docs/superpowers/specs/2026-11-04-requester-registration-design.md; docs/superpowers/plans/2026-11-04-requester-registration.md; private progress/evidence in .superpowers/sdd/2026-11-04-requester-registration and tmp/onboarding-20261104. Production unchanged.

## Requester usability follow-up — 2026-11-05

- Goal: resolve four concrete browser comments: one department field, password visibility, one catalog search with category children, and actionable device-code instructions; investigate WorkTime login.
- Scope/constraints: requester UI only; no server/auth/API/schema/dependency changes; preserve drafts, explicit scenario choice, retry/ownership guards and unrelated local changes. Staging only; leave running.
- Decisions: existing React controls and server search, accessible department combobox, independent password toggles, expanded published problem leaves; two supplied tray/menu images, no code screenshot.
- Current State: complete. App ecd784075a2d758125ae5568ff2b682aeb57c639 deployed canonically after fresh verified backup. Source28 digests/strict TLShealth200/serviceactive and both PNG200 verified. Focused41/build pass; browser27 earlier +3 final pass1366/1920/390. Independent final review clean. Live real-session catalog/guide and public registration/toggles pass, console0, no account/ticket/binding writes. WorkTime separate AD/OIDC identity requirement confirmed from current runtime and login page; local Helpdesk-account login requires a separate trust contract, not implemented here.
- Next Steps: task complete; leave staging running. Acceptance and WorkTime findings: docs/UX_REQUESTER_FOLLOWUP_2026-11-05.md. Production/Endpoint code unchanged, no push/PR.
- Handoff: docs/superpowers/plans/2026-11-05-requester-usability.md; tmp/requester-usability-20261105 evidence.


## Helpdesk to WorkTime login — 2026-11-05

Goal: Registered Helpdesk employees open their own WorkTime without a second login; preserve explicit AD entry.
Scope: Live source-bound single-use PKCE handoff, isolated WorkTime session, own profile and verified same-person AD continuity.
Constraints: Staging only; preserve unrelated changes and AD/DLP/admin boundaries; services remain running.
Decisions: Approved design docs/superpowers/specs/2026-11-05-helpdesk-worktime-login-design.md; native implementation, independent review and canonical frozen releases.
Current State: Complete. Helpdesk7d8dda5d814e88c40d5eac2dfa1e7324135638f3 and Endpointee86a9458a0c7976659b5dc43cc8572e3bb451df installed, revisions153/0044, flags enabled with private backups. Live bdryzhak→WorkTime day and reload required no second password; same person/data preservation verified.
Next Steps: No required implementation remains. Fresh live AD credential round trip remains user-dependent acceptance; initiation verified without MFA request.
Verification: Helpdesk18 unit/API,3 handoff DB,12 OIDC/profile DB,30 frontend; Endpoint38 identity,5 DB,23 WorkTime,143 contracts,69 targeted+2 platform skips,5 deploy guards,76 frontend. Builds/workspace/diff checks passed. Strict TLS200 and three active services confirmed.
Handoff: docs/WORKTIME_HELPDESK_ACCEPTANCE_2026-11-05.md; private evidence tmp/worktime-handoff-20261105/. Production and agent/native packages untouched; unrelated dirty state preserved.


## Requester chat context — 2026-11-05

Goal: Show status, specialist, response/resolution SLA, device and public progress beside the employee conversation.
Scope: Owner-safe detail projection and usable responsive requester chat; existing polling and actions.
Constraints: Staging only, no business/identity/grant changes, preserve unrelated dirty state and drafts.
Decisions: Shared canonical timer projection; safe handling sibling after ownership check; public events in conversation, no raw diagnostics or internal notes.
Current State: Complete. Frozen1ba7c8166e1d0317479a965dcf63b1b7d2accd3a deployed canonically; live own-ticket browser accepted.29 pure backend,2 isolated PostgreSQL/API,27 frontend, build/workspace/browser and independent review pass.
Next Steps: No required chat implementation remains. Staging stays running. Binding remains separately diagnosed configuration/environment mismatch; production acceptance is not claimed.
Verification: Fresh verified backup; nine source hashes match frozen Git, schema153 unchanged, strict TLShealth200, three services active and five business-table seals unchanged. Live console0; mobile/polling/draft/error fixtures pass; preview stopped.
Handoff: docs/REQUESTER_CHAT_ACCEPTANCE_2026-11-05.md, matching spec/plan, private tmp/requester-chat-context-20261105. Return-link0554e70b0d4c679173d502af6000cc53ac17f27f accepted; login bdryzhak confirmed. Production/agent/grants unchanged; unrelated dirty work preserved.


## Access users and staging cleanup — 2026-11-05

Goal: Explain/fix specialist names and the API placeholder; leave admin, admin-2 and bdryzhak in the working account list.
Scope: Verified Registry display names for requester/admin; active default list; reversible guarded staging cleanup, history retained.
Constraints: Staging only; no reassignment, credential reset, production/Endpoint/native changes; preserve unrelated work; leave staging running.
Decisions: admin's verified person carries an exact fixture name; clear only that label, never invent a real name. Disable known synthetic accounts, retain inactive audit access.
Current State: Complete. Guarded cleanup retains159 historical accounts but only admin/admin-2/bdryzhak active; exact admin fixture name cleared. Canonical frozen e0ff50496442801a9fc5eb143af406d02a991a23 deployed after41c751623ac9f25038c7d8ff8a0ae49cd8a51621.13 frontend,15 pure backend,7 script,3 disposable DB/API and build/workspace/browser checks pass; review clean.
Next Steps: No required work remains. Staging left running.10 source hashes/schema153/TLS200/three active services and unchanged history/protected-account seals verified; live browser rows3/overview3+2/placeholder0/console0. Preview stopped; production/Endpoint/native unchanged.
Handoff: docs/ACCESS_USERS_ACCEPTANCE_2026-11-05.md and display/cleanup procedure; private backups and evidence tmp/access-cleanup-20261105. Roles/passwords of protected accounts and ticket/identity history preserved; unrelated work unstaged.

## Requester acceptance and ticket attachments (2026-11-05)

- Goal: ordinary support resolves a ticket; only its requester accepts closure or returns it to work. Browser attachments work without a linked computer.
- Scope: Helpdesk only, isolated staging101.118; production and Endpoint unchanged. Preserve existing closed tickets, decisions, special policies and unrelated local work.
- Decisions: canonical policy registry ordinary closure1.0.3, no automatic expiry; staff guard under the ticket lock. Migration154 permits ticket-bound NULL device artifacts, keeping ownership and scope checks.
- Current state: complete. Commits f65519dae504e1ed7cbae7d549a285e745ab3bd1 and3865912ae94d8ccd720a8db27757e21681b2a643; exact latter SHA installed with schema154. Ordinary policy1.0.3 published/idempotent;51closed records and special policy preserved.
- Verification:117 focused Python tests;5 attachment PostgreSQL/HTTP/migration cases; owner accept/reject and legacy opt-out API cases; latest publication/idempotency/pending/special-policy PostgreSQL case;20 frontend tests, build and workspace check pass. Built-browser fixture verifies acceptance/rejection at1366/390 with no page errors or horizontal overflow.
- Next steps: no required work remains. Two backups verified,30source hashes/TLS200/3active services confirmed. Live requester PNG upload→file-only send→support view→download passed with matching SHA256; one artifact/message on synthetic T-000058. Real T-000075 unchanged. Console0; temporary DB/role resources absent; preview stopped. Staging left running.
- Handoff: docs/TICKET_CLOSURE_ATTACHMENTS_ACCEPTANCE_2026-11-05.md; private logs under tmp/closure-confirmation-20261105 and tmp/attachments-20261105. Production/Endpoint unchanged; full CI not requested. Downgrade154 refuses while NULL-device attachment data exists.

## Support context and screenshot viewer (2026-11-05)

- Goal: move description/answers/result into a separate right-panel Context block; show screenshot thumbnails and open them inside Helpdesk, keeping download separate.
- Actor/job: support workbench; primary job is conversation and resolving the request. Context belongs to the existing inspector, available via Сведения on narrow screens. Preserve drafts, current workflow and advanced tooling.
- Scope: frontend only, existing authenticated artifact download route; safe raster images only, no external URLs or new dependencies.
- Current state: implementation and independent review complete. Context is in the right inspector; raster thumbnail opens a centered native modal with explicit download. Canonical historical ticket_id scope preserved.
- Verification:32 component tests,15 full support browser scenarios plus4 repeated final centered-viewer/draft cases at1366/1440/1920/390 pass; build/workspace/diff checks pass. Exact228f59c0c279d8261883b720ab4a688b9529b4bb deployed canonically;9source hashes/schema154/TLS200/3active services verified. Live T-000075 Context4answers, thumbnail/full292x296 image, close/focus restoration and console0 confirmed. No message/upload/status command submitted. No required work remains; staging left running.
- Evidence: docs/SUPPORT_CONTEXT_PREVIEW_ACCEPTANCE_2026-11-05.md and tmp/context-preview-20261105. Backup verified; fixture ports closed. Production/Endpoint unchanged; unrelated edits preserved. Full CI not requested.

## Requester screenshot preview (2026-11-05)

- Goal: requester chat opens screenshots inside Helpdesk with the same thumbnail/modal and separate download as support.
- Actor/job: requester conversation; view support and own screenshots without losing a reply draft.
- Scope/decision: share ChatAttachment and its standalone stylesheet through webapp/src/components; keep canonical cookie-protected artifact route, safe MIME/URL/legacy ticket_id guards and existing requester ownership. No backend/API/schema/dependency changes.
- State: implementation/review complete.20 component tests and7 browser cases (requester1366/1920/390 plus support4widths) pass, including real HTTP download, Escape/backdrop, focus restoration, preserved draft and no overflow/console errors. Build/workspace/diff checks pass.
- Complete: exactcf51046d5f864f11fa4ea1dea40164acf2ce0a0b installed canonically after verified154 backup.10source hashes/retired viewer absence/schema154/TLS200/3active services verified. Live own requester T-000058 thumbnail/full420x100 image/same URL/close-focus/console0 confirmed. No new message/upload/status command; staging left running. No required work remains.
- Evidence: docs/REQUESTER_IMAGE_PREVIEW_ACCEPTANCE_2026-11-05.md and tmp/requester-preview-20261105. Fixture port closed; unrelated edits preserved. Production/Endpoint/native unchanged; full CI not requested.

## Chat file drop and grouped replies (2026-11-05)

- Goal/actor: requester and support can drop screenshots/files over chat, review/remove grouped attachments, and send them with text as one message. Upload is automatic; send remains explicit.
- Scope: existing authenticated upload/message endpoints and permission/lifecycle guards; no backend/schema/dependency changes. Shared drop/draft UI and scoped serial upload queue; keep partial successes and cancel stale callbacks on ticket/audience change.
- State: shared drop/group UI and scoped serial upload queue implemented in requester/support. 32 focused unit tests and 11 desktop/mobile browser scenarios passed; build/workspace checks passed. Independent review has no remaining blockers.
- Complete: exact f69b5632dddbd9adb7d6693b15bacacbc5cb2ae4 installed canonically after verified154 backup.14source hashes/schema154/TLS200/3active services pass. Live own synthetic T-000058 sent one text+PNG+TXT message; reload/image decode/overflow0/console0 verified. Only one event and two artifacts added; ticket/status counts unchanged. Staging left running; no required task work remains.
- Evidence: docs/CHAT_FILE_DROP_ACCEPTANCE_2026-11-05.md and tmp/chat-drop-20261105.11 fixture scenarios verify drops, responsive grouping, partial failure, queueing and privacy; live picker uses same queue. Fixture port closed; unrelated local changes, real tickets, production and Endpoint preserved. Full CI/backend suites not requested for frontend-only change; no push.

## Clipboard screenshots and Studio form files (2026-11-05)

- Goal: Ctrl+V screenshots join requester/support reply drafts; Studio authors can attach images/files to text-field instructions and requesters can attach files to their answers. User explicitly confirmed both Studio uses.
- Scope/constraints: reuse canonical upload/ownership/capability/storage boundaries; no background clipboard reads, remote HTML image fetch or automatic send. Preserve unrelated edits, production and Endpoint. Leave staging running.
- Chat complete: ff8db7ec972745fe0b0731a93380942b5eda157b deployed canonically after154 backup.37 unit/16 browser cases, exact7source hashes/TLS200/3active services pass; live own T58 Ctrl+V preserved text and decoded thumbnail, console0/overflow0. Cleared own draft; no chat/status command. Evidence docs/CHAT_CLIPBOARD_ACCEPTANCE_2026-11-05.md and tmp/chat-paste-20261105.
- Studio state: separate scoped assets/migration155 and atomic ticket claims implemented.137 server units,12 cleanup/reset units, isolated frontend264tests/53files (plus208Studio/copy tests) and6 final browser cases pass. Native mixed paste preserves text; explicit copy provenance rebases materials/idempotent retry. Isolated PostgreSQL:12asset/purge cases +1copy roundtrip pass;26existing scenario regressions pass. Initial older author fixture used support token(403); corrected latest author test passes. Backend/frontend/finalcopy reviews have no remaining findings; purge FK/pre-commit unlink risks resolved.
- Next: freeze/commit only Studio scope, fresh154 backup, canonical exact-SHA migration/deploy and live synthetic proof. Preserve committed requester-home881cf and unrelated dirty work; leave staging running. No required obligation dropped.
- Evidence: tmp/studio-files-20261105; isolated frontend export excludes concurrent unrelated home/device-link edits (local shared tsc blocked by their invalid test option; isolated build passes). Reviewed plan docs/superpowers/plans/2026-11-05-studio-attachments.md. Full CI not requested; no production/Endpoint changes.


## Requester home redesign (2026-11-05)

- Goal/actor: requester sees a clear create action, own recent tickets and compact profile/computer readiness; implement the first displayed white-sidebar concept on staging.
- Scope: requester shell/home/device guide, existing queries/routes/ownership/consents, no new dependencies/API/schema; preserve unrelated Studio/chat work.
- Decisions: keep profile completion gates, distinguish missing/offline/ambiguous/pending devices; retain no-device request policies. Windows guide keeps screenshots; Linux/ALT uses the existing owner-check assistance form because the current agent has no Linux code UI.
- State: implementation and independent review complete; incorrect Linux intent fixed through failing regression and browser click-through. 64 component checks, build/workspace checks, 11 initial browser cases and final5 home cases at1366/1440/1488/1920/390 pass. No unexpected browser errors/requests or horizontal overflow.
- Complete: exact881cf704f3b28cd41c9a42c71fd452e4a051c058 deployed canonically after verified154 backup;15source hashes/schema154/strictTLS200/3active services match. Live home/list/profile and Windows/Linux guide checked with console0 and HTTP200; no submission or business-count change. Staging remains available; no required task work remains.
- Handoff: docs/superpowers/plans/2026-11-05-requester-home-redesign.md; docs/REQUESTER_HOME_DESIGN_QA_2026-11-05.md; private evidence tmp/requester-home-20261105. Production/Endpoint unchanged; full CI not requested.


## Requester confirmation controls (2026-11-05)

- Goal: employee always sees solution decisions after scrolling to the end of chat.
- Cause: real T-000075 is resolved/pending; controls were before messages inside the transcript scroller while the footer showed a read-only notice.
- Fix: compact bounded footer outside history, also available in description view; existing action flags/access denial preserved. No real ticket decision submitted.
- Verification:25component cases, build/workspace checks,3browser viewport cases passed; confirmation/reopen dispatch, rating expansion, cached401/403/404, long-history scroll and no overflow covered. Independent review has no blockers.
- Complete: runtime860c5677f26f5aabc575089819cfa41da1782124 installed over independently deployed Studio dc60; verified155 backup/4source hashes/health200/3active services and unchanged business counts. Live own synthetic requester ticket confirms3buttons stay visible after scrolling. No decision submitted on T-000075. Staging remains available; production unchanged.
- Evidence: docs/REQUESTER_CONFIRM_CONTROLS_2026-11-05.md and tmp/requester-confirm-controls-20261105. Task is frozen with a private index and its own branch to avoid shared Studio staging.


## Service-name search and missing-service intake (2026-11-05)

- Goal: search actual service names, add Электронный бюджет and ЕИС, offer explicit Не знаю when no matches.
- Cause: search indexed entrances but not offering names; advertised other.unknown was absent from current31published offerings, hiding fallback.
- Changes: additive service rows expand categories without cached scenario launch; explicit public fallback entry; guarded canonical publication of2maps,3entrances each, inheriting current business-system routing/SLA/policies.
- Verification:26Python,33frontend,3browser cases and build/workspace checks pass. Reviewer lock-order/hidden-parent issues fixed with regressions. No new schema/dependencies or ticket commands.
- Complete: runtime f85af9310468780cf87768671043a1e0409684bd installed with verified155 backup,13source hashes,health200 and3active services.2maps published (33offerings); previous74versions/54drafts/76tickets preserved; repeat apply idempotent.26Python/33frontend/3browser checks pass. Real API search/fallback verified; live incomplete-profile guard retained. Staging remains active; production unchanged.
- Handoff: docs/CATALOG_SERVICE_SEARCH_2026-11-05.md; private tmp/catalog-service-search-20261105. Preserve earlier installed requester controls and shared checkout/index.


## Requester symptom search (2026-11-05)

- Goal: ordinary failure/startup/login/opening phrases find different services, keeping named systems/devices specific.
- Cause: literal per-field token matching omitted related symptom phrases and repeated one offering; no result for printer startup.
- Change: curated explicit symptom intents plus noun anchors, offering interleaving and visible offering names; no auth/profile/catalog/schema/dependency changes.
- Verification:53Python/34UI tests, build/workspace and3browser viewport cases pass. Three reviewer precision issues fixed with red/green regressions; followup has no findings.
- Complete: runtime17327fbc981ba1d3261fa0a77f0fb37b863b8550 installed; verified155backup/6source hashes/health200/3active services, unchanged catalog and business counts. Live API generic20distinct, startup7, login13; network and named systems narrowed. Staging active; production unchanged.
- Evidence: docs/CATALOG_SYMPTOM_SEARCH_2026-11-05.md and tmp/catalog-symptom-search-20261105. Shared checkout/index preserved through private freeze on ab80b1a2.


## Preserve resolution SLA on confirmation (2026-11-06)

- Goal: fix and deploy false overdue after requester acceptance, restore T-000075 from verified stop event.
- Cause: closing replaced already stopped resolution_at with closed_at; actual05Nov17:42 solution was before18:47 due, confirmed06Nov09:56.
- Change: preserve stopped SLA, retain close-only fallback and reopen reset. Admin/staging/exact-ticket fingerprinted repair with canonical update and internal audit; no bulk/schema/auth changes.
- Verification:51focusedPython and3browser viewport cases pass; workspace and independent review pass. RealPG rollback/durable audit/idempotence acceptance remains.
- Complete: runtimeb765fd6362686a28209e2aa92839363f961f21bd installed with verified155backups/5source hashes/health200. RealPG flushed-update rollback, audited T75repair and repeat-idempotence pass. Original17:42stop now within18:47target; closed/confirmation/5feedback/75other tickets/21old events preserved;1audit added.3browser viewports and live support UI pass. Staging active; production unchanged.
- Evidence: docs/SLA_CONFIRMATION_FIX_2026-11-06.md and tmp/sla-confirmation-fix-20261106. Private branch/index preserve shared work and prior requester/catalog improvements.


## Preserve requester editing spaces (2026-11-06)

- Goal: stop deleting spaces while typing a new request description and other text-like fields; staging.
- Cause: controlled input rendered normalized string trim() on each keystroke, deleting a trailing space before the next word.
- Fix: render raw editing strings, retain validation/payload/required normalization and numeric/select/checkbox behavior. No API/schema/data changes.
- Verification:3regressions red before fix;141UI tests, build/workspace,3browser viewport cases and independent review pass. Character entry, multiline and dynamic preview/answer covered.
- Complete: runtime587bc6dc3c4bca4b508ece7a5f95514c78f4a49a installed with verified155backup/4source hashes/health200/3active services.141UItests/3browser keyboard-preview-answer cases pass. Real HTTPS shell/assets match installed bytes; all business counts and T75SLArepair preserved. No ticket/profile changes; staging active, production unchanged.
- Evidence: docs/REQUESTER_TEXT_SPACES_FIX_2026-11-06.md and tmp/requester-spaces-fix-20261106. Private branch/index preserve shared work and accepted SLA/catalog changes.


## Requester reopen messages (2026-11-06)

- Goal: requester return reason/comment visible to support and requester; restore2existing T77comments without repeating workflow.
- Cause: reason persisted only in status/quality facts; normal conversation reads chat_message events.
- Fix: one stable canonical public requester message in reopen transaction, postcommit WS publication on3routes, explicit requester rollback/conflict. Operator quality notes stay private.
- Verification:50focusedPython and3browser viewports pass; build/workspace/diff and independent review pass. Recovery source-owner guard tightened with regressions.
- Complete: runtime99f7428692d9627160eac77e2316c42397716462 installed; verified code/data backups, realPG rollback and idempotent2message recovery pass. All originalT77data/76other tickets preserved. Actual support UI shows both reasons/comments with no console warnings/errors; schema155 and strictHTTPShealth200,3services active. Screenshot-step repair continues independently.
- Evidence: docs/REQUESTER_REOPEN_MESSAGES_2026-11-06.md and tmp/reopen-message-fix-20261106. Private index/branch preserve shared work and prior accepted fixes.


## Optional requester screenshots (2026-11-06)

- Goal: remove mandatory screenshot stage from all active maps; preserve pinned sessions and uploads.
- Cause: uploads persist separately but evidence_note required scalar blocks32maps.
- Fix: reviewed legacy effective-definition exception; new canonical publications remove only display stage/coordinate and rewire92edges preserving processing. Batch admin/staging/fingerprint/draft CAS guards; no session retarget or immutable rewrite.
- Verified:147focusedPython/6browser cases, workspace/diff/build and independent review pass. Fresh actual32active/47historical exact patterns accepted; different retired radio pattern guarded with no sessions. Broader legacy noDB fixture failures documented separately.
- Next: exact immutable staging install with backup, realPG batch rollback, canonical32map publication/idempotence, preserved session/assets/tickets receipts and live browser acceptance.
- Evidence: docs/OPTIONAL_SCREENSHOTS_2026-11-06.md and tmp/optional-screenshots-20261106. Private index preserves shared HEAD/index and prior accepted fixes.

## Bell and Web Push notifications (2026-11-06)

- Goal/scope: chat messages and status changes in the shared bell and browser, including a closed tab.
- Implemented: transactional event-to-notification fanout, actor-scoped SQL reads/counts, durable payload-free VAPID queue, browser opt-in/out and notification-only worker with deduplication/session checks. No new dependencies or Endpoint contracts.
- Verified: 48 focused backend, 28 frontend and 7 full-Chromium fixture cases; build, workspace, diff, one Alembic head 156, inventory and cleanup-profile audits. Requester/support desktop/mobile screenshots inspected; independent review findings fixed.
- Pending: isolated PostgreSQL migration/rollback/concurrency acceptance (test tunnel defaults to example.test), real external-provider delivery and reviewed staging/release activation with a private VAPID key. Production unchanged by this task.
- Handoff/evidence: docs/BROWSER_NOTIFICATIONS.md and docs/superpowers/plans/2026-11-06-browser-notifications.md. Preserve concurrent/unrelated dirty changes; no commit/push.
