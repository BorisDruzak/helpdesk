# Unified processing deadlines implementation plan

**Goal:** One Russian-language «Сроки обработки» library block with independent employee and internal support deadlines, preserving every existing definition.

**Approved design:** The user's «сделай единый блок, с русской локализацией» accepts the preceding proposal: employee first response/resolution plus optional internal assignment/processing. Actor is admin, primary job is visually attaching and editing processing deadlines in the existing Studio workbench. Existing policies, timers, precedence, permissions and old schema versions remain authoritative.

**Architecture:** Extend v4 `sla_attachment` with optional `ola_targets` / `ola_policy_ref`, omitted when inherited. Reuse existing SLA profile selection, OLA editor and canonical lifecycle. Keep legacy OLA and sequential SLA readable/editable without automatic conversion. One palette item, Russian labels, combined terminal editor with route and two deadline sections. No migration or dependency.

**Tech stack:** React 19.2.5, TypeScript, existing Pydantic2 DTO/runtime and PostgreSQL JSON definitions. Context7 React19 docs consulted; GitNexus unavailable, verify dynamic boundaries with source and tests.

## Tasks

- [ ] Add failing backend coverage for dual assignments, independent inheritance, terminal precedence, omitted legacy wire keys, fragment policy mappings and validation/reference checks.
- [ ] Extend attachment contract and trusted OLA selection/reference validation without changing legacy semantics; regenerate JSON schema.
- [ ] Add failing component/model coverage for one library item, two independently editable sections and old block preservation.
- [ ] Implement Russian combined editor, terminal grouping, palette/context menu/fragments/result labels; preserve old raw identifiers and stored custom titles.
- [ ] Run focused backend/frontend checks, exact candidate typecheck/build/workspace sanity, review complete candidate diff and docs/CODEMAP.
- [ ] Freeze only task hunks on installed staging dfab45e7e43966d117dfc94a12aaeb30ff3891ca; preserve dirty index and original browser tabs.
- [ ] Back up and restore-drill staging, deploy via canonical installer, test save/reload/preview and old definitions in browser at 1366x768 and 1920x1080. Archive own fixture only; compare original rows/tickets and retain evidence. Production untouched.

## Review focus

Employee and internal controls must not overwrite each other. Empty internal settings inherit existing rules; disabled timer flags still apply. Combined and legacy internal assignments on one target must not become ambiguous. Old definitions omit new null keys. Typed policy references and fragment dependencies cannot confuse SLA and OLA policies with the same code.
