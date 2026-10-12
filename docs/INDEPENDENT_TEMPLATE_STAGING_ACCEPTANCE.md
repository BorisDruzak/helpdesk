# Independent processing template: staging acceptance

Date: 2026-10-12. Application commit: **2f2a2ec93b204466b1cf190308506262d2fb31e9** —
`feat(studio): create independent processing templates`.
Source: `codex/guided-request-studio-v2`; target: `main`; PR 41 remains draft.
Scope: approved isolated Helpdesk staging only. Production is excluded.

## Problem and behavior

Browser inspection confirmed that new service creation required an existing
published template but offered no creation action. The active FormsBuilderWorkspace
only edited existing pack forms. The template purpose was insufficiently explained.

Service creation now explains that a template supplies ordinary questions and
processing rules. **Создать шаблон** opens `/app/admin/forms/new` in a separate
tab. The new page permits its own title/description/type, text/long-text/checkbox
questions and selection of existing published processing-policy references.
Explicit confirmation publishes one new template/form schema through canonical
`POST /api/web/admin/helpdesk-model/request-templates/publish-from-form`, with
`publish_policies=false`. It does not rewrite a shared form pack or existing rules.
A random stable key belongs to the new template; no machine key entry is required.

Admin role plus `admin.forms.publish`, dirty navigation, query retry/error and
pending-mutation controls are preserved. Policy versions are deduplicated by code.
**Обновить список шаблонов** refreshes choices without resetting the local service
values. Services and optional guided scenarios remain separate objects.

## Verification

- Installed application SHA: 2f2a2ec93b204466b1cf190308506262d2fb31e9; service active.
- Installed web digest: `80891a62f3109b5120ceb21c167af48b0308bab61a3a07d755e98b257c690892`.
- [Exact candidate CI 38260933737](https://github.com/BorisDruzak/helpdesk/actions/runs/38260933737):
  successful workflow_dispatch, all 18 canonical layers and Endpoint contract job
  passed. Suite catalog/order, return codes, no timeouts and full merge gate were
  verified from the downloaded artifact. Summary SHA256:
  `47b003fa6340a0a9cd7ce18cf96bce6a143f4e9b370022ad0e5701d8cf8f88a3`.
- `npm --prefix webapp test -- --maxWorkers=2`: frozen 118 files / **682 tests PASS**.
- `npm --prefix webapp run build`: frozen fresh build/typecheck PASS.
- `npx playwright test` in webapp: **110 fixture cases PASS**, including four new
  template-creation viewports. Fixture evidence is separate from actual staging.
- `python scripts/verify_workspace.py --workspace .`; `git diff --check`: PASS.
- Exact-source Semgrep 1.178.0 security-audit/secrets: 17 existing SAST findings,
  zero task-file findings, zero secrets/errors. Source archive digest verified.
- Independent source/contract/admission review: findings resolved, no blockers.
- GitNexus query/context preceded source exploration; canonical handler, schema,
  publication and requester registry consumption were verified against source.
  Context7 closest Playwright docs verified the new-tab event API.

## Actual browser flow, without fixtures

Strict HTTPS/certificate checks and separate protected synthetic admin/requester
contexts were retained. New data mutations used browser UI only.

1. Entered a service title and description in the published Mail section. Followed
   **Создать шаблон** into a separate tab. At 1366x768, 1440x900, 1920x1080 and
   820x1180, the primary action remained visible and there was no horizontal
   overflow. Separate installed probes also checked expanded policy settings;
   browser/HTTP errors were absent.
2. Created **Тест шаблона почты 20261012143808 — форма**, with **Адрес почты** and **Что не работает
   в почте?**, selecting existing published closure/visibility references.
   Published through the explicit UI confirmation. Returned template/schema keys
   and title matched the outbound owned form.
3. Returned to the service tab. Title/description remained unchanged. Refreshed
   the list and selected the newly published template. Created and published the
   bound service; canonical response title, service, code and template binding
   were checked before publication.
4. Opened the service as the synthetic requester, with a complete profile and
   zero devices. Its new question fields rendered. The runtime also adds the
   existing common impact/continuity/importance questions; their server authority
   was preserved. Answered those questions, submitted one actual synthetic
   request and opened its details, where the owned answers were visible.

Final requester execution: zero browser errors, failed requests or HTTP errors.
The first helper omitted common priority questions and stopped at local validation
before a ticket POST. It was resumed using the same published template/service,
without duplicates; failed helper evidence remains separate. Final receipt flags
are limited to the resumed requester execution. Earlier template/service creation
is bound to its logs/screenshots and canonical records in the hashed evidence chain.
No new application change or repeated publication was required for that resume.

## Owned records and evidence

Retained on staging for inspection:

- Template: `template_1792b61daf914ce5afcd6dd83be9c46f`.
- Offering: `mail.scenario_d9e6c4b32c1a43e5bf83d132a0ba2a1d`.
- Ticket: `T-000057` / `a706494a-db5d-4066-bce8-0342eba860d1`.

One template, one service and one synthetic ticket were created by this follow-up.
The user's existing service, scenarios and browser tabs were not modified.
The separate creation page is open in the in-app browser.

Ignored evidence directory:
`artifacts/browser_checks/template-create/2f2a2ec93b204466b1cf190308506262d2fb31e9/`.
It contains viewport/expanded-settings, publication, preserved service, requester
form/answered facts and ticket-details screenshots. The final receipt is
`receipt.json`. `artifacts/template-create-evidence-chain.json` binds stage logs,
proofs and screenshots by SHA256 to the same installed SHA and owned identifiers.

## Limits and delivery

The new creation page offers text, long text and checkbox questions, and reuses
existing published processing rules; it is not a new policy-rule designer or a
standalone-template edit/version-history workbench. No post-creation editing via
the legacy pack-only constructor is claimed by this follow-up.

Backend/schema/dependencies/workflows/Endpoint contracts are unchanged. No real
Endpoint/fleet operation or release acceptance is claimed. Staging remains active
by user request. Sonar remains deferred by explicit user instruction; no fresh
Sonar gate or coverage percentage is claimed. Production rollout and main merge
are excluded. The canonical installer rebuilt the frontend; byte equivalence to
the separate CI bundle is not claimed. Later docs-only acceptance commits do not
represent new application CI/deployment candidates.

## Files in the implementation commit

- `PLANS.md`
- `docs/GUIDED_REQUEST_STUDIO_ADMIN.md`
- `server/docs/CODEMAP.md`
- `webapp/src/app/router.tsx`
- `webapp/src/features/request-template-studio/scenario-offering-form.test.tsx`
- `webapp/src/features/request-template-studio/scenario-offering-form.tsx`
- `webapp/src/pages/admin/template-create-page.test.tsx`
- `webapp/src/pages/admin/template-create-page.tsx`
- `webapp/tests/guided-studio.spec.ts`
