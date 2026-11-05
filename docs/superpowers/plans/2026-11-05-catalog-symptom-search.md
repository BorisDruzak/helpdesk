# Catalog symptom search implementation plan

**Goal:** ordinary failure phrases find relevant published services across the catalog; a named device/system narrows results.

**Design:** extend the existing deterministic, requester-safe search with a small Russian symptom vocabulary (failure, startup, opening, login, printing, signing, connection, slowness). Recognized phrases are matched as intent; remaining words must match the offering/problem context. Generic symptom-only queries interleave offerings so one service cannot fill the page. Existing literal ranking, positive/negative distinctions, bounds, ACL projection and explicit entrance choice remain. Show the offering name on problem results. No new dependency, data publication, schema or external service.

**Constraints:** staging only; preserve profile guards, existing catalog/history and shared checkout/index. Freeze on private branch/index from `ab80b1a2aa0052f0c8f3a875bd74c931761bec2b`; do not stage unrelated dirty work.

- [x] Reproduce current misses on the published catalog snapshot; add failing phrase/diversity/named-service/negation/bounds regressions in `server/tests/test_service_catalog_search.py`.
- [x] Implement bounded intent matching and offering interleaving in `server/tickets/service_catalog_search.py`; expose additive `offering_title`, render it in requester search and cover it with a component regression.
- [x] Verify focused Python/UI tests, build, workspace sanity and browser viewports with actual search-produced results; review the narrow diff and update catalog/CODEMAP docs.
- [ ] Freeze exact source, verified staging backup, canonical immutable install, source hash/health/count/API checks. Keep staging active for the user's requested changes; record live/fixture evidence separately.

**Review focus:** do not match positive actions to negative symptoms; do not lose a device/system noun while expanding intent; no admin/draft inputs; no duplicate-heavy generic page; broad unknown queries remain empty and use the explicit existing fallback.
