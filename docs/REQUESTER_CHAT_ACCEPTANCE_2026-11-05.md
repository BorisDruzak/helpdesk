# Requester chat context: staging acceptance, 2026-11-05

## Change and scope

The employee conversation now shows public status, the assigned specialist,
whose action is needed, first-response/resolution SLA and the associated device.
Public processing events appear in chronological order beside role-correct chat
messages. Access-code notices are system events. Desktop has a persistent context
panel; mobile has a compact expandable summary and accessible reply composer.

The authenticated detail API adds an owner-only `handling` sibling and no-store.
Current device presence requires current ownership and exact Registry/Endpoint
references. No device or unavailable presence is explicit. Existing result,
attachment and resolution actions remain. No new schema, dependencies, roles,
approvals, diagnostic operations or business transitions were introduced.

Frozen code: `1ba7c8166e1d0317479a965dcf63b1b7d2accd3a`,
`feat(requester): show ticket handling context beside chat`, branch
`codex/ui-support-001`. Its18 files cover the requester handler/projection,
shared support timer, requester UI/types, regression tests, contract/CODEMAP and
task design/plan. Unrelated local work was preserved unstaged.

## Verification

- 29 backend tests passed:
  `python -m pytest server/tests/test_requester_ticket_handling_no_db.py server/tests/test_support_workspace_projection_no_db.py server/tests/test_requester_timeline_projection.py -q`.
- 2 PostgreSQL/API tests passed using a fresh disposable test role and isolated
  databases through `tmp/requester-chat-context-20261105/db_tests.py`:
  `server/tests/test_requester_ticket_handling_db.py` and
  `server/tests/test_requester_workspace_api.py::test_requester_ticket_detail_and_message_are_owned_only`.
  Test databases and role were removed. Owner/stranger404, current assignment,
  SLA, public events and public reply survival after205 internal chat events pass.
- 27 frontend tests passed:
  `pnpm --dir webapp test src/pages/requester/ticket-context-panel.test.tsx src/pages/requester/ticket-conversation.test.tsx src/pages/requester/ticket-chat-page.test.tsx src/pages/requester/tickets-page.test.tsx src/pages/requester/tickets-panels.test.tsx src/features/requester/queries.test.ts`.
- `pnpm --dir webapp build`, `python scripts/verify_workspace.py` and staged
  `git diff --check` passed. The canonical release also builds the frozen archive
  with its committed lockfile. Full repository/fleet/production gates were outside
  this focused change. Python reports an existing Authlib deprecation warning.
- Built-bundle browser fixtures at1366x900 and390x844: assignment/status polling
  updates without reload or draft loss; mobile details expand; scroll width390;
  composer/send remain inside844px viewport.503 retains cached chat/draft;404
  removes cached content. Zero page exceptions in both runs. Screenshots:
  `tmp/requester-chat-context-20261105/desktop-final.png`, `mobile-final.png`.
- Independent read-only review found three P2 cases; all fixed and regressed:
  negative paused SLA text, partially hidden SLA targets, and public replies
  displaced by private-event noise. Final review found no remaining code blocker.
  GitNexus committed architecture was consulted; source/tests verified dynamic
  ownership and existing Context/presence boundaries. No HTTP provider contract
  was added. Context7 TanStack Query v5 guidance informed cached-error handling.

## Release evidence

Approved target only: `osn-admin@192.168.101.118`, isolated Helpdesk staging.
Canonical `scripts/deploy_helpdesk_release.py` through the existing staging
transport, exact committed source and lockfile frontend bundle.

Fresh verified private backup before release: PostgreSQL153, source
`7d8dda5d814e88c40d5eac2dfa1e7324135638f3`,13483669 bytes,
SHA256 `40ac5ddc5f9ff046f1f3d5edaf1d03a5ed78da5b105e4f38589f3edd2c4b2a2a`.
Installed selector is
`/opt/helpdesk-staging/releases/helpdesk-1ba7c8166e1d0317479a965dcf63b1b7d2accd3a`.
Normalized-LF SHA256 of nine changed runtime source files matched frozen Git.
Schema remains153. Strict CA/hostname HTTPS health returns200 for both Helpdesk
and Endpoint. All three staging service units remain active as explicitly asked.

Pre/post-release count/content seals match for `tickets`, `ticket_events`,
`ui_users`, `registry_people` and `registry_person_identities`. No user business
mutation was used for acceptance. The installer gracefully stopped the old
process; a transient502 was observed during that interval, then the installed
application loaded successfully.

Current authenticated `admin` session opened its own requester T-000058 at
`/app/requester/tickets/T-000058`. The real API/browser shows accepted status,
unassigned specialist, next action for support, overdue response/resolution SLA,
support group, explicit no-device state, public conversation and reply composer.
No cross-owner bypass was used. Final console error/warning log is empty.
Live screenshot at1280x720:
`tmp/requester-chat-context-20261105/live-requester-chat.jpg`.
Linked-device/assignment changes were verified in source/isolated tests and
built-bundle fixtures; no actual employee assignment or binding was changed.

## Other follow-up results in this session

WorkTime's visible return link was deployed and clicked back into the existing
Helpdesk session without another login. Frozen Endpoint source:
`0554e70b0d4c679173d502af6000cc53ac17f27f`,
`fix(worktime): add a visible return link to Helpdesk`, branch
`codex/worktime-helpdesk-login`. Its six files are the shared return-link
component, employee portal/styles, SSO/runbook notes and guarded staging release
adapter.76 frontend tests, frontend build and5 release guards passed. Canonical
release receipts and verified backup are private in
`tmp/worktime-handoff-20261105/return-endpoint-*.json`; archive SHA256
`232d0750eb36d15d89820886ca61a9a1e50cad08e41e8981288c64414f9489f1`.
Schema0044, strict TLS200 and WorkTime business/grant seals were verified after
activation. Desktop and mobile return-link fixtures were checked. The endpoint
worktree was clean after commit. Login `bdryzhak` was confirmed active and bound
to the verified Helpdesk identity for Дрыжак Борис Николаевич.

Device linking remains a separate diagnosed configuration issue. An invalid-body
probe (no real possession code consumed) proved staging Endpoint returns403
`Required service scope is missing`: its current Helpdesk credential lacks
`device-binding.redeem`. The native PC's Endpoint config points to production;
its code is issued by that provider, while the screenshot was staging. No scope,
native config, credential or production setting was changed. Endpoint origin is
configurable in `C:/Program Files/Endpoint Platform/Agent/config/agent-config.yaml`;
the tray's default Helpdesk link points to production. Production binding was
not accepted live and cannot be claimed working from this staging diagnosis.

## Limits

Public messages and progress use separate bounded newest windows:200 messages,
200 raw progress events. Older progress can be omitted after technical noise;
public replies remain protected. No new full-history pagination was added.
No employee message, status/assignment, consent, device binding or WorkTime
business action is submitted on a real user ticket during acceptance.
Production and the native agent remain unchanged.
