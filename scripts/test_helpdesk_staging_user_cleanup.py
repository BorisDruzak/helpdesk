from types import SimpleNamespace
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest

from scripts.helpdesk_staging_user_cleanup import build_plan
import scripts.helpdesk_staging_user_cleanup as cleanup


def users():
    return [SimpleNamespace(user_login=login, actor_role=role, is_active=True)
            for login, role in [("admin", "admin"), ("admin-2", "admin"), ("bdryzhak", "user"), ("studio.user", "user")]]


def test_plan_preserves_explicit_accounts_and_is_bound_to_current_roles_and_status():
    rows = users()
    plan = build_plan(rows)
    assert plan["keep"] == ["admin", "admin-2", "bdryzhak"]
    assert plan["disable"] == ["studio.user"]
    rows[-1].is_active = False
    assert build_plan(rows)["fingerprint"] != plan["fingerprint"]


def test_unknown_employee_or_missing_protected_user_fails_closed():
    rows = users()
    rows.append(SimpleNamespace(user_login="new.employee", actor_role="user", is_active=True))
    with pytest.raises(ValueError, match="Unexpected non-test account"):
        build_plan(rows)
    with pytest.raises(ValueError, match="Protected accounts"):
        build_plan(users()[1:])


def test_cleanup_never_reactivates_or_changes_a_protected_role():
    rows = users()
    rows[0].is_active = False
    with pytest.raises(ValueError, match="Protected accounts"):
        build_plan(rows)
    rows = users()
    rows[1].actor_role = "user"
    with pytest.raises(ValueError, match="Protected accounts"):
        build_plan(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "read", "init"])
async def test_cli_initializes_and_disposes_its_validated_database(monkeypatch, failure):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "server"))
    import app.db
    import scripts.validate_production_config as config
    release = "a" * 40
    class RuntimePath(type(Path())):
        def resolve(self, *args, **kwargs):
            if str(self).replace("\\", "/") == "/opt/helpdesk-staging/current":
                return Path("/opt/helpdesk-staging/releases/helpdesk-" + release)
            return super().resolve(*args, **kwargs)
    monkeypatch.setattr(cleanup, "Path", RuntimePath)
    monkeypatch.setattr(cleanup.socket, "gethostname", lambda: "test-helpdesk")
    monkeypatch.setattr(sys, "path", sys.path.copy())
    url = "postgresql+asyncpg://fixture@127.0.0.1/helpdesk_staging_db"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(config, "read_environment", lambda _: {"DATABASE_URL": url})
    events = []
    async def init_db(value):
        assert value == url
        events.append("init")
        if failure == "init":
            raise RuntimeError("fixture init failed")
    async def shutdown_db():
        events.append("shutdown")
    @asynccontextmanager
    async def get_session():
        assert events == ["init"], "Standalone CLI must initialize its session maker"
        async def execute(_):
            if failure == "read":
                raise RuntimeError("fixture read failed")
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: users()))
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(app.db, "init_db", init_db)
    monkeypatch.setattr(app.db, "shutdown_db", shutdown_db)
    monkeypatch.setattr(app.db, "get_session", get_session)
    if failure:
        with pytest.raises(RuntimeError, match="fixture .* failed"):
            await cleanup.run(SimpleNamespace(release=release, apply=False))
    else:
        result = await cleanup.run(SimpleNamespace(release=release, apply=False))
        assert result["status"] == "plan"
    assert events == ["init", "shutdown"]


def test_backup_guard_rejects_tampering_expiry_and_other_database(tmp_path, monkeypatch):
    artifact = tmp_path / "backup.dump"
    artifact.write_bytes(b"synthetic fixture, not a database")
    marker = tmp_path / "backup.json"
    release = "a" * 40
    value = {"artifact": str(artifact), "status": "success", "source_release": release,
             "database": "helpdesk_staging_db", "size_bytes": artifact.stat().st_size,
             "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
             "finished_at": datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(cleanup, "Path", lambda value: tmp_path if value == "/var/backups" else Path(value))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://fixture@127.0.0.1/helpdesk_staging_db")
    marker.write_text(json.dumps(value), encoding="utf-8")
    cleanup.verified_backup(marker, release)
    artifact.write_bytes(b"changed bytes")
    with pytest.raises(ValueError):
        cleanup.verified_backup(marker, release)
    artifact.write_bytes(b"synthetic fixture, not a database")
    for changes in ({"finished_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}, {"database": "other_database"}):
        marker.write_text(json.dumps(value | changes), encoding="utf-8")
        with pytest.raises(ValueError):
            cleanup.verified_backup(marker, release)
