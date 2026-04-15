# Modules API

Текущий модульный API работает in-place поверх существующего `modules` контура, но уже использует unified semantic tool contract.

## Canonical docs

Сначала читать:

- `server/docs/MODULE_AUTHORING_RULES.md`
- `server/docs/REGISTRY_PUBLICATION_RULES.md`
- `server/docs/RUNTIME_EXECUTION_CONTRACT.md`

## Domain model

- `module` = pack доставки, versioning, ownership
- `tool` = атомарный типизированный контракт
- `playbook` = orchestration layer поверх tools

Canonical tool ids semantic-only:

- `dns.resolve`
- `network.ping`
- `screen.collect`

Legacy aliases допустимы только для совместимости.

## Server responsibilities

- preflight ZIP and manifest normalization
- ownership/conflict checks
- publish in module registry
- preferred-version policy per module family
- preferred-version resolution
- desired-state persistence before auto-install
- version-aware auto-install/update before `run_tool`

## Admin workbench

`/admin` now embeds a dedicated module workbench loaded from separate static files:

- `server/admin_modules_workbench.html`
- `server/admin_modules_workbench.js`

Workbench API:

- `GET /api/modules/workbench` — grouped module families with versions and preferred-version state
- `GET /api/modules/workbench/{module_name}/{version}` — module detail plus editable draft reconstructed from manifest/archive
- `POST /api/modules/workbench/save` — build, validate, smoke-check and persist a module from structured UI payload
- `PATCH /api/modules/{module_name}/preferred` — assign the preferred version used by auto-install/runtime resolution

The preferred version is stored server-side and is the same source of truth used by:

- the admin UI
- `run_tool` auto-install/auto-update
- preferred module resolution in the server registry

## Builtin modules

Builtin providers (`system`, `screen`, и др.) используют тот же contract и validation vocabulary, но не требуют server ZIP install.

## Historical note

Legacy narrative вида `module.tool` и старые risk enums оставлены только как compat layer внутри runtime. Публичный канон теперь строится вокруг semantic tool ids и shared contract vocabulary.
