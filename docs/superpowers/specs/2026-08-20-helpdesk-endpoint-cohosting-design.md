# Helpdesk Co-hosting on Endpoint Platform Production Host Design

## Status

Approved architecture decisions are recorded below. This document covers the
Helpdesk relocation only; Endpoint Platform source remains a read-only contract
and deployment reference.

## Goal

Deploy a fresh, independently operated Helpdesk service on
`osn_admin@192.168.100.19`. The
service is colocated with Endpoint Platform but is not merged with it.

The initial Helpdesk database is empty except for a newly bootstrapped
administrator. No tickets, identities, users, sessions, agents, device rows,
tokens, attachments, audit history, or other Helpdesk data is copied from the
retired host. Existing agents are deliberately out of scope: a future
authentication and connection design will onboard them.

## Target Architecture

```text
                         192.168.100.19

helpdesk.sosnadmin.local -> Nginx -> 127.0.0.1:8666 -> Helpdesk systemd unit
                                                |-> helpdesk PostgreSQL database
                                                |-> /var/lib/helpdesk runtime data

endpoint.sosnadmin.local -> Nginx -> 127.0.0.1:8000 -> Endpoint systemd unit
                                                |-> endpoint_platform PostgreSQL database

Helpdesk -- HTTPS, CA validation, scoped service bearer --> Endpoint API v1
```

Helpdesk has its own Git repository, immutable release directories below
`/opt/helpdesk/releases`, `current` symlink, Unix account, root-owned
environment/secrets, PostgreSQL role/database, systemd units, data directory,
Nginx virtual host, log stream, and rollback marker. Endpoint resources are
never reused except the host OS, PostgreSQL server, Nginx process, network, and
versioned public Endpoint API.

## Deployment Model

Use archive-based immutable releases, modelled on the Endpoint production
procedure rather than the retired host's Git-working-tree deployment:

1. run the local verification gate and identify the exact Helpdesk commit;
2. build an archive without `.git`, environment files, certificates, or
   secrets;
3. install it under `/opt/helpdesk/releases/helpdesk-<commit>` with a private
   venv and atomically update `/opt/helpdesk/current`;
4. run one forward-only Alembic upgrade against the new `helpdesk` database;
5. start dedicated systemd units, validate loopback health, then enable the
   Helpdesk Nginx vhost; and
6. retain the previous immutable release for application rollback. Database
   rollback is restore-from-backup only, never automatic Alembic downgrade.

The release procedure uses only the dedicated Helpdesk deployment profile and
must not reuse legacy Git, SMB, or runtime paths.

## Configuration and Secrets

Copy the current Helpdesk environment file to the new host only through a
privileged, root-owned transfer path; do not put it in Git or print its values.
Review it key-by-key before activation:

- replace host- and path-specific settings with the Helpdesk runtime paths and
  final public URL;
- create a dedicated local PostgreSQL URL/role/database;
- preserve only features explicitly needed for the clean deployment;
- retain or reconfigure Remote Assist, TURN/ICE, Guacamole, release markers,
  and other integration settings only after their endpoints are validated from
  the new host; and
- provision an independent Helpdesk-to-Endpoint service credential and CA path
  when Endpoint Operations is enabled.

No retired database data, token rows, cookie/session data, device records, or
agent credentials is copied as part of environment transfer.

## Network and TLS Phases

The destination has a valid wildcard certificate for `*.sosnadmin.local`, but
`helpdesk.sosnadmin.local` does not yet resolve. The permanent configuration is
therefore blocked on a DNS A record for `192.168.100.19`, a Helpdesk Nginx
server name, certificate/key deployment, HTTPS/WSS enforcement, secure cookies,
and browser smoke through that FQDN.

The user authorized a short IP-only bootstrap phase before certificate setup.
It is limited to the administrative network, contains no agents or production
data, and is explicitly not a production acceptance state. The implementation
must make the exposure reversible and cannot report a production-ready release
until the TLS/FQDN gate passes.

## Endpoint Integration

Helpdesk continues to use `EndpointPort` and the versioned Endpoint Operations
API v1. Co-location does not permit direct imports, a shared database, local
loopback shortcuts without TLS, or cross-domain foreign keys.

Before enabling Helpdesk endpoint diagnostics, Endpoint Platform must enable
`ENDPOINT_OPERATIONS_API_ENABLED` and provision a least-privilege service
identity for Helpdesk. Helpdesk must use `https://endpoint.sosnadmin.local`,
the trusted local CA, and only the scoped bearer in its root-owned environment.
Until that acceptance is complete, the existing fail-closed unavailable mode
remains active.

## Agent and User Scope

The fresh Helpdesk database has no agent/device/authentication state. Existing
agents cannot authenticate against it and are intentionally not migrated,
registered, or redirected by this work. The sole initial account is a new
administrator created through the approved bootstrap mechanism. User and agent
onboarding are separate follow-up work.

## Verification and Rollback

Each release must prove: package integrity; environment parsing without secret
output; fresh schema at Alembic head; loopback health; service isolation and
least-write systemd settings; Nginx configuration; restricted bootstrap access;
and, at final acceptance, DNS, TLS hostname/chain validation, HTTPS/WSS,
secure-cookie login, admin browser flow, and service-to-service Endpoint API
health.

Application rollback changes the Helpdesk `current` symlink to the recorded
previous release and restarts only Helpdesk services. It never restarts or rolls
back Endpoint Platform. If a database migration has run, rollback requires an
approved restore of a verified Helpdesk database backup.

## Non-goals

This work does not alter Endpoint Platform source, make a monolith, migrate
retired Helpdesk data, enroll agents, weaken the final TLS/authentication
requirements, or decommission the retired host without a separate approved
retention/decommission procedure.
