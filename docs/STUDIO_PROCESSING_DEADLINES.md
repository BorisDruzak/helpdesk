# Processing deadlines in Request Studio

The administrator block library and map context menu offer one **«Сроки обработки»** attachment. Connect its dashed setting link to an ordinary step or result; it never becomes an employee step or a flow transition.

The editor has independent Russian-language sections:

- **«Сроки для сотрудника»**: published SLA policy or map profile for first response and resolution. Existing processing facts remain under the urgency/importance disclosure.
- **«Внутренние сроки поддержки»**: inherit, choose a published OLA policy, or enter assignment and group-processing minutes. Assignment stops the first clock; resolution stops processing according to the existing lifecycle policy. The existing server feature flag still controls these clocks.

Both follow retained-path precedence independently. Terminal choices override their respective path selection; leaving either choice empty preserves inheritance for that category. The result editor groups route and both deadline categories in one section, and checked publication/simulation results use Russian labels.

## Compatibility and authority

The v4 `sla_attachment` JSON kind is retained and gains optional `ola_targets` / `ola_policy_ref`. Absent internal overrides are omitted during serialization. Old v1-v3 definitions, legacy sequential `sla`, old separate `ola_attachment`, user titles, processing profiles and historical published versions are not rewritten. Old OLA blocks remain editable with Russian type/field labels. New built-in internal-deadline fragments use the combined attachment.

SLA and OLA references remain distinct policy kinds, including fragment mappings where their codes coincide. Backend policy availability checks, strict integer durations, authenticated server-owned submission and canonical ticket timers remain authoritative. A combined internal override and a separate old OLA assignment cannot both attach to the same target; remove one explicit internal assignment before publication. A legacy SLA-only attachment may continue sharing its target with a legacy OLA attachment.

No database migration, new route, dependency, permission or Endpoint contract is introduced. Definitions remain schema version4 and the database stays at revision158. This is an additive reader update: rolling back the application after saving combined internal fields requires a compatible reader; backups and immutable published versions remain the recovery path.

## Verification

`test_request_scenario_unified_timing.py` covers independent deadline selection/terminal inheritance, old wire omission, legacy coexistence, conflicting assignments and typed fragment/reference boundaries. `scenario-timing.test.tsx` covers a single library item, independent visual edits and connection conflicts. Native `studio-timing.spec.ts` and legacy `studio-ola.spec.ts` verify visual connections and terminal edits at1366×768 and1920×1080.
