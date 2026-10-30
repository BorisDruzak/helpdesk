# Environment-bound WorkTime navigation implementation plan

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
- [ ] Freeze a task-only commit, use the canonical staging release, configure only
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
