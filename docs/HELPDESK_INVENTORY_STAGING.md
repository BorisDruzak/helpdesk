# Inventory integration on staging

Registration supports an optional invitation to a specific employee. An
administrator can also connect inventory to an existing account after
identity verification. The integration is
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
3. Apply migrations through 160 with the normal staged release. An administrator can
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

For a new employee, open **Приглашение сотрудника из инвентаризации** in the
admin Registry. Copy the employee ID from the web_ovpn card, choose the
corresponding active Helpdesk department, and record why the invitation was
issued. The code expires after 30 minutes. Issuing a replacement invalidates
the previous code. An administrator can revoke the pending code. Manual
confirmation also invalidates a pending code for the same employee. The issue endpoint is
\`POST /api/web/admin/registry/inventory-invitations\`.

The employee enters the code in the ordinary registration wizard and confirms
the displayed name and department. Preview reveals only the selected record.
Registration checks the name and department against the invitation and consumes
it in the same transaction as account creation and linking. The browser keeps
the code in memory and asks for it again after a reload during an uncertain
submission. The server persists the digest in migration 160.

Migration 159 adds a dedicated local projection; it neither imports people nor
changes passwords, identities, devices or bindings. Rolling back the app
can leave the table in place. The migration rejects dropping a populated
table.

The remaining work includes the policy that synchronizes effective Endpoint
bindings with assignment changes and the operator installation actions. Installation must use the existing Windows MSI and
ALT Linux workflow with a verified Endpoint registration and heartbeat. No
production endpoint should be used for this staging acceptance.
