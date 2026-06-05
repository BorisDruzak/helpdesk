# webapp/AGENTS.md

## Webapp-specific rules

- Follow root `AGENTS.md`; the local Windows repo remains the source of truth.
- Browser-visible changes require real browser validation, not only code inspection, API calls, DB checks, or smoke tests.
- Use `.agents/skills/pc-client-browser-check/SKILL.md` for UI/browser work.
- Use `https://192.168.100.17:9443/admin` for project browser checks unless the user explicitly requests another target.
- Check console and network errors for UI behavior changes.

## Toolchain

- Before new `webapp/`, React, frontend bundle, or web-asset release work, run:
  - `python scripts/bootstrap_web_toolchain.py`
- The canonical frontend toolchain is managed by project scripts. Do not invent a parallel install/build flow when a project script exists.

## Docs and verification

- Update frontend docs, CODEMAP-covered navigation docs, and API/DTO references when routes, screens, forms, user flows, contracts, or build/release behavior change.
- For typed web API or DTO changes, check both server API producers and frontend consumers.
- Run targeted frontend checks when available, then collect browser evidence for visible behavior.
