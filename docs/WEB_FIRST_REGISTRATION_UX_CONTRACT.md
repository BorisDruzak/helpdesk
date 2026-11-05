# Requester and device visibility contract

Helpdesk keeps authenticated requester and administrator web workspaces.
Employee registration guides the requester through ФИО → отдел и контакты → пароль.
«Отдел» is one searchable selection field: typing filters active published names;
only explicitly selecting an option supplies its ID. Unmatched text cannot submit
an old selection. Keyboard arrows/Enter select without advancing the wizard.
Password and confirmation each have their own show/hide button, without storing
either value or submitting the form.
The server generates a lowercase transliterated login from the first-name initial
and surname (`Иван Петров` → `ipetrov`), adding a suffix starting at `2` on a
collision. Existing logins and confirmed domain identities are never renamed.
Account, complete own profile and verified own `ui_login` alias are created in one
transaction, always with role `user`. The browser then uses ordinary password
login and opens `/app/requester`. It shows the actual login; the ticket form opens
only when the employee clicks «Создать обращение». Registration creates no ticket
and does not follow a pre-registration `next` directly to the ticket form.

The public
`GET /api/web/session/capabilities` projects the server registration flag; disabled
registration leaves login available and shows a clear state on the register route.
Account registration is separate from device binding and Endpoint Agent enrollment.

`GET /api/web/session/registration-options` returns only active departments and a
strict editable signup schema, with no people, locations, device links, hidden
fields or administrator metadata. `POST /api/web/session/register-requester`
accepts name parts, department/contact/profile fields, password/repeat and a UUID
`request_id`; caller-selected login, role, person and location are forbidden.
Both routes enforce the registration flag. Signup also retains same-origin,
password and rate-limit checks. The legacy account-only register API remains
compatible; its clients complete their own profile through authenticated setup.

Migration `152` adds `web_requester_registrations`: a retry receipt, not a session
or credential. A retry uses the original request ID and exact non-password fields,
and must verify the original password. Competing requests are serialized and
partial failures roll back account/profile creation. The browser retains only the
request ID, non-password pending profile and confirmed login in session storage;
passwords are never persisted. A refresh after an uncertain response asks for the
password again and repeats the same attempt even if the profile schema changed.

Requester profiles require ФИО, «Отдел» and telephone/internal number plus any
published required custom fields. Location is hidden and optional; old required
location overrides are retired. Hidden historical location values are preserved.
Existing profiles may keep their own archived department when updating contacts;
the historical label remains readable, but that department is unavailable for new
profiles and other assignments. Existing incomplete accounts receive a profile
setup wizard without creating another account or changing their login.

The names-only catalog is `server/registry/requester_departments_20260831.json`.
`scripts/helpdesk_requester_departments.py::publish_department_catalog` plans or
applies its 30 shared departments on staging only. The caller must provide the
exact reviewed synthetic IDs/names, administrator actor, fresh private backup and
unchanged plan fingerprint. Canonical Registry operations archive synthetic
departments/locations with audit and retain all prior profile/device/history
references. A second publication is a no-op. Employees from the source DOCX are
not imported, and the two employment groups do not produce separate departments.

The new-request catalog has one whole-catalog search. Focusing it with an empty
query opens all available categories; a guided category expands its published
problem entrances. Expansion does not start a scenario. Choosing a problem starts
or resumes that entrance; ordinary categories open the existing form. There is no
additional category select or within-category search on this page. Server search,
availability checks, direct links, owner-scoped scenario selection and form drafts
remain authoritative. Search errors remain distinct from no matches.

Device linking explains how to open the Windows tray, right-click Endpoint Agent,
choose «Привязать компьютер к Helpdesk», and copy the code. Optional tray/menu
illustrations are under `webapp/src/assets/guides`; no actual code is published.
Expiry/renewal and missing-agent guidance keep the ordinary support path available.
The code remains Endpoint-owned possession proof; Helpdesk binding and conflict
review are unchanged.

On the approved staging host (`test-helpdesk`, `192.168.101.118`), run
`python scripts/configure_helpdesk_registration.py --enabled true` to enable
requester registration (`false` disables it). The utility updates only
`WEB_SELF_REGISTRATION_ENABLED` in `/etc/helpdesk-staging/helpdesk.env`, retains
a private backup, and preserves unrelated settings. Restart only
`helpdesk-staging.service` through `scripts/manage_remote_stack.py` using the
staging remote profile, then verify `/api/web/session/capabilities` and the
registration flow. New accounts always receive role `user`; this does not
provision AD accounts or grant support/administrator privileges.

Earlier staging acceptance on 2026-11-04, before guided onboarding: registration was enabled with a private
configuration backup; unrelated configuration and file permissions were verified
unchanged. Helpdesk was restarted through the project lifecycle command and
left running. TLS health returned 200, registration and SSO capabilities were
both true, and the application release remained `376b46c012160473fe2ebc40a0185784f692e487`.
Live browser registration returned 201; first login returned 200 and opened the
requester workspace. The new synthetic account had role `user` and only the
`requester` workspace. The new-ticket page opened and requested profile
completion before ordinary catalog requests. At that checkpoint registration did
not complete the personal profile automatically. Two synthetic accounts with prefix
`registration.check.20261104.` were created during verification; the first UI
run reached successful registration but its verification callback failed, so
first-login acceptance used the second account. No real employee credentials
were reset. Browser console errors and failed application requests were absent
in the successful run. The configuration utility's three tests and
`python scripts/verify_workspace.py` passed; no frontend assets or application
code were changed or redeployed.

Retired Helpdesk browser pairing and account-session issuance remain unavailable.

| Route | Purpose | Authority | Evidence |
| --- | --- | --- | --- |
| `/app/requester/devices` | Read the requester's existing device bindings and open device binding. | Authenticated Helpdesk requester. | Redacted Registry device projection. |
| `/app/requester/devices/link` | Enter an Endpoint one-time device code. | Authenticated requester with a complete RegistryPerson profile; Endpoint verifies possession, Registry decides ownership. | Registry binding/claim and bounded audit, never the code. |
| `/app/requester/new` | Create a Helpdesk ticket. | Authenticated requester and Helpdesk ticket policy. | Ticket/audit record and Endpoint-backed diagnostic facade where applicable. |
| `/app/admin/registry` | Administer people, bindings, registration claims, profiles and password-reset requests. | Helpdesk RBAC. | Registry audit event with a redacted before/after projection. |

Endpoint Platform alone owns agent enrollment, agent connectivity and all
device-control workflows. Helpdesk consumes only the documented Endpoint
operation contract and preserves `/ws_ui` browser notifications.

Requesters and administrators must never receive raw credentials, tokens,
internal identifiers, endpoint operation secrets, or database metadata. A
retired Helpdesk legacy endpoint must return `404` or `410`.

## Device binding

The requester home uses a light, requester-only shell and two primary destinations:
create an обращение and open own tickets. Recent tickets use grouped rows, followed
by compact, server-derived profile and computer readiness. A linked offline computer
is distinguished from no binding, ambiguous primary selection and pending ownership
review. Pending consents retain explicit approval/denial; read errors never imply
that the profile, computer or consent check succeeded. Profile/create and ownership
guards remain authoritative in the existing routes and APIs; appropriate forms still
allow requests without a linked computer.

The existing Windows Endpoint tray offers copy, new-code and open-Helpdesk actions.
The device-link page separates Windows and Linux / ALT Linux instructions into
keyboard-accessible tabs. Windows retains optional screenshots. Current Linux
agents have no tray code-issuance UI: the guide asks for the hostname (system settings
or unprivileged `hostname`), OS and department in the existing owner-change assistance
flow. It does not promise self-service code issuance or direct access to protected
agent credentials. An already obtained valid code can still be entered manually.
Six ASCII digits (`123456` or `123-456`) expire after ten minutes and redeem once.
Browser links put the code only in a fragment. The application captures and removes
that fragment before auth routing, retains the code only in memory across login or
profile completion, and submits it only on the user's explicit action. Reloading
the application loses the code; no storage, cookie, query parameter or browser log
retains it. Logout and successful redemption clear it.

`POST /api/web/requester/devices/link` uses existing session, same-origin/CSRF and
HTTPS Endpoint adapter policies. It resolves a complete RegistryPerson before the
S2S redemption. The exact provider SHA and canonical OpenAPI hash are pinned in
`integration/endpoint_contract.lock.json`; the dedicated service scope is
`device-binding.redeem`. Endpoint does not assign a Helpdesk owner.

Registry migration `146` owns an exact, unique Endpoint-to-local-device mapping.
A new verified device receives a marked Registry projection. Existing legacy IDs,
hostnames and diagnostic ticket targets never establish this mapping. An ID
collision fails closed for administrator review. The person and device rows are
locked for activation; person status is refreshed after the provider call.
Free ownership activates through canonical Registry policy, same-owner primary
binding is idempotent, and existing/shared/ambiguous ownership creates an audited
claim for administrator review without replacing owners. The source and
verification marker are `endpoint_possession_proof`.
Administrator claim listings and Registry snapshots expose this bounded source
without challenge material. The requests tab labels it “Код привязки Endpoint”
and retains separate explicit administrator review for ownership conflicts.

## Tickets

Normal forms allow tickets without a computer by default. The historical policy
key `available_without_agent_binding` remains compatible; explicit `false` still
requires a selected device. Device-picker fields are optional for forms allowing
no-device submission. The requester selector preselects an available primary computer. Choosing
“Без компьютера” sends `device_scope: "none"` through preview, create and diagnostic context,
preventing automatic primary-device fallback. A selected device must pass existing
requester ownership authorization. An exact Registry mapping plus a fresh,
non-retired Endpoint projection is required before retaining a diagnostic reference.
Routing, SLA/OLA, chat, consent, resolution and requester-confirmed closure keep
their canonical workflows.

Live First Wave acceptance uses the isolated staging host and Windows test VM.
ALT Linux Agent binding acceptance is intentionally excluded. Unit and fixture
browser checks do not replace real tray, WSS, consent or lifecycle acceptance.
