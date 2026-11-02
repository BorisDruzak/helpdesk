# Confirmed identity and OIDC foundation

Migration **151** adds `ui_users.password_login_enabled` (default true),
`ui_tokens.auth_method` (default password), confirmed identity bindings,
unconfirmed migration candidates, one-use OIDC flows and encrypted upstream
session authority. No existing login, role, ticket, person or consent is rewritten.

`auth/identity.py` is the authority for explicit person/account/AD/OIDC binding.
It requires an existing active RegistryPerson, active UiUser and the same person's
verified `ui_login` alias. It never calls generic identity upsert/normalization.
OIDC subjects are exact and case sensitive. Database uniqueness reserves issuer /
subject, AD GUID and UiUser even after revocation. Revocation cannot silently free
an identity for a different person. Merging either bound person is blocked;
changing an account or person to inactive/merged denies all roles at the next
protected request. Unmapped ordinary accounts keep their existing password path.

## Operator migration

The authenticated administrator cookie/header authority and existing same-origin
CSRF checks protect these POST operations:

- `/api/web/admin/identities/propose`: exact `person_id`, `user_login`, `issuer`,
  `subject`, `ad_object_guid`; returns a pending `candidate_id`, no access.
- `/api/web/admin/identities/confirm`: `candidate_id`, `verification_reference`;
  the administrator must independently verify the AD owner and legacy person / UI
  account before confirmation. A collision is retained as a conflict candidate.
- `/api/web/admin/identities/migrate-password`: `binding_id`,
  `verification_reference`; requires a currently valid, persisted, independently
  introspected SSO session for that binding before disabling password login.
  The same transaction revokes previously issued password-origin UiTokens;
  subsequent verification also rejects password tokens issued by a racing login.
- `/api/web/admin/identities/revoke`: `binding_id`; revokes the binding and all
  existing local UiTokens for its UiUser. It does not reenable password login.

These operations write UiUserAudit; they do not accept OIDC claims from an
employee browser as evidence of identity ownership. Password resets do not
reenable the migration flag. Retain a separately controlled unmapped emergency
administrator account under the organization's existing emergency-access policy;
this foundation adds no special password bypass or automatic emergency grant.

## Integration contract v1

`POST /api/integration/v1/identities/resolve` accepts exactly `issuer`, `subject`
and canonical lowercase UUID `ad_object_guid`. No person selector, contacts,
tickets, roles, passwords or tokens are returned. Success contains `version: 1`,
stable `person_id`, identical issuer / subject / AD GUID, `state: active` and
nullable `department_id`.

Only `Authorization: Bearer <IDENTITY_RESOLVE_SERVICE_TOKEN>` authorizes this
route. Configure a separate random credential of at least 32 characters, never an
ordinary UI or Endpoint device credential. The route authenticates itself and
never creates an AuthContext for other routes. Empty/short configuration fails
closed. Requests are limited to 4096 bytes;
responses disable caching. The authenticated shared service IP budget defaults to
6000 requests per minute, configurable with `IDENTITY_RESOLVE_RATE_LIMIT_PER_MINUTE`
(1–100000). Size this for department reads and active companion polling; an
ordinary interactive-login budget cannot serve a shared Endpoint client.
Production proxies must preserve correct trusted IP
configuration and enforce their own connection/rate limits across workers.

Status: 401 wrong service authority; 400 invalid body/issuer; 404 unknown;
409 conflicting or unconfirmed; 403 revoked/inactive; 429 rate limited;
503 unavailable/unconfigured. The exact issuer must match `OIDC_ISSUER`.

## OIDC BFF configuration

`OIDC_ENABLED` defaults false. Required runtime settings when enabled:

- `OIDC_ISSUER`: exact HTTPS realm issuer, without a query or fragment.
- `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET`: independent confidential Helpdesk
  client, Authorization Code only, PKCE S256 required; sign ID tokens with RS256.
- `OIDC_REDIRECT_URI`: exact HTTPS
  `https://<helpdesk-host>/api/web/session/oidc/callback`; register only this URL.
- `OIDC_TOKEN_ENCRYPTION_KEY`: Fernet key, supplied from protected runtime secrets,
  independent of every client/service credential. Retain it only while the
  corresponding unexpired flows/sessions are needed. Rotation invalidates them.
- AD SSO uses the domain password for every Helpdesk role, including support,
  administrators and auditors. Helpdesk does not request `acr_values` or require
  an MFA `acr` on login, session validation or refresh. `OIDC_PRIVILEGED_ACR` is
  deprecated and ignored, including when still present in an existing environment.
  The identity provider's Helpdesk client must also use password-level defaults
  and minimum assurance; an upstream OTP enrollment/flow requirement can still
  prompt for OTP independently of Helpdesk. Apply provider changes through its
  reviewed configuration workflow, scoped to the intended Helpdesk client.
- `OIDC_AD_GUID_CLAIM` defaults `ad_object_guid`. Configure canonical AD objectGUID
  UUID in signed ID tokens. Introspection must return active, sub, iss, client_id,
  exp and matching sid when ID token supplied sid.
- `OIDC_CA_FILE`: optional PEM trust bundle for an internal issuer CA. The same
  verified SSLContext covers discovery, JWKS, code exchange, refresh and
  introspection. An unreadable/invalid configured CA fails closed; TLS verification
  cannot be disabled.
- `OIDC_END_SESSION_ENDPOINT` / `OIDC_POST_LOGOUT_REDIRECT_URI`: optional fixed
  HTTPS provider endpoint and exact registered Helpdesk post-logout redirect.
  The provider endpoint must share the issuer origin; the redirect must share the
  configured callback origin. No request-supplied logout URL is accepted.
- Secure cookies and same-origin CSRF protection must be enabled. OIDC mode
  forces database password authentication and disables insecure config/memory
  auth fallback. These settings are never deployment defaults for an unconfigured
  local development environment.

`GET /api/web/session/oidc/login` stores an encrypted PKCE verifier, nonce and
hashed state/browser binding in PostgreSQL for five minutes. It redirects through
Authlib and sets a secure HttpOnly SameSite=Lax flow cookie.
`GET /api/web/session/oidc/callback` atomically consumes that state before code
exchange, validates RS256 / issuer / audience / expiry / nonce with Authlib's
CodeIDToken and joserfc, then resolves only the explicit confirmed binding.
It transactionally persists the existing hashed UiToken authority plus encrypted
upstream access/refresh tokens and issues the existing HttpOnly browser cookie. No OAuth
token, verifier or refresh token reaches browser JavaScript. Success redirects
to `/app`; no arbitrary return URL is accepted.

The initial access/ID token validity is capped at 15 minutes. When a refresh
token is issued, the opaque local session/cookie has a fixed eight-hour maximum;
without refresh it expires with the initial token. At 30 seconds before access
expiry, Authlib refreshes under a PostgreSQL row lock, revalidates signed ID claims,
the exact identity and session, and stores rotated encrypted tokens. A returned
`acr` is retained as session metadata and is not a role authorization source.
Refresh never extends the eight-hour ceiling. A denied refresh, changed identity,
bad signature or provider outage grants no operation. Refreshed ID tokens must
include the original nonce, AD GUID and session identity.

Every protected operation rechecks current
UiUser/role, binding/person/verified alias and performs authenticated upstream
introspection; provider outage, revoked session or changed issuer fails closed
immediately with no positive cache. This favors prompt revocation over provider
outage availability and adds one discovery + introspection round trip to each
operation. Metadata/JWKS endpoints must be HTTPS on the configured issuer origin;
redirects and ambient proxies are disabled. `POST /api/web/session/logout` revokes
the possessed local UiToken and deletes the cookie without first introspecting
upstream authority. Same-origin CSRF checks still apply. Optional
`POST /api/web/session/oidc/logout` completes the same local operation before a
303 to the fixed RP logout endpoint. It uses client_id and the registered redirect,
never a token in the browser URL; the provider may ask for logout confirmation.
Local logout remains available while the issuer is offline.
For a native browser POST (`Accept: text/html`), missing or rejected optional RP
configuration returns a 303 to the fixed `/app/login` after local revocation and
cookie deletion. JSON API callers retain the ordinary local logout response.

### Helpdesk staging provider assurance

`scripts/configure_helpdesk_sso_password.py` is the fixed staging provider
helper. Run it as root on the existing SSO host `192.168.100.19`; default mode
only reads policy and prints a nonsecret `before_sha256`. After reviewing that
plan, `--apply --expected-sha256 <before_sha256>` changes only
`helpdesk-staging-web`'s `default.acr.values` and `minimum.acr.value` to level 1.
It reads the existing protected provisioning credential in memory, refuses
custom client flows, retains PKCE and writes a private metadata backup under
`/var/backups/keycloak/helpdesk-password-*/client.json` before its single REST
update. It rereads the full client and verifies the five other application
clients unchanged. No credential, role, user required action or realm flow is
changed. A failure after PUT requires inspecting the current client and private
backup before retry; the helper never silently retries or rolls back an uncertain
write. Production Helpdesk and Endpoint clients are outside this helper's scope.
The update explicitly retains `webOrigins`, including an empty list, because
Keycloak infers a redirect origin when that field is omitted. For the verified
legacy partial-update case only, `--reconcile-backup <private-client.json>` plans
restoring the original empty origins while retaining password assurance; apply
still requires the current fingerprint. Any other full-client difference refuses
this reconciliation.
Deploy the matching Helpdesk code through the canonical release script; changing
only the provider leaves the old privileged-session check in place.

## Browser entry and employee navigation

`GET /api/web/session/capabilities` publicly returns only the nonsecret boolean
policies `self_registration_enabled` and `sso_enabled` (from `OIDC_ENABLED`),
with `Cache-Control: no-store`. `/app/login` offers the domain-account entry only
when SSO is enabled. It navigates to the fixed same-origin OIDC login route;
browser query parameters cannot choose an issuer, callback or return target.
The existing password form remains available for gradual migration. Failed or
legacy capabilities responses hide the SSO entry; they do not prevent password
login. The login form remains first on small screens.

Authenticated session payloads retain `auth_type: ui_token` and expose a separate
`login_method: password|oidc` derived from the verified persisted credential.
This field selects the logout flow and grants no permissions. OIDC logout clears
the actor's query cache and drafts, then submits a top-level POST to the fixed
OIDC logout route so the server's optional RP redirect can proceed. The browser
never stores or receives OAuth token material. Password sessions keep the
existing local logout API. A login-method change also resets the actor cache.

`WORKTIME_PORTAL_URL` defaults blank. The server accepts only these exact pairs
of `SERVER_PUBLIC_BASE_URL` and employee portal:

| Helpdesk public origin | WorkTime portal |
| --- | --- |
| `https://helpdesk.sosnadmin.local` | `https://endpoint.sosnadmin.local/employee` |
| `https://helpdesk-staging.sosnadmin.local` | `https://endpoint-staging.sosnadmin.local/employee` |

Unknown origins, mixed environments, and decorated URLs (userinfo, port, query,
fragment or other paths) keep the link hidden. Selection uses configured origins,
never a request Host/forwarded header. This nonsecret URL appears as nullable
`worktime_portal_url` in the
authenticated session payload. The requester desktop/mobile navigation shows
“Рабочее время”; it never appends a person ID, device authority or user credential.
The portal authorizes the employee independently through its own session.
The shared frontend link repeats the exact two-URL allowlist and sends no Referer.

Frontend regressions: `webapp/tests/sso-worktime.spec.ts` (fixture browser
entry/policy failure, trusted navigation at desktop/mobile widths and native
POST logout) and focused auth/shell component tests. Fixture evidence does not
establish actual issuer/AD availability or independent WorkTime authorization.

Use `test_sso_identity.py`, `test_sso_oidc.py` and `test_sso_tls.py` for local contract,
real-library flows and generated-private-CA TLS regressions. These tests are not evidence of real AD/LDAPS/MFA
acceptance. Run a pilot with the actual issuer, its TLS/LDAPS CA and confirmed
operator-approved identities before enabling SSO in a live environment.

## Callback logging and deployment

`observability/access_log.py` supplies `QuerySafeAccessLogger` to `web.run_app`.
Its JSON records retain method, path, status, response bytes and elapsed time;
query strings, Referer, Authorization and response headers are never fields.
The exact OIDC callback has an unexpected-error boundary that logs only the
exception type and a constant outcome. Existing HTTP redirects, request IDs,
authentication/observer audit events and ordinary error diagnostics remain.

`deploy/helpdesk/helpdesk.nginx.conf` defines its own `helpdesk_path_only`
format in the nginx HTTP context. Both HTTP redirect and HTTPS servers write
`/var/log/nginx/helpdesk.access.log` using `$uri`, without query or header fields.
Only `/api/web/session/oidc/callback` discards nginx's unformatted upstream error
messages, which otherwise contain raw request URLs. The safe access outcome
still records callback failure; other nginx error logging stays unchanged.

Deploy the application through the normal reviewed release procedure; merely
updating nginx does not replace an already running aiohttp logger. A bounded
config-only repair is available in Endpoint's operator tooling:
`tools/release/apply_query_safe_nginx.py --site helpdesk --source <reviewed-asset>
--source-sha256 <reviewed-sha256>` validates a plan on `.19`; add `--apply` only
after independent review. It checks the existing enabled-site target, validates
the complete candidate configuration, preserves exact old bytes by hash and
restores/reloads the original on failure. It changes no application, DB or env
files. The canonical asset uses port 8666 and must not be substituted for a
staging profile with different paths or ports.

`tools/release/verify_query_safe_nginx.py --site helpdesk --asset <reviewed-asset>`
starts an isolated loopback nginx with a deliberately unavailable upstream and
synthetic callback code/state/Referer values. Its result reports only sentinel
counts and preserved path/status/metrics, never raw logs. Existing private logs
are not inputs to this check. `server/tests/test_access_log_no_db.py` covers the
real aiohttp logger, redirects, callback failures and request-ID preservation.
