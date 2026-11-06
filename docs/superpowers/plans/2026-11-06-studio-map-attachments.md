# Studio attached policies and direct manipulation plan

> Use superpowers:subagent-driven-development for coherent work units and independent review. This continues the approved full Studio implementation and six explicit follow-up comments.

Goal: direct manipulation of map editors/transition cards, clearly labelled question help, a top-level employee preview, attached SLA/routing settings and inherited/explicit final route+SLA.

Architecture: existing ReactFlow/Tiptap and v4 JSON; no new dependencies, DB schema version or automatic legacy conversion. New v4 modifier kinds `sla_attachment` and `routing_attachment` have `attached_to` target block id, no transitions. Existing `sla` retains executable legacy semantics. One attachment of each kind per target; conflicts are rejected. New route settings use existing map routes or published routing policies. Final submit_ticket supports explicit route/routing_policy_ref analogous to existing sla_profile/policy_ref. Inheritance by omission. Server replays visited blocks, applies attached settings, then selected edge assignments; final attachments precede explicit terminal assignments. Unvisited settings never contribute. Impact/urgency/importance retain existing aggregation, not a new numeric sum.

UI: new SLA/Route cards connect to ordinary blocks by visually distinct dashed setting links. They are not employee steps or ordinary route edges. Keep empty unattached drafts editable with publication issues. Preserve all existing published definitions, pinned sessions and original user tabs. Old sequential SLA has an explanatory legacy label; no silent migration.

Transition settings expand at their label on the map, in the same editable card style as nodes. Drag empty card space with grab/grabbing cursor; inputs/contenteditable/buttons remain usable. Resize at every edge/corner with invisible hit zones and correct cursor; remove dimensions/footer control, keep keyboard accessibility. Local size/offset preferences do not dirty business definition. Native ordinary map-node position persistence remains unchanged. Full editors may move within available viewport. A visible question-help label/placeholder explains its employee-facing purpose, and requester preview renders edited content. Top actions include `Как у сотрудника`, opening the existing full page preview from the current/entry block without requiring a saved draft.

Tasks:
- [ ] Snapshot all relevant code before edits; preserve dirty checkout/index, use actual staging6aefbc4cba43fd71679382d775b5e2f1cf0a4252 as release base.
- [ ] Backend/contract worker: DTO/schema/runtime/submission/validation/readiness/fragments and focused regressions for attachments and final route override.
- [ ] Gesture worker: editor border resizing/blank-space dragging, edge-anchored editor support, question help label, tests.
- [ ] Modifier UI worker: new editors/palette/model helpers/terminal route and summary integration, tests; parent owns canvas/workbench/wizard wiring.
- [ ] Parent: wire canvas modifier edges/ports, anchored edge editors, top preview, dirty/result guards and browser fixture acceptance.
- [ ] Independent review, bounded corrections, focused/backend/frontend/build,1366/1920 browser verification.
- [ ] Task-only frozen staging release, verified backup/restore, install through canonical workflow, real unpublished test copy, compare original row hashes. Production untouched; no user draft mutation/reload.
