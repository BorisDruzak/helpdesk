# Helpdesk Guided Request Studio v3 — frontend prototype

> Historical design prototype

This standalone prototype records the selected Studio v3 design. Architecture
notes below describe the implementation baseline at design time, not the current
Helpdesk runtime. For current service authoring, see
[the canonical guide](../../docs/UNIFIED_SERVICE_SCENARIOS.md).

Separate Product Design prototype. Production source, Git main and deployed services are unchanged. Runtime uses only local browser data; it never calls Helpdesk or Endpoint APIs. Fonts are vendored under their OFL licenses.

## Nine connected screens

| Screen | Local route | Main task |
|---|---|---|
| 1. Admin catalog | `/#catalog` | Search/filter precise employee problems; see shared scenario and its starting step |
| 2. Categories, items and entry points | `/#entries` | Create/edit categories and catalog items; choose a reusable scenario and initial node |
| 3. Visual Low-Code builder | `/#builder` | Read/pan/zoom/drag the shared graph, add a block, connect routes, open contextual inspector |
| 4. Block/question/condition settings | `/#settings` | Edit question choices, influences, instruction text, decision destinations and local advanced settings |
| 5. Processing | `/#processing` | Select existing routing, priority, SLA and approval policy references; inspect demonstration processing |
| 6. Interactive testing | `/#testing` | Enter from any catalog item; simulate answers and four safe diagnostic failures; test all routes |
| 7. Publication and versions | `/#publication` | Review readiness, changes and history; explicitly confirm a new local immutable version; restore to draft |
| 8. Employee catalog | `/#employee-catalog` | Search published items by title, description and synonyms |
| 9. Employee journey | `/#employee-session` | Follow a pinned published graph; resolve without ticket or confirm transfer to support |

Every screen is rendered individually at desktop size. `screens.html` presents separate 1440×1024 captures, one at a time, with additional dialog/empty/success states. It is not a collage.

## Walkthrough

1. Create a catalog item such as “Печатает полосами”. Select the existing “Проблемы с печатью” scenario and “Проверьте качество печати” as its first step.
2. Inspect its entry settings and permanent employee preview. Draft items are not available in the employee catalog.
3. Edit a question or instruction on the map or Settings screen. Local advanced settings belong to the selected block.
4. Choose published policy references on Processing. Values are fixtures, not a second policy/SLA engine.
5. Test each entry interactively; then run all demo paths. The baseline has 432 combinations (3 entries × 4 impact answers × 3 urgency answers × 3 results × 4 diagnostic failures). Adding a fourth entry creates 576 combinations.
6. Review publication changes, acknowledge safe diagnostic fallback and write a change summary. Confirm local demo publication.
7. Open the employee catalog. The new item is searchable and leads to its specialized first step. Continue to either resolution or support.
8. Restore an earlier version into a draft. Publication history stays immutable and a new test is required.

Use “О прототипе и ограничениях” → “Начать с исходных демоданных” to reset local demo edits. Browser localStorage key is versioned. Autosave failures are shown; this is not a server autosave/revision implementation.

## Architecture and existing backend limitations

Verified against Helpdesk main `bb8c521faaf76eea01119f314f68fecdeb34cefb`, GitNexus, `server/docs/SERVICE_CATALOG.md`, `server/docs/GUIDED_REQUEST_SCENARIOS.md`, `request_scenario_models.py`, `request_scenario_runtime.py`, `request_scenario_processing.py` and `helpdesk_policy_runtime.py`.

Existing canonical chain remains:

`Service → Offering → RequestTemplate/FormSchema → published policy references → canonical ticket creation`.

For printing, the existing canonical offering is `workplace.printer_issue`, with request template `printer`. The prototype does not create an Offering or Service per symptom.

### Target entry model (not implemented in backend)

`Category → CatalogItem → versioned EntryPoint → ScenarioVersion + entry_node → existing Offering/template/process binding`.

- “Не печатает” starts at the common impact question.
- “Застряла бумага” starts at a safe jam instruction.
- “Бледная печать” starts at quality guidance.
- Specialized paths converge on the same impact/urgency questions, guidance, safe diagnostic fallback, resolution check and support handoff.
- A catalog item has a title, synonyms, category, availability and a reference to a shared scenario/starting node. It does not own a copy of diagnostic logic.
- Entry binding must be published/versioned atomically with the applicable graph. Starting nodes must be reachable, compatible with the offering/template and able to collect all mandatory facts before submission. Restricted item/category access must intersect existing service/offering/ancestor visibility.

Today `RequestStudioScenario` is bound to one Offering and its definition has one `entry_block_id`. Immutable versions have at most one published version per Offering. The independent multi-entry catalog-item relation shown here is absent. Its implementation requires a separately reviewed additive domain/DTO/API/persistence/publication contract, not client-side selection of arbitrary node IDs and not scenario clones. No such changes are made here.

Current server schema bounds include 256 blocks, a 1 MiB definition, 64 KiB answer input, bounded typed conditions and a 512-variant readiness coverage cap. The local demo's 576 paths for four entries is a demonstration count, not a claim that the existing server would admit that definition. The future multi-entry readiness contract must cover every entrance, deduplicate shared work where valid and retain fail-closed coverage limits. UI layout positions are prototype metadata, not fields to forward into the strict existing Scenario DTO.

### Facts, diagnostics and trust

- `reportedSymptom` is the chosen catalog label; `answers` are employee reports. Neither is placed in `verifiedFacts`.
- Question influence toggles demonstrate `diagnostic_input`, impact, urgency and routing roles. Diagnostic inputs remain employee reports.
- Existing pre-ticket diagnostic execution is `unavailable`; simulator failure values are unavailable/denied/timeout/capability_absent. There is no success fixture, dispatch, real consent grant, attachment staging or operation.
- Self-service success is phrased as the employee's confirmation. The automatic cause remains unknown.
- Missing/unknown answers do not invent facts. Required policy inputs cannot be bypassed by specialized entry or support escape.

### Existing policy runtime

Production must resolve active published policy references through the current registry/runtime, including source inheritance, current queue availability and mandatory facts. Scenario policy references originate in a server-loaded trusted version, not requester JSON. Existing ticket creation repeats authorization, policy, routing, SLA/OLA and approval checks.

`processing()` in this prototype is explicitly a bounded display fixture, not production business logic. Its “whole department” example selects printer specialists through a demonstration routing policy; its impact/urgency example changes a displayed priority. SLA deadlines come from the chosen fixture policy. Never port these calculations into a parallel SLA engine.

The current policy contract points to current published policies rather than frozen policy versions. A production version-readiness preview must bind its source snapshot and recheck stale/invalid references. The local fingerprint check in this prototype is not a replacement for server revision compare-and-swap, role/audit controls, locked snapshots, source-bound confirmation tokens, expiry or single-use publication.

### Deliberate prototype bounds

One printing scenario/service binding; a bounded category hierarchy; one-choice questions; question/instruction insertion; editable decision destinations; reference selection of policies. No authentication, real API integration, production mutations, live diagnostics or full authoring of all backend field kinds. Browser refresh returns to the screen route; in-flight demo answers are ephemeral. A session pins a published snapshot for the mounted journey. Server-owned resumable/expiring sessions require the existing backend contracts.

## Verification

- `node --test tests/domain.test.mjs` — 16 invariant tests.
- `npm run build` — Vite and template packaging.
- Browser workflow and individual desktop captures — recorded in `design-qa.md` and `evidence/`.
- `python scripts/verify_workspace.py --workspace .` and `git diff --check` — run from repository root.

The dev server is bound to `127.0.0.1:4173`. Start command, if needed in a later session: `npm run dev -- --host 127.0.0.1 --port 4173 --strictPort`.
