import subprocess
import tarfile
import textwrap

import scripts.deploy_helpdesk_release as deploy_release
from scripts.deploy_helpdesk_release import (
    WORKSPACE,
    _ssh_base,
    release_path,
    remote_install_command,
)
from scripts.helpdesk_remote_profile import RemoteProfile
import pytest


def test_release_path_is_scoped_to_helpdesk_releases() -> None:
    profile = RemoteProfile.from_environment({})

    assert release_path(profile, "abc123") == "/opt/helpdesk/releases/helpdesk-abc123"


def test_release_path_accepts_a_distinct_immutable_release_id() -> None:
    profile = RemoteProfile.from_environment(
        {"HELPDESK_REMOTE_ROOT": "/opt/helpdesk-staging/current"}
    )

    assert release_path(profile, "abc123", release_id="abc123-venvfix") == (
        "/opt/helpdesk-staging/releases/helpdesk-abc123-venvfix"
    )


def test_release_path_rejects_unsafe_release_id() -> None:
    profile = RemoteProfile.from_environment({})

    with pytest.raises(ValueError, match="release id"):
        release_path(profile, "abc123", release_id="../mutable")


def test_append_webapp_bundle_to_release_archive_places_dist_under_release_prefix(tmp_path) -> None:
    release_archive = tmp_path / "helpdesk.tar"
    bundle_dir = tmp_path / "webapp-dist"
    assets_dir = bundle_dir / "assets"
    assets_dir.mkdir(parents=True)
    (bundle_dir / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (assets_dir / "app.js").write_text("export {}", encoding="utf-8")

    with tarfile.open(release_archive, "w"):
        pass

    deploy_release.append_webapp_bundle_to_release_archive(
        release_archive,
        bundle_dir,
        "helpdesk-abc123",
    )

    with tarfile.open(release_archive) as archive:
        assert "helpdesk-abc123/webapp/dist/index.html" in archive.getnames()
        assert "helpdesk-abc123/webapp/dist/assets/app.js" in archive.getnames()


def test_webapp_bundle_is_built_from_the_release_commit_not_dirty_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    (workspace / "webapp").mkdir()
    (workspace / "webapp" / "source.txt").write_text("committed", encoding="utf-8")
    (workspace / "scripts" / "build_webapp_bundle.py").write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument("--workspace", type=Path, required=True)
            parser.add_argument("--output-dir", type=Path, required=True)
            parser.add_argument("--archive", type=Path, required=True)
            args = parser.parse_args()
            args.output_dir.mkdir(parents=True)
            (args.output_dir / "assets").mkdir()
            (args.output_dir / "index.html").write_text(
                (args.workspace / "webapp" / "source.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (args.output_dir / "assets" / "app.js").write_text("export {}", encoding="utf-8")
            args.archive.write_bytes(b"bundle")
            """
        ).strip(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-m", "test release source"], cwd=workspace, check=True, capture_output=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (workspace / "webapp" / "source.txt").write_text("dirty", encoding="utf-8")
    release_archive = tmp_path / "helpdesk.tar"
    with tarfile.open(release_archive, "w"):
        pass

    deploy_release.build_webapp_bundle_into_release_archive(
        workspace,
        commit,
        release_archive,
        "helpdesk-test",
    )

    with tarfile.open(release_archive) as archive:
        member = archive.getmember("helpdesk-test/webapp/dist/index.html")
        assert archive.extractfile(member).read().decode("utf-8") == "committed"


def test_script_bootstraps_workspace_for_direct_python_execution() -> None:
    source = (WORKSPACE / "scripts" / "deploy_helpdesk_release.py").read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(WORKSPACE))" in source


def test_remote_install_command_uses_immutable_release_and_system_services() -> None:
    profile = RemoteProfile.from_environment({})

    command = remote_install_command(profile, "abc123", "/tmp/helpdesk-abc123.tar")

    assert "test -f /etc/helpdesk/helpdesk.env" in command
    assert "test ! -e /opt/helpdesk/releases/helpdesk-abc123" in command
    assert "sudo readlink -f /opt/helpdesk/current" in command
    assert "/etc/helpdesk/previous-release" in command
    assert "sudo ln -sfn /opt/helpdesk/releases/helpdesk-abc123 /opt/helpdesk/current" in command
    assert command.index("/etc/helpdesk/previous-release") < command.index(
        "sudo ln -sfn /opt/helpdesk/releases/helpdesk-abc123 /opt/helpdesk/current"
    )
    assert "reset-failed helpdesk-migrate.service" not in command
    assert "sudo systemctl start helpdesk-migrate.service" in command
    assert "sudo systemctl restart helpdesk-server.service helpdesk-control.service" in command


def test_remote_install_command_supports_isolated_staging_service_profile() -> None:
    profile = RemoteProfile.from_environment(
        {
            "HELPDESK_REMOTE_ROOT": "/opt/helpdesk-staging/current",
            "HELPDESK_ENV_FILE": "/etc/helpdesk-staging/helpdesk.env",
            "HELPDESK_MIGRATE_SERVICE": "helpdesk-staging-migrate.service",
            "HELPDESK_SERVER_SERVICE": "helpdesk-staging.service",
            "HELPDESK_CONTROL_SERVICE": "",
            "HELPDESK_RELEASE_VENV_PATH": "venv",
        }
    )

    command = remote_install_command(profile, "abc123", "/tmp/helpdesk-abc123.tar")

    assert "test -f /etc/helpdesk-staging/helpdesk.env" in command
    assert "/etc/helpdesk-staging/previous-release" in command
    assert "/etc/helpdesk/previous-release" not in command
    assert "sudo systemctl start helpdesk-staging-migrate.service" in command
    assert "sudo systemctl restart helpdesk-staging.service" in command
    assert "helpdesk-control.service" not in command
    assert "sudo python3 -m venv /opt/helpdesk-staging/releases/helpdesk-abc123/venv" in command
    assert "helpdesk-abc123/venv/bin/pip install" in command


def test_ssh_base_adds_tty_only_for_explicit_interactive_profile() -> None:
    profile = RemoteProfile.from_environment({"HELPDESK_SSH_TTY": "true"})

    assert _ssh_base(profile)[:2] == ["ssh", "-tt"]
