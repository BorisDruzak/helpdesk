# Ordered automatic service readiness — 2026-11-09

User's annotated Studio publication page now presents five numbered points: service
identity/access, map, processing/deadlines, checked outcomes, changes/publication.
Each point reports its current saved-revision assessment. Required title/section
omissions are visible before autosave. The highlight button scrolls/focuses existing
problems and performs no preview or publish request. Creation remains in the catalogue;
manual save/create controls and their floating portal are removed while editing.
Autosave retains error/conflict protection and an explicit error-only retry.

The canonical publish-preview is a write: it may issue a persisted administrator-
scoped one-use confirmation token and takes the scenario lock. Requests are debounced
by saved revision/actor/visibility, stale replies cannot restore readiness, section
navigation preserves the mounted assessment, blocked assessments refresh every30s
and on foreground/network recovery, and token expiry clears consent before refresh.
No automatic publishing, new route, migration, dependency or weaker authorization.
Service/processing settings are lazily rendered; canvas remains mounted. Optional v4
fallback definitions are secondary to normal service processing settings.

## Verification and isolation

The working Studio suite passed450tests/86files before final review fixes;17focused
publication regressions then passed, including stale reads, actor switch, expiry,
external policy repair, failure retry, dirty draft and local missing metadata.
The initial1366/1920browser pass was10/10; final frozen suite additionally checks
immediate problems, no create/save bar, section re-entry without reissuing preview,
and external repair without publication. Exact final results and installed/live
receipt follow below after execution; no green full CI claim.

Current files were overlaid explicitly on the installed staging baseline from
`tmp/studio-readiness-20261109/baseline.json`; CODEMAP/PLANS apply only this task's
appendix. Other dirty Studio/catalogue/ticket/OIDC work and normal Git index/checkout
are preserved. GitNexus MCP discovery and bounded endpoint access were attempted,
but unavailable. Source/provider behavior and tests were checked directly.

Evidence directory: `tmp/studio-readiness-20261109/`.


## Frozen candidate verification

- `pnpm --dir tmp/studio-readiness-20261109/source/webapp test src/features/request-template-studio src/pages/admin/request-template-studio-page.test.tsx --maxWorkers=2`: **452passed /86files**, `frozen-tests-final.log`.
- `pnpm --dir tmp/studio-readiness-20261109/source/webapp build`: TypeScript/Vite passed; existing large-chunk warning only, `build-final.log`.
- Native publication/guidance suite: **12passed**,1366×768 and1920×1080; `browser-final.log`. Includes immediate problem marks, no create/save bar, highlight-only no-preview, retained state on section navigation, external repair and explicit consent remaining unchecked. No mutating test ran against staging.
- `python scripts/verify_workspace.py`: passed. Candidate `git diff --check` passed.
- Focused read-only review corrected a stale blocked assessment after external policy repair. No remaining concrete finding. A partial legacy fixture without a title exposed a defensive rendering issue; the existing terminal regression and new missing-metadata regression pass after correction.
- Pre-task page/publication/wizard files exactly matched the installed72997cf1baseline; explicit overlay excludes parallel unpublished work.
- Verified staging database backup and isolated restore both passed, schema158.

The existing selected service was recorded before activation: scenario75b408c9-8db4-4a5d-8180-8fe81ce2809b, draft revision67. The final live receipt compares its definition hash, published version and visibility; normal preview token rows are expected to be issued by automatic checks.


## Guarded integration with a concurrent staging update

Initial candidate b73d5b6d458b816c94d8e91cacec6696348a5583 was rejected before installation:
expected-current-SHA guard detected support queue release7fe767a72796427cd1e70a05471c581897399ca2 replacing72997cf1a073700c36c8ec689cfbaa5412ab86a4. Helpdesk remained active, no candidate directory or migration override was created. The initial candidate branch is retained for audit and was not pushed.

The refreshed candidate uses7fe767a as parent and retains all21files of that release.
No Studio source or test path overlaps that update. Only CODEMAP/PLANS appendices
needed combination; no history rewrite or deployed-file patch. All Studio code/test
hashes are unchanged from the452-test/12-browser accepted candidate; refreshed build
and browser checks validate composition with the new shell/navigation baseline.
