# SSO, confirmed identities and WorkTime

## Intent and authority

Implement the supplied SSO + Helpdesk + Endpoint + DLP + WorkTime specification
in stages A–F. The user authorized implementation, separate agent updates,
deployment and tests on the Linux test machine and local domain workstation,
and requires independent subagent review and verification at every stage.
Do not expand this to fleet rollout, domain GPO changes, bulk AD edits, forced
account migration or organization-wide personnel monitoring.

## Existing foundations

Helpdesk's RegistryPerson is the person authority. Existing UiUser keys, ticket
ownership, requester resolution, grants and consent history must survive SSO.
RegistryPersonIdentity's generic normalizer must not process case-sensitive OIDC
subjects. Its generic upsert can return an identity belonging to another person;
that result is not evidence of a successful identity binding.

Endpoint's current main is 78d24e9. Its original checkout has unrelated pending
changes and is 487 commits behind; implementation uses
`C:/Users/admin-2/Documents/endpoint/.worktrees/sso-worktime-20261027`.
Helpdesk starts at 6cca48e5, which includes current main and existing fixes.
GitNexus group status was checked; Endpoint index is one commit behind and
source verification remains necessary. Never run group_sync manually.

## Approach

Extend the independent applications and existing agent. Use Keycloak with AD
LDAPS federation and a maintained OIDC client (Authlib), opaque application
cookie sessions and server-side flow state. Do not build an authorization server
or introduce another telemetry collector. A combined service/database would
violate the supplied boundaries; duplicating employees or matching email/login
would lose identity guarantees. These alternatives are rejected by the brief.

The required OIDC dependency is a necessary implementation choice, not a user
preference. Context7 was attempted but exhausted its quota; consult versioned
official library documentation and verify the installed API. Secrets are runtime
inputs, never repository content. New features default disabled until configured.

## Identity contract v1

Helpdesk owns `POST /api/integration/v1/identities/resolve`. A separately
configured high-entropy service credential authorizes this operation only; user
cookies and ordinary UI/API credentials cannot authorize it. Compare credentials
in constant time, fail closed if unconfigured, rate/bound requests, disable
caching and avoid recording credentials or full request identities in logs.

Input: `issuer` (exact configured HTTPS issuer), `subject` (case-sensitive OIDC
sub), `ad_object_guid` (canonical UUID). The consumer obtains all three from
validated OIDC claims, never browser-supplied person IDs. No person_id selector.

Success: `version: 1`, stable `person_id`, the same `issuer`, `subject` and
`ad_object_guid`, `state: active`, nullable `department_id`. No contacts, tickets,
passwords or tokens. Resolve only a single confirmed binding to an active person
and active existing UiUser. Unknown = 404, conflicting/unconfirmed = 409,
inactive = 403, invalid service authority = 401, unavailable = 503.

Persist an explicit confirmed binding with database-enforced uniqueness for
`(issuer, subject)`, AD GUID and UiUser, FK to RegistryPerson and UiUser, confirmed
actor/time and revocation state. Do not auto-create or merge people during login.
Preserve unsuccessful migration candidates separately for operator resolution.
Disable a mapped account's password login only after an explicit verified
migration step; keep unmapped accounts and bounded emergency access working.

Endpoint validates OIDC issuer, signature, audience, expiry, nonce and one-use
state with PKCE S256 before resolving identity. Provider or Helpdesk failures
create no binding and grant no access. Administrative and employee clients,
cookie names, callback state and authorization audiences remain separate.
Device credentials, service tokens and WSS authority remain unchanged.

Persist upstream sid, expiry and encrypted OAuth token material server-side.
Introspect before protected use with at most 60 seconds of cached positive
authority; reject on expiry, revoked binding or provider failure. Local logout
revokes the application session immediately and clears its cookie; RP logout
uses the fixed configured provider endpoint. This bounds provider revocation,
not AD replication: AD disable propagation must be tested against the actual
LDAP federation configuration and documented before pilot acceptance.
Administrative SSO requires an exact configured MFA acr value supplied by a
Keycloak conditional MFA flow; missing assurance denies issuance. Never infer
MFA merely from successful SSO or a requested acr. Emergency access has an
explicit configured expiry and existing local rights, with audit; unmapped
existing employees retain their current login during gradual migration.

## Authorization and WorkTime

Employee self access derives person_id from the server session. Explicit scoped
roles grant Manager, HR, WorkTime Admin, Endpoint Admin and DLP Officer abilities.
An Endpoint technical administrator gains no personnel or DLP rights implicitly.
Revalidate current account/grants on protected operations; audit changes.

WorkTime has separate durable records for confirmed identity, schedules/shifts,
day events, status intervals, explanations, corrections, approvals and audit.
UTC instants, Asia/Yekaterinburg reporting, half-open intervals, transactionally
serialized transitions, idempotent requests and immutable correction history.
Technical ACTIVE/IDLE/LOCKED/DISCONNECTED/UNKNOWN intervals remain technical
evidence and never become confirmed work automatically. Existing analytics
unions overlapping devices; unverified login aliases remain unattributed.

For the initial pilot, an operator confirms a temporal account mapping scoped
to person, device, canonical OS account and validity interval using independent
AD/directory evidence. One active mapping cannot name two people. A rename
requires another verified validity-bounded alias; shared-device lookup must
match the authenticated current sensor session. Old agents without sufficient
session evidence collect existing telemetry but receive no personal companion
notification. This preserves safety while a later protocol extension can add
stable OS identity; do not guess a GUID from an account name.

WorkTime retention is a separate policy and defaults to no automatic deletion
until the organization approves a duration. Activity cleanup has no cascading
FK to explanations, status events, approvals or monthly records. Saved totals
must not depend on technical detail surviving its shorter retention window.

Use separate concentric day rings (work status / computer activity), 00:00 top,
clockwise 24 hours, selectable arcs plus accessible text list. Date/week/month
views and manager approvals use the same scoped APIs. DLP stays separate.

## Companion and safety

Only a confirmed uninterrupted measured inactivity interval >=1200 seconds,
followed by measured return, can create an explanation request. Honor schedules,
existing explanations and predeclared covered status intervals. UNKNOWN gaps,
ambiguous identities and another OS session suppress notification. Durable
server requests provide idempotence and later completion. The unprivileged
Windows/Linux user process opens a fixed trusted employee portal URL; no device
credentials or browser secrets enter that process or URL. Do not launch UI in
Windows Session 0 or add generic Gateway command execution.

## Stages and gates

1. A: identity schema/contract, safe linking, Authlib OIDC BFF, Keycloak/LDAPS
   configuration, preserved Helpdesk identity and split Endpoint sessions.
2. B: employee/admin/DLP navigation and server permissions, Helpdesk portal link.
3. C: WorkTime persistence, scoped API, events/schedules/calculation/corrections.
4. D: accessible two-ring visualization and employee/manager/HR interactions.
5. E: durable return notifications, Windows/Linux companion and agent release.
6. F: installed integration pilot, rollback and regression evidence.

Each gate requires independent subagent review, focused regression tests and
documented evidence. Browser-visible gates require Playwright. Real SSO, LDAP,
MFA and device acceptance require configured infrastructure and real pilot
identities; local mocks do not substitute for those outcomes. Publish each
repository independently and retain backwards compatibility during rollout.

## Infrastructure inputs and open decisions

Keycloak TLS certificate, LDAPS CA/bind secret and pilot identities must come
from the approved runtime secret channel. The user instructed checking AD
admin-2@192.168.100.11 and, if absent, deploying a separate Keycloak on
192.168.100.19. Read-only inventory found no Keycloak service or Java/container
process and no sso/keycloak DNS records on AD-MAIN. Deploy the isolated service
on .19; DNS/TLS and private LDAP bind inputs remain explicit provisioning steps.
Capacity read-only check: 13 GiB available. No infrastructure or agent changes
have yet been made.
