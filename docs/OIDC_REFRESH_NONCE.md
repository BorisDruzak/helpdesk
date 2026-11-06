# OIDC refresh ID tokens

`server/auth/oidc.py` validates the initial authorization response with the
saved nonce. During refresh only, an absent nonce is permitted by OIDC Core
§12.2. A present nonce, including null or an empty value, must match the original.
The refresh call explicitly selects this mode; token claims cannot enable it.

Signature, issuer, audience, expiry, AD identity binding, upstream session ID,
introspection, refresh rotation locking and the eight-hour session ceiling remain
required. This does not extend a revoked or expired provider session.

Regression coverage in `server/tests/test_sso_oidc.py` includes strict initial
nonce checks, optional refresh nonce, malformed nonce rejection and a provider
that omits nonce during refresh while rotating its tokens.

Reference: https://openid.net/specs/openid-connect-core-1_0.html#RefreshTokenResponse
