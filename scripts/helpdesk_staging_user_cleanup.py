#!/usr/bin/env python3
"""Reversible, reviewed cleanup for the approved Helpdesk staging test accounts.

Plan first; apply requires the same user-state fingerprint and a verified fresh
staging backup. Never deletes users, people, tickets, events or memberships.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from datetime import datetime, timezone

KEEP = {"admin": "admin", "admin-2": "admin", "bdryzhak": "user"}
TEST_PREFIXES = (
    "cutover_", "guided-studio-", "isolation_", "outage_", "phase1.",
    "prod_", "readiness_v1_", "registration.check.", "sentry_release_",
    "sso-life-", "staging-", "throttle_",
)
TEST_LOGINS = {"studio.user", "test_01", "tproverochnyy-onbording"}
REASON = "Authorized staging cleanup: retain admin, admin-2 and bdryzhak; preserve ticket history."


def build_plan(users) -> dict:
    rows = sorted(
        [{"user_login": u.user_login, "actor_role": u.actor_role, "is_active": bool(u.is_active)} for u in users],
        key=lambda row: row["user_login"],
    )
    by_login = {row["user_login"]: row for row in rows}
    if any(login not in by_login or by_login[login]["actor_role"] != role or not by_login[login]["is_active"]
           for login, role in KEEP.items()):
        raise ValueError("Protected accounts must exist, remain active and retain their explicit roles")
    candidates = [row for row in rows if row["user_login"] not in KEEP]
    if any(row["user_login"] not in TEST_LOGINS and not row["user_login"].startswith(TEST_PREFIXES) for row in candidates):
        raise ValueError("Unexpected non-test account; cleanup refused")
    return {
        "keep": sorted(KEEP), "disable": [row["user_login"] for row in candidates],
        "active_to_disable": sum(row["is_active"] for row in candidates),
        "fingerprint": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
    }


async def apply_to_session(session, expected_fingerprint: str) -> dict:
    from sqlalchemy import select, text
    from app.db.models import RegistryPerson, RegistryPersonIdentity, UiUser
    from registry.admin_operations_service import RegistryAdminOperationsService
    from web_api.registry_handlers import _disable_ui_user_access

    # Prevent a concurrent signup/role/status edit between planning and apply.
    await session.execute(text("LOCK TABLE ui_users IN SHARE ROW EXCLUSIVE MODE"))
    users = (await session.execute(select(UiUser).order_by(UiUser.user_login).with_for_update())).scalars().all()
    plan = build_plan(users)
    if plan["fingerprint"] != expected_fingerprint:
        raise ValueError("Account state changed after plan; cleanup refused")
    revoked = 0
    for user in users:
        if user.user_login in KEEP:
            continue
        result = await _disable_ui_user_access(
            session, user, actor_id="staging-cleanup-20261105", reason=REASON,
            action="disabled_by_staging_cleanup",
        )
        revoked += int(result["revoked_ui_tokens"])

    # Remove only the observed fixture label from the already verified admin
    # person. Never infer a real name, rebind an identity or rewrite snapshots.
    person = await session.scalar(
        select(RegistryPerson).join(RegistryPersonIdentity,
            RegistryPersonIdentity.person_id == RegistryPerson.person_id)
        .where(RegistryPersonIdentity.provider == "ui_login",
               RegistryPersonIdentity.normalized_identifier == "admin",
               RegistryPersonIdentity.verified.is_(True))
        .with_for_update(of=RegistryPerson)
    )
    profile_corrected = False
    fixture_name = "Тестовый Пользователь 1"
    if person is not None and person.full_name == fixture_name and person.display_name == fixture_name:
        person.full_name = None
        person.display_name = "admin"
        person.updated_at = datetime.now(timezone.utc)
        await RegistryAdminOperationsService(session).append_event(
            object_type="person", object_id=person.person_id, event_type="person_updated",
            actor_id="staging-cleanup-20261105", actor_role="admin", reason=REASON,
            payload={"fields": ["full_name", "display_name"], "removed_fixture_label": True},
        )
        profile_corrected = True
    await session.flush()
    active = (await session.execute(select(UiUser.user_login).where(UiUser.is_active.is_(True)).order_by(UiUser.user_login))).scalars().all()
    if list(active) != sorted(KEEP):
        raise ValueError("Unexpected active accounts; transaction must roll back")
    return {**plan, "revoked_ui_tokens": revoked, "admin_fixture_label_removed": profile_corrected}


def verified_backup(marker: Path, release: str) -> None:
    from scripts.helpdesk_database_backup import libpq_environment
    value = json.loads(marker.read_text(encoding="utf-8"))
    artifact = Path(value["artifact"])
    if not artifact.resolve().is_relative_to(Path("/var/backups")):
        raise ValueError("Backup must remain in the private backup directory")
    finished = datetime.fromisoformat(value["finished_at"])
    age = (datetime.now(timezone.utc) - finished).total_seconds()
    if (value.get("status") != "success" or value.get("source_release") != release
            or value.get("database") != "helpdesk_staging_db" or not 0 <= age <= 3600
            or libpq_environment(os.environ["DATABASE_URL"])["PGDATABASE"] != "helpdesk_staging_db"
            or artifact.stat().st_size != value.get("size_bytes")):
        raise ValueError("Fresh verified staging backup required")
    with artifact.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != value.get("sha256"):
            raise ValueError("Backup digest mismatch")


async def run(args) -> dict:
    runtime = Path("/opt/helpdesk-staging/current").resolve()
    if socket.gethostname() != "test-helpdesk" or not re.fullmatch(r"[a-f0-9]{40}", args.release):
        raise ValueError("Approved staging host and frozen release required")
    if runtime.name != "helpdesk-" + args.release or runtime.parent != Path("/opt/helpdesk-staging/releases"):
        raise ValueError("Unexpected staging selector")
    sys.path.insert(0, str(runtime))
    sys.path.insert(0, str(runtime / "server"))
    from scripts.validate_production_config import read_environment
    from scripts.helpdesk_database_backup import libpq_environment
    settings = read_environment(Path("/etc/helpdesk-staging/helpdesk.env"))
    if libpq_environment(settings["DATABASE_URL"])["PGDATABASE"] != "helpdesk_staging_db":
        raise ValueError("Unexpected database")
    os.environ.update(settings)
    from app.db import get_session, init_db, shutdown_db
    from app.db.models import UiUser
    from sqlalchemy import select
    if args.apply:
        if not args.fingerprint or not args.backup_marker:
            raise ValueError("Plan fingerprint and backup marker required")
        verified_backup(args.backup_marker, args.release)
    try:
        await init_db(settings["DATABASE_URL"])
        async with get_session() as session:
            if args.apply:
                result = await apply_to_session(session, args.fingerprint)
                await session.commit()
                return {"status": "applied", **result}
            users = (await session.execute(select(UiUser))).scalars().all()
            return {"status": "plan", **build_plan(users)}
    finally:
        await shutdown_db()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--fingerprint")
    parser.add_argument("--backup-marker", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args))))


if __name__ == "__main__":
    main()
