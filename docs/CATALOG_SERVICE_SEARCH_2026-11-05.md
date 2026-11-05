# Service-name search and missing-service intake — 2026-11-05

User scope: search the actual service catalog, add Электронный бюджет and ЕИС,
and allow «Не знаю» when nothing matches. Staging only, preserve existing
publication/draft/ticket history and earlier requester decision controls.

## Observed causes

The live public catalog has31offerings but search indexed only their entrance
texts when entrances existed. «электронная подпись» therefore found only an ЕСЭД
problem and missed the signature service itself. Электронный бюджет and ЕИС did
not exist. The advertised fallback was retired `other.unknown`, absent from the
current offering list, so the UI could not show its fallback button.

## Changes and checks

Search emits additive service rows for public offering/section names, retaining
entrance ranking and bounds. Selecting a service browses its problems without
starting a remembered scenario. Explicit configured fallback metadata resolves
only to one public executable entrance under a real public parent. The UI offers
«Не знаю / моей услуги нет в списке» with that exact entrance key.

The new guarded publication helper builds two maps from the current published
information-system intake, inheriting routing, SLA and policy refs. Each has
login/signature/system-error entrances; the existing Other `not_found` entrance
becomes fallback. Publication uses canonical audited services, sorted service
locks before source freeze, an admin/actor check and a fresh source fingerprint.

Verification: search/public-parent/definition tests and component/browser checks
pass locally; exact commands, release identity and data publication evidence will
be completed after canonical staging acceptance. No new dependency or schema.
Full CI and production publication are outside scope.

Private evidence: `tmp/catalog-service-search-20261105`. The source working copy
contains earlier committed requester-control changes from another branch; freeze
this task on top of `1a341d05dcd8b89b10891d3ad8447e59ec865efe` with a private index
so those installed controls and unrelated shared staging are preserved.
