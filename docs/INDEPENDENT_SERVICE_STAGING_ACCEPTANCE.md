# Independent service creation: staging acceptance

Date: 2026-10-12. Scope: approved isolated Helpdesk staging only. Production is
excluded and was not contacted or changed by this follow-up. Staging remains active
for the requested inspection. PR 41 remains a draft against main.

## Behavior

The catalog explains that a service is an employee-facing card and a scenario is
optional guided help for that service. **Создать услугу** opens a separate page
(`/app/admin/request-template-studio/services/new`). Saving creates only a service
(offering) draft and opens its dedicated page. Explicit standalone publication
makes its existing ordinary form available; a scenario can be created afterwards.

Service selection in scenario authoring explains the section/subcategory relationship.
Essential transitions are visible under **Что делать дальше**. Missing-transition
simulation errors identify the affected step and offer **Исправить шаг**. Server
validation and canonical publication/role/audit controls remain authoritative.

## Exact candidate and checks

- `1f022cbd2464ae4ecabd36a07440bd4880144f96` —
  `feat(studio): create services independently of scenarios`.
- `519cc29618fd293fa0fba40885d6868a1aca2831` —
  `test(studio): assert visible transition issue navigation` (one test file).
- Installed application candidate: **519cc29618fd293fa0fba40885d6868a1aca2831**.
- Installed web digest: `4225219362b680a4b4bedc4f4a257acd0d631f2eecc54e14e6a4219ee5f89277`.
- [Exact candidate CI run 38251065696](https://github.com/BorisDruzak/helpdesk/actions/runs/38251065696):
  success, all 18 canonical full-CI layers executed successfully with isolated
  PostgreSQL/fresh migrations; Endpoint contract acceptance also passed.
- Full-CI summary SHA256:
  `ad09f62b8022faf9880d84ce0d73438ca91e42ce6ddc81c524605f3ba9d30b75`.
- `npm --prefix webapp test -- --maxWorkers=2`: 117 files / 678 tests passed on
  frozen 519cc296 source.
- `npx playwright test` in webapp: 106 fixture cases passed; includes four
  standalone creation cases. This is separate from the installed browser evidence.
- `npm --prefix webapp run build`: typecheck and fresh build passed.
- `python scripts/verify_workspace.py --workspace .` and `git diff --check`: passed.
- Semgrep 1.178.0 at exact 519cc296: zero findings in task files, zero secrets/
  scan errors; 17 pre-existing repository SAST findings remain.
- Independent source review: no remaining application blockers. Docs-only
  acceptance updates do not change installed application bytes or represent a new
  application CI/deployment candidate.

## Actual browser flow, without fixtures

Strict HTTPS and certificate validation were preserved. Synthetic admin and
requester accounts were reused; credentials were supplied only through protected
runtime input. All product mutations below were performed through browser UI.

1. Opened standalone creation at 1366x768, 1440x900, 1920x1080 and 820x1180:
   primary save action visible; no horizontal overflow.
2. Created **Тест отдельной услуги 20261012131111** in **Рабочее место**, using the
   published printer processing template. Saving created no scenario. Published
   the service through its explicit confirmation, then opened its ordinary form
   as the synthetic requester.
3. Created its scenario and saved an instruction without transitions. Server
   rejected simulation with SCENARIO_INVALID/missing_fallback; the UI explained
   the issue and **Исправить шаг** opened the visible transition editor.
4. Built and saved a valid graph through the UI:
   instruction → resolution check; **Да** → finish; **Нет/Не знаю** → canonical
   printer questions → review → submission. Canonical fact keys, choices and
   processing roles came from the published form, not a fixture. Positive
   self-resolution simulation completed successfully.
5. Publication correctly blocked absent closure/visibility policies. Selected
   existing published staging pilot policies through the processing step. Fresh
   publication readiness checked **161 outcomes**, with no blockers. Published
   version 1; subsequent canonical detail and visible service card confirmed it
   enabled. No validation bypass or deployed-file patch was used.
6. Requester completed the positive path and finished without a ticket. In a
   fresh browser tab, the requester followed the support branch, answered the
   questions, reviewed them, obtained server processing preview and created one
   actual synthetic ticket. A separate read-only browser visit opened that ticket
   and verified its owned marker/answers.

Final requester execution has zero browser errors, failed requests or HTTP errors.
The earlier deliberate missing-transition HTTP 400 is a negative test, not an
unexpected runtime failure. This scenario contains no diagnostic block or
Endpoint operation; physical Endpoint/fleet acceptance is outside this follow-up.

## Owned records and evidence

Retained for inspection on staging:

- Offering: `workplace.scenario_ba5771e4a61e4970bb42b8469c9793f6`.
- Scenario: `82ac0260-bedd-4013-b667-a35259fd7838`, published version 1.
- Synthetic ticket: `54b4f1e0-a263-433d-ae9c-997bba98d999`.

The existing user scenario and browser draft were not modified. There is one
new service, one new scenario and one synthetic ticket from this follow-up.

Ignored local evidence is under `artifacts/browser_checks/standalone-service/519cc29618fd293fa0fba40885d6868a1aca2831/`:
creation screenshots, ordinary service/form, transition error, simulation success,
publication readiness, requester finish, processing preview, ticket creation and
ticket details. `receipt.json` records only final requester-run observations;
`ticket-details-proof.json` verifies the separate read-only ticket visit.
`artifacts/standalone-service-evidence-chain.json` binds earlier logs/screenshots
by SHA256 to the same installed SHA and owned IDs.

The browser helper was resumed without creating duplicate records: its initial
selector expected the raw offering code instead of the existing composite option
value; the publication-link wait was too short for the 161-outcome assessment;
reusing a completed session in the same tab required finishing and opening a new
tab for the support case. Failed helper logs are retained separately. Earlier
creation/negative-test assertions are not claimed as executed in the final
requester receipt. Screenshots plus the corresponding stage logs preserve the
combined execution evidence. The invalid helper instruction→finish graph was
caught by independent review before any scenario creation and replaced with the
canonical resolution-check/support graph.

## Limits

Sonar remains **deferred by the user's instruction**; no fresh Sonar coverage or
production enablement claim is made. Production rollout/merge and broader fleet
acceptance are not authorized by this staging result. Backend code, schema,
dependencies, workflows and Endpoint contracts are unchanged in this follow-up.
The installed frontend was built by the canonical installer; its digest is not
claimed byte-identical to the separately generated GitHub artifact.

## Files in the implementation commit

- `PLANS.md`
- `docs/GUIDED_REQUEST_STUDIO_ADMIN.md`
- `server/docs/CODEMAP.md`
- `webapp/src/app/router.tsx`
- `webapp/src/features/request-template-studio/offering-details.tsx`
- `webapp/src/features/request-template-studio/offering-publication.test.tsx`
- `webapp/src/features/request-template-studio/offering-publication.tsx`
- `webapp/src/features/request-template-studio/scenario-api.ts`
- `webapp/src/features/request-template-studio/scenario-block-builder.test.tsx`
- `webapp/src/features/request-template-studio/scenario-block-editor.tsx`
- `webapp/src/features/request-template-studio/scenario-issue-navigation.ts`
- `webapp/src/features/request-template-studio/scenario-offering-form.test.tsx`
- `webapp/src/features/request-template-studio/scenario-offering-form.tsx`
- `webapp/src/features/request-template-studio/scenario-purpose.test.tsx`
- `webapp/src/features/request-template-studio/scenario-purpose.tsx`
- `webapp/src/features/request-template-studio/scenario-simulation.test.tsx`
- `webapp/src/features/request-template-studio/scenario-simulation.tsx`
- `webapp/src/features/request-template-studio/scenario-wizard.tsx`
- `webapp/src/features/request-template-studio/unified-catalog.test.tsx`
- `webapp/src/pages/admin/request-template-studio-page.test.tsx`
- `webapp/src/pages/admin/request-template-studio-page.tsx`
- `webapp/src/pages/admin/service-create-page.test.tsx`
- `webapp/src/pages/admin/service-create-page.tsx`
- `webapp/tests/guided-studio.spec.ts`

The second commit changes only
`webapp/src/features/request-template-studio/scenario-issue-navigation.test.tsx`.
