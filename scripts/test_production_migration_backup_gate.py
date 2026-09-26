import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("arguments", [["-c", "alembic.ini", "upgrade", "head"],
                                      ["revision", "--autogenerate"], ["stamp", "head"]])
def test_production_rejects_unreviewed_alembic_argument_forms(monkeypatch, tmp_path, arguments):
    path = Path(__file__).resolve().parents[1] / "server/scripts/run_migrations.py"
    spec = importlib.util.spec_from_file_location("migration_entrypoint", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / "absent")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://helpdesk@localhost/helpdesk")
    monkeypatch.setattr(module.sys, "argv", ["run_migrations.py", *arguments])
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: pytest.fail("unsafe Alembic invocation"))
    assert module.main() == 1


def test_failed_backup_never_invokes_alembic(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "server/scripts/run_migrations.py"
    spec = importlib.util.spec_from_file_location("migration_entrypoint", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / "absent")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://helpdesk@localhost/helpdesk")
    monkeypatch.setattr(module.sys, "argv", ["run_migrations.py", "upgrade", "head"])
    def forbidden(*args, **kwargs):
        pytest.fail("Alembic must not run without a verified backup")
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    assert module.main() == 1


def test_production_downgrade_is_not_automatic_recovery(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / "server/scripts/run_migrations.py"
    spec = importlib.util.spec_from_file_location("migration_entrypoint", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / "absent")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://helpdesk@localhost/helpdesk")
    monkeypatch.setattr(module.sys, "argv", ["run_migrations.py", "downgrade", "-1"])
    assert module.main() == 1


def test_verified_config_but_failed_backup_blocks_alembic(monkeypatch, tmp_path):
    import json
    import scripts.helpdesk_database_backup as backups
    import shared.production_security as policy
    path = Path(__file__).resolve().parents[1] / "server/scripts/run_migrations.py"
    spec = importlib.util.spec_from_file_location("migration_entrypoint", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    release = tmp_path / "release"; (release / "server").mkdir(parents=True)
    (release / "release-identity.json").write_text(json.dumps({"helpdesk_git_sha": "a" * 40}))
    monkeypatch.setattr(module, "SERVER_DIR", release / "server")
    monkeypatch.setattr(module, "ENV_FILE", tmp_path / "absent")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://helpdesk@localhost/helpdesk")
    monkeypatch.setenv("PC_CLIENT_SERVER_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("TECH_BACKUP_STATUS_PATH", str(tmp_path / "backup.json"))
    monkeypatch.setattr(policy, "production_config_errors", lambda _: [])
    attempts = []
    def failed_backup(*args):
        attempts.append("backup")
        raise RuntimeError("backup failed")
    monkeypatch.setattr(backups, "create_verified_backup", failed_backup)
    monkeypatch.setattr(module.sys, "argv", ["run_migrations.py", "upgrade", "head"])
    def forbidden(*args, **kwargs):
        pytest.fail("Alembic started after a failed backup")
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    assert module.main() == 1
    assert attempts == ["backup"]
