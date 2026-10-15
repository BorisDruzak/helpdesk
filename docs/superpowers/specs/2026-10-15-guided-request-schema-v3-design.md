# Guided Request Studio schema v3

## Goal and boundaries

Extend the canonical Studio map from schema v2 to v3 with map-owned SLA profiles,
trusted queue directions, branch processing decisions, explainable composite rules,
complete JSON/YAML interchange and public catalog search. Retain historical v1/v2
definitions, pinned sessions, policy registries and the current ticket lifecycle.
Work in one feature branch. Staging and disposable tests are authorized; production,
changes to existing SLA/queues and publication of real services are excluded.

## Architecture

The strict definition adds `processing.sla_profiles`, `processing.routes`, explicit
`processing.defaults` and `assignment_mode: last_matching_branch`. SLA profiles use
positive bounded minutes with calendar/business time; business profiles reference
an active validated calendar. Directions reference active queues by canonical code.
Transition `processing` chooses route/profile and optionally whether approval is
required. `processing_facts` continues to feed the existing priority policy.

Revalidate retained answers before deriving decisions. Start with explicit defaults
and traverse selected edges in execution order. A later explicit assignment replaces
an earlier assignment; trace includes its source and previous value. Coordinates
have no execution meaning. Composite rules keep canonical `and/or/not`, explicit
first-match priorities and fallback. Missing answers stay unknown; the editor shows
paths that can skip a question and offers presence guards.

One trusted adapter feeds existing TicketRoutingService and TicketSlaService through
the request-template context in preview and create. The standalone SLA dictionary
uses the selected profile's targets for every priority; no global policy is created.
Remove inherited legacy SLA IDs so they cannot supersede the selected map profile.
Preserve selected processing through canonical policy overlays and lifecycle logic.
Approval retains canonical approver resolution and fails clearly when unavailable.

## Publication and persistence

Use existing bounded readiness traversal, source snapshots/locks, actor-bound
confirmation tokens, audit and immutable published versions. Validate all configured
queue/calendar references, including unused directions/profiles. Runtime repeats
availability checks. Migration 150 expands the immutable version check to 1/2/3,
rewrites no rows and refuses downgrade while v3 versions exist. Import remains a
validation/preview action and never publishes without the existing confirmation.

## UI and search

Admin's primary job remains authoring one map in explorer/canvas/inspector.
Processing settings contain named map profiles, durations/units/calendar selection,
queue pickers and explicit defaults. Branch results show next step, direction, SLA
and approval; logic supports groups/negation and all upstream question labels.
Testing uses server results, explains rule leaves/assignment sources, highlights the
route and supports comparing two runs. Preserve local-only employee preview.

Requester searches across the already authorized published catalog. Add a query to
the current catalog API and rank title/phrase/synonym/multiple tokens/prefix/limited
typo matches deterministically. Normalize Russian case, ё, punctuation, stems and
keyboard layout while preserving negation. Results directly open a confirmed entry,
with category, description, help mode and useful matching reason. Empty/loading/error
states and another-problem fallback remain understandable.

## Verification

Test strict contract/roundtrip/version compatibility, three-question branching,
overlap/unknown/specialized entrances, default/override trace, calendar validity,
queue deactivation, actual create versus preview, branch approval, catalog visibility
and search ranking. Run focused backend/frontend suites, build and scoped workspace
verification; then one independent risk review and exact-candidate staging browser
checks at 1366 and 1920. Prepare a draft PR with exact commands and limitations.
