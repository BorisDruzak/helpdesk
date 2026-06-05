# webapp/AGENTS.md - Webapp Instructions

## Scope

This file applies to frontend/browser-visible work under `webapp/`.

Use it for:

- frontend routes/pages/components
- admin UI behavior
- forms, tables, modals, navigation
- browser-visible state and data flows
- visual/CSS/responsive changes
- frontend build/toolchain behavior
- browser validation
- webapp docs updates

Root `AGENTS.md` still applies.

## Local context

Before non-trivial webapp edits, consult available project routing docs:

- `docs/QUICK_LOOKUP.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/CONTEXT_INDEX.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`

Use focused context tools when available:

```powershell
python scripts/build_context_pack.py --topic "<webapp task>"
python scripts/search_context_index.py "<route component error symbol>"
rg "<pattern>" webapp
```

## Relevant skills

Use repo-local skills when applicable:

- Context discovery: `.agents/skills/pc-client-context-pack/SKILL.md`
- Browser validation: `.agents/skills/pc-client-browser-check/SKILL.md`
- Bugs, regressions, failing tests: `.agents/skills/pc-client-systematic-debug/SKILL.md`
- Code review: `.agents/skills/pc-client-code-review/SKILL.md`
- Docs/CODEMAP drift: `.agents/skills/pc-client-docs-drift/SKILL.md`
- Release/deploy validation: `.agents/skills/pc-client-release-gate/SKILL.md`

## Webapp implementation rules

- Browser-visible changes require real browser validation when project tooling supports it.
- Do not claim UI behavior is fixed based only on code inspection.
- Use the project frontend bootstrap script when required:
  - `python scripts/bootstrap_web_toolchain.py`
- Reuse existing routing, state, data-fetch, component, and styling patterns.
- Do not introduce a parallel UI architecture unless explicitly requested.
- Check console and network errors for UI behavior changes.
- Preserve Russian text rendering; mojibake is a defect.
- If routes, screens, forms, user flows, build behavior, or browser-visible behavior change, update relevant docs.

## Verification

Before claiming completion for webapp work:

- Run workspace sanity when available:
  - `python scripts/verify_workspace.py`
- Run targeted frontend checks when available.
- Use `.agents/skills/pc-client-browser-check/SKILL.md` for browser-visible changes.
- Validate the relevant route/page/user flow in a real browser or project browser MCP workflow when available.
- Check console/network status when relevant.

## Docs drift

Use `.agents/skills/pc-client-docs-drift/SKILL.md` when webapp work changes:

- routes/pages
- components with documented behavior
- forms/tables/navigation
- admin workflows
- build/toolchain behavior
- frontend test/check commands

## Final response requirements

For webapp tasks, include:

- frontend files changed
- route/page/user flow impact
- browser evidence
- console/network status when checked
- frontend checks run
- docs updates or why not needed
- residual UI risks
