# Inventory integration on staging

Keep the existing requester registration and login paths. Inventory can be
connected by an administrator after identity verification. The integration is
disabled when `HELPDESK_INVENTORY_BASE_URL` is unset; registration, login and
profile editing remain independent of web_ovpn.

1. Start a separate web_ovpn staging instance with a synthetic inventory and
   the web_ovpn Helpdesk inventory API. The production web installer is not
   suitable for this. Set a dedicated credential digest on the provider
   (`HELPDESK_INVENTORY_TOKEN_HASH`).
2. Configure the Helpdesk staging service with the provider HTTPS origin
   (`HELPDESK_INVENTORY_BASE_URL`), an access-restricted file holding the token
   (`HELPDESK_INVENTORY_TOKEN_FILE`) and, if needed, the trusted provider CA
   (`HELPDESK_INVENTORY_CA_FILE`). Do not reuse either Endpoint or operator
   credentials. The client rejects redirects, plaintext and untrusted TLS.
3. Apply migration 159 with the normal staged release. An administrator can
   confirm a verified account using
   `PUT /api/web/admin/registry/people/{person_id}/inventory-link`, with
   `inventory_person_id`, `user_login` and a non-empty `reason`. The two IDs
   refer to different services. A name match is insufficient. Conflicting
   links return HTTP 409; removal is an explicit `DELETE` with a reason.
4. Open `/app/requester/profile` as the linked user. The separate requester
   API `GET /api/web/requester/inventory-devices` checks ownership and refreshes
   assignments. If the provider is unreachable, the last confirmed list is
   marked stale and its presence becomes unknown. The integration grants no
   diagnostic or ticket-device permissions. The device action uses only the
   devices already authorized by the existing profile.

Migration 159 adds a dedicated local projection; it neither imports people nor
changes passwords, identities, devices or bindings. Rolling back the app
can leave the table in place. The migration rejects dropping a populated
table.

The next stage is the operator UI, one-time invitation or pre-registration
confirmation, and the policy that synchronizes effective Endpoint bindings
with assignment changes. Installation must use the existing Windows MSI and
ALT Linux workflow with a verified Endpoint registration and heartbeat. No
production endpoint should be used for this staging acceptance.
