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
3. Apply migrations through 161 with the normal staged release. An administrator can
   confirm a verified account using
   `PUT /api/web/admin/registry/people/{person_id}/inventory-link`, with
   `inventory_person_id`, `user_login` and a non-empty `reason`. The two IDs
   refer to different services. A name match is insufficient. Conflicting
   links return HTTP 409; removal is an explicit `DELETE` with a reason.
4. Open `/app/requester/profile` as the linked user. The separate requester
   API `GET /api/web/requester/inventory-devices` checks ownership and refreshes
   assignments. If the provider is unreachable, the last confirmed list is
   marked stale and its presence becomes unknown.
5. To test automatic bindings, set `HELPDESK_INVENTORY_AUTO_BIND_ENABLED=true`
   on Helpdesk staging. A confirmed employee/account link, a current confirmed
   assignment and a matching, non-retired Endpoint UUID are required. The
   reconciler applies the primary/shared relationship, checks Registry limits
   and records each activation and revocation. An explicit admin revocation
   blocks the same assignment evidence on later refreshes. Automatic bindings
   grant the existing ticket device selection for their validity period.
   Diagnostic actions still require the existing authorization and consent.

6. In a support ticket, open **Сведения**, **Контекст**, and then
   **Назначенные компьютеры** in the device section. Only operators who can
   read the ticket can read this list. The requester comes from the ticket
   record. Diagnostic readiness is read from the existing ticket capabilities
   API when the confirmed Endpoint UUID matches the ticket's target. The
   administrator can also open **Назначенные компьютеры** in the selected
   employee's **Профиль** under **Пользователи**. Set
   `HELPDESK_INVENTORY_WEB_URL` if the operator-facing HTTPS origin differs
   from the API origin. The links point to the specific inventory card and
   the agent section on that card, where web_ovpn checks its own permissions.

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

The worker refreshes links every two minutes and authorization checks the
five-minute confirmation deadline on every read. A successful refresh of
the inventory and Endpoint extends that deadline. Cached assignments remain
available for display during an outage. An independent six-digit possession
proof retains its own Registry binding when inventory changes.

Migration 161 stores automatic bindings in the `inventory_active` state.
Older app versions select `active`, so they do not use inventory grants.
Before rolling back, disable automatic binding on the new version and wait
for the worker to drain automatic bindings. Verify that no
`device_user_bindings` rows have status `inventory_active`. This also
releases the primary slot for legacy writes. The downgrade enforces this
condition before dropping the lease column.

To show Helpdesk account status in web_ovpn, set a second dedicated secret.
Put only its SHA-256 digest in `HELPDESK_INVENTORY_STATUS_TOKEN_HASH` on
Helpdesk. Configure `HELPDESK_INVENTORY_STATUS_BASE_URL`,
`HELPDESK_INVENTORY_STATUS_TOKEN_FILE` and, if needed,
`HELPDESK_INVENTORY_STATUS_CA_FILE` on web_ovpn. The HTTPS base is also used
for the operator link to the Helpdesk profile.

`POST /api/internal/inventory/v1/helpdesk-account-status` takes
`{"inventory_person_ids": [...]}` with 1–250 distinct employee UUIDs.
The `linked` array contains only requested UUIDs with a verified active
requester account, along with the Helpdesk person ID and login. Missing
entries in a successful response indicate no active verified link.
Authentication, transport or payload failures display unknown status in
web_ovpn and exclude those rows from the no-account filter.

The operator installation actions still need the existing Windows MSI and
ALT Linux workflows with verified Endpoint registration and heartbeat on
the staging test devices.
