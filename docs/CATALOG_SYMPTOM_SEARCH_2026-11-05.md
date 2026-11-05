# Requester symptom search — 2026-11-05

User request: make ordinary phrases such as «не работает» and «не включается»
find different relevant services. Continue the approved isolated staging work.

## Cause and change

The existing search matched literal/stemmed words within one field. It did not
connect equivalent failure/startup/login/opening phrases, and a service with many
matching entrances could fill the page. The installed public catalog snapshot
returned only one offering for «не включается» and none for «не включается принтер».

The pure public-catalog ranker now recognizes a bounded set of explicit Russian
failure phrases. Other device/system words remain mandatory context; phrases
containing internet/network retain that entity. Complete literal matches keep
priority; specific error phrases do not expand into all errors. Symptom-only
queries interleave offerings before repeating one and reject unrelated word
fragments (e.g. account-creation instructions mentioning work and passwords).
A named offering with no exact symptom entrance remains browsable as a service.
Problem results expose additive `offering_title`, displayed alongside category.

Files: `server/tickets/service_catalog_search.py`, its backend tests;
`webapp/src/features/requester/catalog-search.tsx`, API type and component tests;
`webapp/tests/catalog-service-search.spec.ts`; catalog/CODEMAP docs, this report,
implementation plan and the task's PLANS section. No dependency, schema, catalog
publication, auth/actor/profile change or Endpoint contract change.

## Verification

- Focused Python search/public-contract/publication-helper tests: 53 passed.
- Requester search/entrance/new-request component tests: 34 passed.
- Webapp build and `python scripts/verify_workspace.py`: passed.
- Browser search spec at 1366x768, 1920x1080 and 390x844: 3 passed. It feeds real
  Python search results from a synthetic public catalog into the UI fixture;
  checks broad/startup/named queries, offering labels, explicit service/entrance
  selection, unknown fallback, no ticket writes, no console errors or overflow.
- Independent review found network entity loss, unrelated setup promotion and
  suppression of specific literal errors; regressions observed red then green.

## Staging acceptance

Installed `17327fbc981ba1d3261fa0a77f0fb37b863b8550` —
`fix(catalog): match failure phrases across relevant services`, 11 files listed
above. Branch `codex/catalog-symptom-search`; canonical immutable installer rebuilt
the exact Git archive and frozen-lockfile frontend bundle. All 6 source/test hashes
match the committed files. Independent review's final narrow check has no findings.

Verified backup SHA256: `548bb9b283489ce44ed190ba0efe94939c5a051699cfbb715008335bff5a2d42`.
Schema remains 155. Strict hostname/CA HTTPS health returns 200 for Helpdesk and
Endpoint; all 3 staging services are active. Counts are unchanged: 76 tickets,
18218 events, 6 artifacts, 160 users and 44 people. Public catalog before/after is
identical; this task performs no map publication or data migration.

Real API unique-offering counts within the bounded result page:

| Query | Before | After |
|---|---:|---:|
| не работает | 13 | 20 |
| не включается | 1 | 7 |
| не запускается | 4 | 7 |
| не могу войти | 2 | 13 |
| ошибка входа | 5 | 13 |
| не включается принтер | 0 | 2 printer services |

`нет интернета`, `пропал интернет` and `нет сети` stay within the network offering;
named ЕИС and Электронный бюджет stay within their respective offerings. An unknown
device remains empty, preserving explicit fallback. All returned rows have the
offering label. Private receipts: `before.json`, `after.json`, `installed.json`,
`backup.json`, `deploy.log` and browser screenshots under
`tmp/catalog-symptom-search-20261105`.

Exact checks: `python -m pytest server/tests/test_service_catalog_search.py server/tests/test_service_catalog_contract_no_db.py scripts/test_helpdesk_catalog_service_search.py -q`;
`pnpm --dir webapp test src/features/requester/catalog-search.test.tsx src/features/requester/scenario-entrances.test.tsx src/pages/requester/new-request-page.test.tsx`;
`pnpm --dir webapp build`; `python scripts/verify_workspace.py`;
`PC_CLIENT_WEBAPP_E2E_PORT=4189 pnpm --dir webapp test:e2e tests/catalog-service-search.spec.ts --output=../tmp/catalog-symptom-search-20261105/browser-final`;
private-index diff check. Existing Authlib deprecation and fixture chunk-size
warnings remain; no failing check is hidden.

Full CI and production deployment are outside scope. The live admin session has
an incomplete profile, so ordinary requester results were verified by the real
public API and browser fixture without changing identity. Staging remains running
for the requested user testing. The curated vocabulary is bounded, not arbitrary
natural-language interpretation.

Shared HEAD/index and unrelated dirty work are preserved. Candidate is frozen
through a private index on top of `ab80b1a2aa0052f0c8f3a875bd74c931761bec2b`.
