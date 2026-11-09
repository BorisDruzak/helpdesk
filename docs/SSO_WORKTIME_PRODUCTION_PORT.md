# Selective SSO and WorkTime production port

The operator explicitly authorized this port on2026-11-09. Its base is the
actual production release6cca48e5780d625cace590e46a30212ca9ecfb4d/schema150.
The independent current staging Helpdesk contains other ongoing product work;
do not replace that deployment or transfer its unrelated features wholesale.

The port retains the reviewed confirmed-identity/OIDC implementation, callback
log hygiene, password-level domain login, profile-preserving recovery, fixed
environment navigation, source-session WorkTime handoff and refresh nonce fix.
Initial login always validates nonce. A refreshed ID token may omit it; a present
nonce must match. Studio, ticket behavior, WebPush, account unification and the
new requester-registration workflow are outside this change.

Canonical migrations151,152 and153 remain byte-identical to their original
staging revisions.152 creates an empty registration retry-receipt table and is
retained with its model solely as the original prerequisite of153. These
migrations do not bind people, change existing profiles or migrate accounts.
Rehearse150 to153 against a protected full production clone before activation;
keep private backups and the existing no-downgrade production migration gate.

Both actual Endpoint environments run818d2897b1d4b86bd0a90ed75729bdaa0d5f3170,
schema0051. The consumer lock pins that provider and canonical OpenAPI digest
1d2fce6b033fe8c46df9f65bb81eae9b285316abea065aa1bb8626fa1b991869.
Compared with the previous lock, no existing HTTP path or schema changed;
19 routes were added. Generated primitive-contract verification is unchanged.
Helpdesk source identity/WorkTime authority is a separate documented provider
boundary in [SSO_IDENTITY](../server/docs/SSO_IDENTITY.md).

Deployment uses the canonical exact-SHA CI and release procedure. Qualify the
candidate in a separate, disposable staging database/service; preserve the
existing staging service and its later schema/features. A protected production
clone is for migration rehearsal only, not a parallel runtime or worker.
Fixtures in disposable databases are test data, not live employee acceptance.
Record the actual TLS/API/browser checks and all qualification limits separately.

Enable the fixed production WorkTime handoff only with its prepared confidential
service credential, secure cookies/CSRF and paired Endpoint origin. Helpdesk
password sessions remain valid; a self-only WorkTime session does not grant
HR, DLP, administrator or other-person access. Enabling Helpdesk AD login and
migrating an account require an independently confirmed binding; never infer
one from a login, email or device account. Keep unconfigured AD login disabled.
An incomplete employee profile must fail closed. Finish actual cross-service
acceptance using an existing complete employee session; do not invent profile
fields, privileged principals, attendance events or device/person bindings.

Agent versions remain Windows177 and native Linux183. WorkTime uses the existing
agent's typed, credential-free user companion, explicit temporal account/device
bindings and server requests. Technical activity is not personnel attendance.
No agent rebuild, fleet assignment, GPO or Support policy change is part of this port.
