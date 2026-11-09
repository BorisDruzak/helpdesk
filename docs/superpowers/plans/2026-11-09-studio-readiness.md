# Automatic service readiness and ordered publication

User's annotated request: remove create/save controls while editing an existing service; keep autosave; show ordered, immediately checked requirements; make the check button reveal problems rather than initiate validation.

Actor: administrator. Primary job: complete service configuration and deliberately publish the reviewed saved revision. Archetype: ordered checklist with expandable settings and final confirmation. No new dependency, endpoint, schema or change to publication authorization.

Approach: reuse canonical publish-preview after each saved revision and catalogue visibility change. Clear stale readiness/confirmation on dirty edits, changed identity/revision/permission, expiry and failed checks. Debounce checks, ignore stale responses, retain explicit final confirmation. Failure retry is separate from the highlight-only button. Keep the map mounted and reuse existing issue-to-setting navigation.

- [x] Regression tests: automatic initial check; highlight makes no new request; dirty/stale/failed checks cannot authorize publishing; explicit confirmation remains required; no create/manual-save bar in the editor; autosave/retry remain reachable.
- [x] Compose five steps: service identity/access, scenario map, processing/deadlines, checked outcomes, reviewed changes/publication. Show scoped issues and current check state on each step immediately.
- [x] Remove editing header action portal; retain catalogue creation and explicit recovery after autosave errors. Split existing settings into their respective steps.
- [x] Focused Studio/page tests, TypeScript/build, workspace verification, 1366/1920 browser evidence, no horizontal overflow, console/network and failure states.
- [ ] Review code and docs, isolate task delta from pre-existing dirty Studio work, deploy immutable candidate on the live staging baseline through the canonical guarded script, then inspect the user's saved service without publishing or editing it.

GitNexus MCP discovery and a bounded request to the configured endpoint were attempted; currently unavailable. Verify the committed baseline and local changes directly. Live baseline is recorded under tmp/studio-readiness-20261109/baseline.json.
