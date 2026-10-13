# Unified service scenarios

Approved product direction: service creation always opens the scenario map. The
user approved conversion of existing forms, preserving their data and processing,
and explicitly requested sequential implementation without further approval stages.

## Source and compatibility

The existing scenario draft/version JSON is the only editable question and route
source. Schema v2 adds typed processing effects; v1 remains executable for pinned
sessions. The server derives the canonical form-validation projection from the
server-loaded v2 map and its visited, visible fields. Existing RequestTemplate
bindings supply processing configuration, never an independent v2 question set.
No new tables, configuration store, or priority engine are introduced.

New service creation generates the internal Offering binding transactionally.
Processing defaults come from the selected section's configured template or an
existing published offering/template in that section. Missing/ambiguous defaults
produce a clear error instead of silently inventing processing policy.

## Authoring

Actor: administrator. Primary job: create a service by assembling its map.
Archetype: existing workbench (library, canvas, contextual inspector).
Create service opens an empty local v2 draft immediately and inherits the selected
section/category. Saving creates its internal binding on the server. Start is
visible, unique and nondeletable; Start-to-block edges are catalog entrances, not
runtime transitions. Names are edited on the map. New entrances inherit the map
category; historical entrance overrides are preserved for compatibility.

The ordinary palette has five kinds: question, instruction, condition, resolution
check and result. Review is generated at submit; existing review/diagnostic nodes
remain supported. Existing diagnostics remain unavailable until their backend
contract is enabled. Connections are authored on the map, with keyboard-accessible
connection controls in a secondary menu, not duplicate primary selectors.

## Processing

Question answer mappings and selected transitions may contribute typed impact
(single_user/multiple_users/department), urgency (can_work/degraded/blocked), and
importance (normal/important/critical). The highest contributed value per dimension
wins along the current retained traversal. Hidden/unvisited answers and branches
do not contribute. The server adapter feeds values into the existing effective
priority policy's input fields; no client priority/deadline authority is accepted.
An effect whose effective policy has no corresponding input binding blocks
publication with an explicit issue. Existing policy matrix and SLA runtime compute
the result; simulation displays it.

## Declarative interchange

JSON and YAML encode the same versioned definition, including entries, fields,
conditions, effects, outcomes, policy refs and layout. Server parsing is bounded,
rejects duplicate keys, aliases, custom tags, unsupported versions and non-finite
numbers. Import validates the DTO and graph and returns a preview; saving uses
the existing revision/CAS path. Existing identity/binding cannot be silently
replaced by import. Export and import live under an advanced menu, not a raw editor
in the main authoring flow. YAML uses PyYAML SafeLoader with stricter guards.

## Conversion

Conversion is idempotent per existing Offering. It resolves the canonical current
form, converts fields/options/validation/visibility/roles into a v2 map, and retains
the Offering/template and policy bindings. Unsupported trigger, condition, field,
layout or configuration semantics are explicit blockers. Existing maps and drafts
are never overwritten. Conversion creates a draft; an existing published service
switches only through readiness and the existing confirmed publication path.
No old form/template/version is deleted. Existing tickets and pinned sessions
continue on their old snapshots. Bulk conversion reports ready/skipped/blocked
items and does not publish automatically.

## Acceptance

Real browser: catalog -> create -> visible Start -> question -> named entrance ->
condition -> result -> save -> simulate -> publish. Verify independent dragging,
delete/undo, multiple entrances, invalid import with no mutation, JSON/YAML round
trip, auto review and resulting processing. Verify 1366x768 and 1920x1080, console,
no horizontal body overflow and visible primary actions. Backend tests cover strict
parsing, source projection, effects, revision conflict, conversion and pinned v1
compatibility. Staging only; no production or Endpoint changes.
