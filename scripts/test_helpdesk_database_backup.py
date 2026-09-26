import json
import subprocess

import pytest

from scripts.helpdesk_database_backup import create_verified_backup, libpq_environment, restore_drill


def test_credentials_are_only_runtime_subprocess_environment():
    env = libpq_environment("postgresql+asyncpg://helpdesk:p%40ss@127.0.0.1:5432/helpdesk")
    assert env["PGPASSWORD"] == "p@ss"
    assert env["PGDATABASE"] == "helpdesk"


@pytest.mark.parametrize("failure", ["pg_dump", "pg_restore"])
def test_backup_failure_never_publishes_success(tmp_path, failure):
    def run(argv, **kwargs):
        if argv[0] == failure:
            raise subprocess.CalledProcessError(1, argv, stderr="private detail")
        if argv[0] == "pg_dump":
            __import__("pathlib").Path(argv[-1]).write_bytes(b"PGDMPtest")
        return subprocess.CompletedProcess(argv, 0, stdout="143\n")
    marker = tmp_path / "backup-status.json"
    with pytest.raises(RuntimeError, match="backup failed"):
        create_verified_backup("postgresql://helpdesk@localhost/helpdesk", tmp_path / "backups", marker, "a" * 40, run=run)
    assert json.loads(marker.read_text())["status"] == "failed"


def test_verified_backup_has_digest_revision_and_private_mode(tmp_path):
    def run(argv, **kwargs):
        assert not any("postgresql:" in item for item in argv)
        if argv[0] == "pg_dump":
            __import__("pathlib").Path(argv[-1]).write_bytes(b"PGDMPtest")
        return subprocess.CompletedProcess(argv, 0, stdout="143\n")
    marker = tmp_path / "backup-status.json"
    result = create_verified_backup("postgresql://helpdesk@localhost/helpdesk", tmp_path / "backups", marker, "a" * 40, run=run)
    assert result["status"] == "success"
    assert result["pre_migration_revision"] == "143"
    assert len(result["sha256"]) == 64
    assert result["format"] == "postgres-custom"
    assert "password" not in marker.read_text()


@pytest.mark.parametrize("fail_restore", [False, True])
def test_restore_drill_drops_only_its_disposable_database(tmp_path, fail_restore):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "pg_dump":
            __import__("pathlib").Path(argv[-1]).write_bytes(b"PGDMPtest")
        if fail_restore and argv[0] == "pg_restore" and "--exit-on-error" in argv:
            raise subprocess.CalledProcessError(1, argv)
        output = "t" if argv[0] == "psql" and "to_regclass" in argv[-1] else "143"
        return subprocess.CompletedProcess(argv, 0, stdout=output)
    backup = tmp_path / "backup.json"; output = tmp_path / "restore.json"
    create_verified_backup("postgresql://helpdesk@localhost/helpdesk", tmp_path / "backups", backup, "a" * 40, run=run)
    if fail_restore:
        with pytest.raises(RuntimeError):
            restore_drill("postgresql://test_admin@localhost/postgres", backup, output, run=run)
        assert json.loads(output.read_text())["status"] == "failed"
    else:
        assert restore_drill("postgresql://test_admin@localhost/postgres", backup, output, run=run)["status"] == "success"
    drops = [argv for argv in calls if argv[0] == "dropdb"]
    assert len(drops) == 1
    assert drops[0][1].startswith("helpdesk_restore_")
    assert drops[0][1] not in {"helpdesk", "postgres"}
