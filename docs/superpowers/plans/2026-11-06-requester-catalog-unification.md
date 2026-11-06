# Requester catalog unification and staging rollout

Goal: apply the approved recommendations in REQUESTER_CATALOG_REVIEW_2026_11_06.md
and leave the tested result running on Helpdesk staging.

Architecture: retain the canonical published catalog and server-side permissions;
group search rows by offering, rank service-name queries before generic symptoms,
and use one visible catalog/form navigation. Preserve legacy templates and history
while retiring only verified test publication and mapping equivalent entrances.
No dependencies, new database schema or Endpoint changes.

- [x] Inspect fresh staging identity/catalog/forms; inventory duplicates against fields and routing.
- [x] Add regressions and implement grouped, concise search and uniform creation/navigation; anonymized aggregate measurement only.
- [ ] Verify focused backend/frontend, build and browser desktop/mobile; independent review.
- [ ] Freeze task-only commit over actual staging baseline, verified backup, canonical guarded deployment, live browser/source/health/data verification.

Constraints: staging osn-admin@192.168.101.118 only; preserve concurrent dirty work,
current deployed schema156 and later changes. No production actions, hard deletion,
credential exposure, auth weakening or independent replacement workflow engine.
Record exact SHA, commands, data changes, rollback path and limitations.
