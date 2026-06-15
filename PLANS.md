## Active Work: Knowledge Platform Refactor — Production Knowledge Base

Status, 2026-06-15: Knowledge Platform refactor is partially complete. K1 is implemented and hardened: Knowledge Sections exist, section metadata has documented owners/readers, contradictory section policies are rejected, and the UI has clear empty/archive/validation states. K2/K3 are closed on the core code side: Knowledge Studio uses a simplified one-save authoring flow, review/version/manual segmentation are hidden from default UI, and articles can be linked to Help Desk service/offering/request-template context with enforceable binding surfaces. K4 is partially implemented: RAG eligibility exists through article metadata and section `allow_rag`, and retrieval filters candidates by audience and RAG policy. K5 operations dashboard product pass is implemented in the current slice: Knowledge Ops summary action queues are rendered as Russian-first actionable queues with fixing routes, quick transitions and hover hints. K6 import alignment is implemented, deployed and live-checked on the stand for commit `485969d6`; evidence is under `artifacts/browser_live_validation/knowledge-import-k6-485969d6-20260615/`. Remaining work is focused on K7 settings consistency, K8 graph simplification, stale mojibake cleanup across older plan/docs/tests, and live evidence for later UI slices.

Progress, 2026-06-15: K2/K3/K4 backend production-correctness slice is implemented and live-checked on the stand for commit `c4d6c54c`; evidence is under `artifacts/browser_live_validation/knowledge-binding-surfaces-c4d6c54c-20260615/`. Binding `metadata.surfaces` is now enforced in search/suggestions/retrieval before projection, with `requester_portal -> requester_pre_submit`, `support_workspace -> support_ticket_workspace`, `agent_gui -> agent`, and Ask/retrieval surfaces -> `ai_rag`. Binding API now supports duplicate upsert plus `PATCH|DELETE /api/web/knowledge/items/{item_id_or_slug}/bindings/{binding_id}`. Knowledge Studio binding panel is localized in Russian, includes surface guidance, and supports edit/delete. Quality scoring no longer reports `missing_reviewer` when `KNOWLEDGE_REVIEW_REQUIRED=false`. K1 hardening now rejects `show_in_requester_portal=true` for non-requester-safe visibility, empty `allowed_item_types`, `allow_rag=false` while active articles force `ai_rag_policy=allowed`, and article `ai_rag_policy=allowed` in a section where RAG is disabled. The requester portal reads `show_in_requester_portal`, the support workspace reads `show_in_support_workspace`, and Studio reads `article_length_recommendation`.

### Scope

This plan covers only Knowledge Platform:

- `/app/admin/knowledge`
- `/app/admin/knowledge/sections`
- `/app/admin/knowledge/studio`
- `/app/admin/knowledge/import`
- `/app/admin/knowledge/search-settings`
- `/app/admin/knowledge/ai`
- `/app/admin/knowledge/indexing`
- Knowledge backend services, retrieval, RAG, bindings, audience rules and ops summary.

Out of scope for this plan:

- Registry UI refactor
- Access/RBAC workspace
- agent registry registration flows
- unrelated localization commits

Registry/audience foundation is treated as an existing dependency.

---

## K1 — Knowledge Sections

Status: implemented and hardened.

Implemented:

- `/app/admin/knowledge/sections` exists.
- User-facing term is `Раздел базы знаний`.
- Section editor supports title, code, description, visibility, lifecycle status, publication, ingestion, RAG, portal/support exposure, allowed material types and article length recommendation.
- Space-level audience summaries are shown.
- Uses existing `KnowledgeSpace` API and `knowledge_audience_rules` with `subject_type=space`.
- Stable section metadata keys are documented with owners/readers:
  - `show_in_requester_portal`
  - `show_in_support_workspace`
  - `article_length_recommendation`
- Backend rejects contradictory policies:
  - `show_in_requester_portal=true` with non-requester-safe visibility;
  - `allow_rag=false` while active article policy forces RAG allowed;
  - article `ai_rag_policy=allowed` in a section where RAG is disabled;
  - no allowed item types.
- The section list has a clear no-sections empty state.
- The section editor warns before archiving a section that still has active articles.

Remaining:

- No open K1 hardening items.

Acceptance:

- Section policies are understandable without raw ids or JSON.
- Section default audience can be previewed.
- Section metadata contract is documented.
- No contradictory section policy can be saved silently.

---

## K2 — Simplified Knowledge Studio

Status: implemented, needs production cleanup.

Implemented:

- Studio has one main save action: `Сохранить статью`.
- Save flow updates item settings, creates version, publishes version.
- Review workflow is hidden from default UI.
- Manual segmentation is hidden behind advanced tools.
- Basic field explanations exist for section, type, visibility and RAG.
- Version history is moved out of the main flow.
- Tests verify no visible review buttons and no visible manual segmentation in default UI.

Remaining:

1. Align backend quality with review-disabled mode:
   - `missing_reviewer` must not be treated as a blocking quality issue when review is disabled;
   - or reviewer must be auto-filled.
2. Ensure failed publish due to missing reviewer cannot happen in simplified save.
3. Add explicit save error messages:
   - validation error;
   - publish blocked;
   - audience denied;
   - section publication disabled.
4. Add dirty-state warning when leaving unsaved article.
5. Add autosave draft or explicit “Несохранённые изменения” indicator.
6. Add a simple “Создать статью и сразу открыть редактор” flow without requiring the left drawer to feel separate.
7. Ensure support and admin see the same normal authoring flow for allowed visibilities.

Acceptance:

- Support/admin creates and publishes a normal article without knowing versions/review.
- No review terms appear in default UI.
- Save failure explains the exact reason in Russian.
- Article save does not produce hidden publish blockers.

---

## K3 — Help Desk Binding / Where to Show Article

Status: implemented at UI/API create level, not fully enforced.

Implemented:

- Studio has `Связь с обращениями`.
- Article can be linked to service, offering, request template and ticket type.
- UI allows selecting display surfaces:
  - requester pre-submit;
  - requester after submit;
  - support ticket workspace;
  - support command center;
  - agent;
  - AI/RAG.
- Binding metadata stores `surfaces`.

Critical remaining work:

1. Enforce `metadata.surfaces` in suggestion/retrieval flows.
   - `requester_pre_submit` must affect pre-submit/request form suggestions.
   - `requester_after_submit` must affect requester ticket suggestions after submit.
   - `support_ticket_workspace` must affect support ticket workspace suggestions.
   - `support_command_center` must affect command center queues/suggestions.
   - `agent` must affect agent-side suggestions.
   - `ai_rag` must affect AI/RAG candidate eligibility together with RAG policy.

2. Add binding edit/delete:
   - edit service/offering/template;
   - edit surfaces;
   - delete or archive binding;
   - show reason for destructive changes if audited.

3. Add duplicate binding handling:
   - prevent duplicate same service/offering/template binding;
   - or merge/update existing binding.

4. Add preview:
   - “Статья будет предложена в: …”
   - “Не будет предложена в: …”
   - “Причина: visibility/audience/surface/RAG disabled.”

Acceptance:

- Saving surfaces changes actual suggestions.
- Support/requester suggestions respect both audience rules and surfaces.
- Wrong binding can be corrected from UI.
- No hidden article title/snippet leaks through a disallowed surface.

---

## K4 — RAG Eligibility

Status: backend exists, needs UI/ops verification.

Implemented:

- Article metadata supports `ai_rag_policy`.
- Section supports `allow_rag`.
- Retrieval filters candidates by RAG policy after audience filtering.
- RAG trace is exposed for privileged explain roles.

Remaining:

1. Verify `ai_rag_policy` is applied in all AI paths:
   - Ask;
   - retrieve;
   - vector retrieval;
   - future orchestration center;
   - support AI summary if it uses Knowledge.
2. Connect binding surface `ai_rag` with RAG eligibility.
3. Make RAG policy visible in Ops:
   - excluded by section;
   - excluded by article;
   - excluded by staff_only;
   - excluded by requester_safe_only.
4. Add tests for:
   - article policy disabled;
   - section allow_rag false;
   - staff_only requester denied;
   - requester_safe_only support_internal denied;
   - privileged trace redacts safely.

Acceptance:

- AI/RAG cannot use content that article/section policy excludes.
- Admin/support can explain why an article was excluded from RAG.
- Requester never sees hidden RAG trace metadata.

---

## K5 — Knowledge Operations Center

Status: implemented; live/browser evidence must be collected for the final committed slice.

Implemented:

- Ops summary has action queues:
  - `no_audience_users`;
  - `missing_helpdesk_binding`;
  - `stale_article`;
  - `indexing_failed`;
  - `low_quality`;
  - `zero_result_searches`.
- `/app/admin/knowledge` is a true operations dashboard rather than an article editor.
- Generic queue cards are replaced with actionable queues:
   - “Статьи без аудитории”;
   - “Статьи без связи с обращениями”;
   - “Просроченные статьи”;
   - “Ошибки индексации”;
   - “Низкое качество”;
   - “Поиски без результата”.
- Each queue item opens the correct fixing route:
   - Studio article;
   - Sections;
   - Indexing;
   - Search settings;
   - Import/create article.
- Fast transitions exist for Sections, Import/create article, Indexing and Search settings.
- Queue and fast-transition links include Russian hover hints for the expected fix.
- Raw content-pack JSON is hidden from the default ops screen.
- Content packs/import/debug remain under dedicated advanced/admin tools.

Remaining:

- No open K5 UI product-pass items after targeted and live verification pass.

Acceptance:

- Admin sees what needs attention.
- Every queue item has a next action.
- Ops page is not an article editor.
- No raw JSON default workflow.

---

## K6 — Import Alignment

Status: implemented, deployed and live-checked on the stand for commit `485969d6`.

Implemented:

1. Import wizard must require/choose `Раздел базы знаний`.
2. Import preview must show:
   - detected title;
   - section;
   - visibility;
   - audience;
   - RAG policy;
   - whether auto-segmentation will run.
3. Imported documents default to safe draft/internal mode.
4. Imported drafts carry `metadata.ai_rag_policy=inherit`; backend validation rejects explicit `ai_rag_policy=allowed` when the chosen section has `allow_rag=false`.
5. Long documents use auto-segmentation at 800+ words instead of requiring manual segmentation.
6. After import, the wizard opens the simplified Studio with the created article.
7. Live browser evidence is saved under `artifacts/browser_live_validation/knowledge-import-k6-485969d6-20260615/`; the created live draft `K6 Live Import 485969d6` opened in Studio as item `51d2bc64-b237-4012-8fd2-f24f176374a0` with `visibility=support_internal`, `metadata.import_mode=safe_draft` and `metadata.ai_rag_policy=inherit`.

Remaining:

- No open K6 items after targeted and live verification pass.

Acceptance:

- Imported article enters the same simplified lifecycle as manually created article.
- Import does not bypass section/audience/RAG policy.
- No requester-visible imported article is published accidentally.

---

## K7 — Search Settings / AI Settings Consistency

Status: existing pages likely still need product cleanup after new model.

Remaining:

1. Search settings should explain:
   - keyword/full-text/vector/RAG difference;
   - when RAG can use articles;
   - how visibility/audience filters apply.
2. AI settings should show:
   - provider health;
   - RAG policy blocks;
   - whether requester-safe content can be sent to cloud;
   - local/security-restricted restrictions.
3. Settings pages must not contradict article/section RAG policy.

Acceptance:

- Admin can understand why AI/RAG does or does not use a given article.
- Search/RAG settings do not bypass article/section visibility.

---

## K8 — Knowledge Graph / Related Articles

Status: not part of the simplified authoring MVP.

Remaining:

1. Keep graph as advanced workbench.
2. Add simple “Связанные статьи” UI in Studio later.
3. Use graph for:
   - related articles;
   - duplicates;
   - supersedes;
   - known error → workaround;
   - service → article.
4. Do not force authors to use graph for normal article creation.

Acceptance:

- Normal article creation works without graph.
- Graph improves discovery but does not block publishing.

---

## K9 — Cleanup and Documentation

Remaining:

1. Rewrite stale `PLANS.md` problem statement.
2. Move completed K1/K2/K3 from problem statement to completed status.
3. Keep current open issues clear:
   - surfaces enforcement;
   - binding edit/delete;
   - review-quality alignment;
   - section metadata contract;
   - import alignment;
   - ops UI pass.
4. Update docs:
   - Knowledge Sections contract;
   - Article visibility contract;
   - Help Desk binding contract;
   - RAG eligibility contract;
   - simplified Studio user guide.
5. Add browser evidence after each UI pass.

Acceptance:

- PLANS.md reflects current state, not old problems.
- A new developer can understand which Knowledge tasks are open without reading unrelated Registry/Access work.
