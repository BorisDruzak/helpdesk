# Environment-bound WorkTime navigation implementation plan

Latest dependent Endpoint checkpoint:1b6ce5a83dd17852ecca724c1b45378ac8536041,
schema43, API272154/worker272211; ordinary employee login no longer asks for
administrative ACR. Original activation HOLD is preserved separately from the
successful readonly current runtime/data verification. Helpdesk remains19d/
PID267363/schema151. Fresh domain form has no acr_values; authenticated cabinet
acceptance awaits admin-2 profile selection/confirmed identity binding. No binding
or role grant has been made. Detailed receipts live in
C:/Temp/worktime-employee-login-level-20261030. Endpoint observations below describe
the earlier navigation deployment only.

> **For agentic workers:** Use superpowers:executing-plans; Root implements.
> One short independent delta review covers code, tests and deployment inputs.

**Goal:** Show the WorkTime navigation link in staging Helpdesk without sending
staging employees to production.

**Architecture:** The existing nullable session field and existing desktop/mobile
link remain the boundary. Validate one fixed pair of configured Helpdesk public
origin and Endpoint employee URL. Both production and staging pairs are explicit;
unknown, mixed or decorated URLs hide the link. No request Host, forwarded host,
person ID, credential, authority or OAuth token becomes part of navigation.

**Tech stack:** Existing Python/aiohttp session handler, standard-library URL
validation, existing React shared navigation and Playwright fixture workflow.

**Spec:** The ongoing SSO/WorkTime plan and the user's instruction to proceed to
the next stage after resolving the remaining inventory requests.

## Scope and constraints

- Two old inventory requests expired normally after their acknowledged sessions
  closed during the prior deployment. No results were received. Fresh readonly
  evidence has inflight0/unknown0/inconsistent0 and clear=true; historical false
  gate receipts stay unchanged. No commands were retried or records rewritten.
- Helpdesk deployed736 and local692 differ only in planning documentation.
- Modify session URL selection, focused tests and matching docs only; preserve
  unrelated planning/user changes. No new dependencies or DB migration.
- Deploy staging .118 through the canonical reviewed Helpdesk release procedure;
  keep Endpoint source/schema/services and production unchanged.

## Steps

- [x] Add production/staging pair and fail-closed cross-environment tests; reproduce
  staging rejection before implementing the minimal handler change.
- [x] Update SSO/CODEMAP docs, run focused backend and desktop/mobile browser
  checks, and obtain a short independent delta review.
- [x] Freeze a task-only commit, use the canonical staging release, configure only
  its nonsecret navigation URL, and verify served source, health, actual URL
  projection and unchanged Endpoint runtime. Record any unverified live SSO step.

Evidence directory: C:/Temp/worktime-inventory-followup-20261030.

Verification:31 backend tests passed after four expected RED failures;31 focused
shell/session frontend tests passed after staging-link RED. Both server and
frontend had separate production-only filters; both are now fixed. Fresh canonical
bundle plus4 Chromium scenarios passed (production/staging links, desktop/mobile,
real intercepted navigation without Referer, and logout). An intermediate browser
run used the stale main dist; rebuilding the main bundle fixed that evidence gap.
Root inspected desktop/mobile screenshots; mobile uses the existing horizontally
scrollable requester navigation. Workspace sanity and diff check passed. One
independent delta review found no blockers. Playwright MCP transport unavailable;
canonical Playwright CLI used. Context7 quota exhausted; official React conditional
rendering docs and existing conditional pattern used, with no dependency changes.

Outcome: commit19d53152f1b1da6330654d740d7c6993fe70a583 (9 files/no push) deployed
on .118, HD process267363/schema151. Exact39 runtime packages and six complete
durable identity/person/audit tables preserved; Endpoint10c/schema43 and runtime
263352/263407 unchanged. Only WORKTIME_PORTAL_URL changed to the staging portal.
Fresh PGDMP13,712,887bytes SHA
ba2cda2d88529b67f4364d410f34fa49491a65d860a9d88499c1085961bef0f1,
TOC verified, not restore-tested. Native projection accepts staging and rejects
production, strict HTTPS passes,16 served asset sizes/SHA match archive; index
matches after public runtime-config injection/whitespace normalization. Real
public login page renders with0 console errors/warnings. Authentication itself
was not performed; employee navigation remains fixture/native projection evidence.

The original canonical installation succeeded, but a diagnostic-only import path
omitted the shared project root and triggered rollback. OLD availability/env151
were independently verified; the original HOLD receipt is retained. Corrected
readonly projection passed before the reviewed owned-candidate activation, which
requalified full source/freeze and took a new backup. No package/migration replay.
Timeout uncertainty fences, actual schema checks and durable parent fsyncs were
reviewed; no production/Endpoint control changes or secret disclosure. Temporary
projection services collected automatically; deployed Helpdesk remains running.
Evidence: activation-result.json, served-assets.json and inventory-readonly.json
under C:/Temp/worktime-inventory-followup-20261030. Native notifications still
need the domain pilot host address/readiness requested from the user.
