# OLA blocks in Request Studio

Administrators can add **OLA** from the block library or map context menu in a version 4 scenario. Drag its purple setting link onto a question, instruction, navigation step or result. It is an attachment, never an employee step or an executable transition. Only one OLA attachment of this kind may be connected to a target; SLA and routing attachments remain independent.

Choose a published OLA policy or enter acknowledgment and processing durations. Manual values are whole calendar minutes from 1 to 525600. Both values belong to one assignment; selecting a policy clears manual targets and selecting manual targets clears the policy. The built-in OLA fragment provides an instruction, terminal and an attached editable 15/240-minute example.

The retained requester route determines OLA. Last visited explicit attachment wins; settings on unvisited or backtracked branches do not contribute. The terminal attachment applies next, followed by the terminal's optional explicit override. An empty terminal choice inherits the route; absent assignments preserve existing service/template/queue behavior. The terminal shows structural alternatives and the server-checked result; publication outcomes and simulation show OLA separately from SLA and route.

## Contract and runtime

`ola_attachment` adds `attached_to`, optional `targets: {ack_minutes, processing_minutes}` and `policy_ref` to the v4 discriminated block union. `submit_ticket` optionally adds `ola_targets` and `ola_policy_ref`. Old terminal JSON omits these keys. Historical schemas 1-3 and prior v4 definitions remain accepted without rewriting. Database schema stays at revision 158; definitions are already JSON and the database permits version 4.

`tickets/request_scenario_ola.py` selects only server-loaded retained visits and composes explicit targets into the existing OLA policy. Existing start/stop/pause/resume and breach rules remain in effect. A trusted `scenario_ola` marker pins the manually selected durations through registry overlays and ticket lifecycle policy reads. Published policies remain registry-resolved and active/published validation is mandatory. No requester-supplied authority fields are accepted. Fragments use a separate typed `ola_policy_refs` mapping, avoiding collisions with SLA and routing policy codes.

OLA timers require `TICKET_OLA_ENABLED=true`. This flag remains the canonical lifecycle guard; a map block never bypasses it. The staging-only `scripts/configure_helpdesk_staging_ola.py` holds the canonical staging deployment lock while it checks host, runtime path, exact release and environment SHA, keeps a private byte-for-byte environment backup, atomically enables only this flag, and restarts only helpdesk-staging.service. No backfill of existing tickets occurs. Environment restoration uses the protected backup and a service restart through the release/runbook workflow; do not copy secrets into logs or the repository. This script rejects production.

## Verification

Focused tests cover retained-branch and terminal precedence, strict durations, forbidden flow targets, policy-kind fragment mappings, canonical OLA deadlines, registry pinning and staging configuration guards. Native Chromium covers map creation, dragged attachment reconnection and terminal editing at 1366x768 and 1920x1080. Live staging acceptance uses an isolated draft and preserves existing services, drafts and browser tabs.

When OLA is disabled, simulation returns `ola.enabled=false`, omits effective deadline previews and labels configured durations as inactive. Publication rejects a new explicit attachment/terminal OLA assignment until the runtime feature is enabled. Existing definitions with inherited rules are not made incompatible.

Support timer projection uses `ola_ack_at` and `ola_processing_at` as completion timestamps. Assignment stops acknowledgment; resolving or closing stops processing according to the existing lifecycle policy. Completed clocks remain completed after their original deadline, and a late completion retains its missed-target result. SLA clocks remain independent.
