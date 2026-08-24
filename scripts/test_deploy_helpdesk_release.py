from scripts.deploy_helpdesk_release import (
    WORKSPACE,
    _ssh_base,
    release_path,
    remote_install_command,
)
from scripts.helpdesk_remote_profile import RemoteProfile


def test_release_path_is_scoped_to_helpdesk_releases() -> None:
    profile = RemoteProfile.from_environment({})

    assert release_path(profile, "abc123") == "/opt/helpdesk/releases/helpdesk-abc123"


def test_script_bootstraps_workspace_for_direct_python_execution() -> None:
    source = (WORKSPACE / "scripts" / "deploy_helpdesk_release.py").read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(WORKSPACE))" in source


def test_remote_install_command_uses_immutable_release_and_system_services() -> None:
    profile = RemoteProfile.from_environment({})

    command = remote_install_command(profile, "abc123", "/tmp/helpdesk-abc123.tar")

    assert "test -f /etc/helpdesk/helpdesk.env" in command
    assert "test ! -e /opt/helpdesk/releases/helpdesk-abc123" in command
    assert "sudo ln -sfn /opt/helpdesk/releases/helpdesk-abc123 /opt/helpdesk/current" in command
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
    assert "sudo systemctl start helpdesk-staging-migrate.service" in command
    assert "sudo systemctl restart helpdesk-staging.service" in command
    assert "helpdesk-control.service" not in command
    assert "sudo python3 -m venv /opt/helpdesk-staging/releases/helpdesk-abc123/venv" in command
    assert "helpdesk-abc123/venv/bin/pip install" in command


def test_ssh_base_adds_tty_only_for_explicit_interactive_profile() -> None:
    profile = RemoteProfile.from_environment({"HELPDESK_SSH_TTY": "true"})

    assert _ssh_base(profile)[:2] == ["ssh", "-tt"]
