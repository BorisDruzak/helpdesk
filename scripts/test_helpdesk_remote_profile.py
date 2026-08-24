from __future__ import annotations

from pathlib import Path

import scripts.helpdesk_remote_profile as profile


def test_default_profile_targets_independent_helpdesk_host() -> None:
    defaults = profile.RemoteProfile.from_environment({})

    assert defaults.remote == "osn_admin@192.168.100.19"
    assert defaults.root == "/opt/helpdesk/current"
    assert defaults.server_python == "/opt/helpdesk/current/server/venv/bin/python"
    assert defaults.ssh_key == Path(r"C:\Users\admin-2\.ssh\id_ed25519_osn_192.168.100.19")


def test_profile_environment_overrides_are_scoped_to_helpdesk() -> None:
    profile_value = profile.RemoteProfile.from_environment(
        {
            "HELPDESK_REMOTE": "deploy@example.test",
            "HELPDESK_REMOTE_ROOT": "/srv/helpdesk/current",
            "HELPDESK_SSH_KEY": r"C:\keys\helpdesk",
        }
    )

    assert profile_value.remote == "deploy@example.test"
    assert profile_value.root == "/srv/helpdesk/current"
    assert profile_value.server_python == "/srv/helpdesk/current/server/venv/bin/python"
    assert profile_value.ssh_key == Path(r"C:\keys\helpdesk")


def test_profile_allows_an_explicit_interactive_ssh_tty_only() -> None:
    interactive = profile.RemoteProfile.from_environment({"HELPDESK_SSH_TTY": "1"})

    assert interactive.ssh_tty is True
    assert profile.RemoteProfile.from_environment({}).ssh_tty is False
