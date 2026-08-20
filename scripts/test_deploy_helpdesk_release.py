from scripts.deploy_helpdesk_release import WORKSPACE, release_path, remote_install_command
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
    assert "sudo systemctl reset-failed helpdesk-migrate.service || true" in command
    assert "sudo systemctl start helpdesk-migrate.service" in command
    assert "sudo systemctl restart helpdesk-server.service helpdesk-control.service" in command
