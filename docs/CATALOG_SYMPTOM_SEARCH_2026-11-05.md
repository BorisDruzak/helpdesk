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

Staging exact-SHA install, strict HTTPS/source/count checks and current API
before/after evidence are recorded after canonical deployment. Private evidence
directory: `tmp/catalog-symptom-search-20261105`. Full CI and production are outside
scope. Live admin session has an incomplete profile, so ordinary requester results
are verified by the real public API and browser fixture without changing identity.

Shared HEAD/index and unrelated dirty work are preserved. Candidate is frozen
through a private index on top of `ab80b1a2aa0052f0c8f3a875bd74c931761bec2b`.
