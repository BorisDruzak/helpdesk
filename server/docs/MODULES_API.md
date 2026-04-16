# Modules API

The current modules API evolves the existing `modules` path in-place and now uses the unified semantic tool contract.

## Canonical docs

Read these first:

- `server/docs/MODULE_CREATION_GUIDE.md`
- `server/docs/MODULE_AUTHORING_RULES.md`
- `server/docs/REGISTRY_PUBLICATION_RULES.md`
- `server/docs/RUNTIME_EXECUTION_CONTRACT.md`

## Domain model

- `module` = delivery pack, versioning, ownership
- `tool` = atomic typed executable contract
- `playbook` = orchestration layer over tools

Canonical tool ids stay semantic-only:

- `dns.resolve`
- `network.ping`
- `screen.collect`

Legacy aliases exist only as compatibility bridges.

## Server responsibilities

- preflight ZIP and manifest normalization
- ownership/conflict checks
- publish into the server registry
- preferred-version policy per module family
- rollout settings for how preferred-version changes propagate to devices
- preferred-version resolution for auto-install
- desired-state persistence before auto-install
- version-aware auto-install/update before `run_tool`

## Admin workbench

`/admin` embeds a dedicated module-development workbench loaded from:

- `server/admin_modules_workbench.html`
- `server/admin_modules_workbench.js`

Workbench API:

- `GET /api/modules/workbench` - grouped module families with versions and preferred-version state
- `GET /api/modules/rollout_settings` - current rollout policy for preferred-version changes
- `PATCH /api/modules/rollout_settings` - update the rollout policy (`manual` or `installed_devices`, plus reconcile/refresh toggle)
- `GET /api/modules/workbench/{module_name}/{version}` - module detail plus editable draft reconstructed from manifest and archive contents
- `POST /api/modules/workbench/validate` - build a package in memory, run preflight/smoke, report ownership conflicts, and return an editable preview without publishing
- `POST /api/modules/workbench/save` - build, validate, smoke-check, and persist a module from the structured UI payload
- `POST /api/modules/upload` - upload a ready ZIP package, run server preflight/smoke, publish it into the registry, and make it available for immediate editing in the workbench
- `DELETE /api/modules/{module_name}/{version}` - remove a published module version from the registry and delete its archive from storage; clears preferred-version assignment if the deleted version was preferred
- `PATCH /api/modules/{module_name}/preferred` - assign the preferred version used by auto-install/runtime resolution

Workbench UX expectations:

- the `Модули` page is split into inner tabs for guided development, catalog/list, advanced editor, and device install state
- the guided flow is a 4-step wizard: `Каркас -> Инструменты -> Политики -> Проверка`
- the catalog/list view is also the entrypoint for ZIP import and destructive actions on published versions, so authors do not need a separate screen for archive onboarding
- common manifest/tool fields no longer require raw JSON for everyday authoring:
  - module platforms are chosen from supported platform pills (`any`, `linux`, `win32`, `darwin`)
  - module `requirements` and `optional_requirements` are entered as one item per line instead of JSON arrays/objects
  - params/output schemas can be assembled from validated line-based blueprint rows such as `hostname:string! | Имя хоста`, while raw JSON schema stays available as an advanced fallback
- local validation is expected to catch platform mistakes, owner-scope conflicts, and malformed schema JSON before server-side validate/publish
- archive import expects `module_name` and `version` for the upload contract, but canonical values are still reconciled against `manifest.json` inside the ZIP

Workbench detail and validate preview both expose archive/source decomposition for generated ZIP packages:

- extracted text files from the archive
- detected `@exposed_tool` functions and method names
- per-tool reconstruction strategy (`markers`, `ast`, `raw`)
- unresolved tools and methods so the editor can highlight where manual cleanup is still needed

The preferred version is stored server-side and is the same source of truth used by:

- the admin UI
- `run_tool` auto-install and auto-update
- preferred module resolution in the server registry

Preferred-version rollout now has an explicit server-side setting:

- `manual` - changing preferred only changes the registry/source-of-truth; devices update later through `run_tool`, manual install, or other runtime touch points
- `installed_devices` - changing preferred immediately rewrites desired state for devices that already have the module installed (or already have `desired=installed`), triggers reconcile so the target version is enqueued to the agent, and then queues inventory/toolset refresh so server-side actual state converges in the UI

## Builtin modules

Builtin providers such as `system` and `screen` use the same contract vocabulary and validation model, but they do not require server ZIP installation.

## Historical note

Legacy `module.tool` naming and the old risk vocabulary remain only as internal compatibility layers. The public canon now centers on semantic tool ids and the shared contract vocabulary.
