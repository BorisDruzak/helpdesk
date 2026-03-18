import argparse
from pathlib import Path

import pytest

import scripts.deploy_workspace_to_remote as deploy


def test_build_local_dirty_message_explains_git_only_deploy() -> None:
    message = deploy.build_local_dirty_message([" M server/websocket/agent_handler.py"])

    assert "deploys only committed Git state" in message
    assert "would NOT be copied" in message
    assert "--allow-local-dirty" in message


def test_build_local_dirty_message_truncates_long_list() -> None:
    entries = [f" M file_{index}.py" for index in range(25)]

    message = deploy.build_local_dirty_message(entries)

    assert "file_19.py" in message
    assert "file_20.py" not in message
    assert "... and 5 more" in message


def test_main_refuses_dirty_workspace_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deploy,
        "parse_args",
        lambda: argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            remote_name="linux",
            remote_host="altserver@192.168.100.17",
            remote_worktree="/var/chat_bot/pc_client",
            branch="main",
            allow_local_dirty=False,
        ),
    )
    monkeypatch.setattr(deploy, "git_env", lambda: {})
    monkeypatch.setattr(
        deploy,
        "get_local_dirty_entries",
        lambda workspace, env, *, git_binary: [" M server/websocket/device_outbox_sender.py"],
    )

    with pytest.raises(SystemExit) as exc_info:
        deploy.main()

    assert "would NOT be copied" in str(exc_info.value)


def test_main_allows_dirty_workspace_with_override(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        deploy,
        "parse_args",
        lambda: argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            remote_name="linux",
            remote_host="altserver@192.168.100.17",
            remote_worktree="/var/chat_bot/pc_client",
            branch="main",
            allow_local_dirty=True,
        ),
    )
    monkeypatch.setattr(deploy, "git_env", lambda: {})
    monkeypatch.setattr(
        deploy,
        "get_local_dirty_entries",
        lambda workspace, env, *, git_binary: [" M server/websocket/device_outbox_sender.py"],
    )

    calls: list[list[str]] = []

    def fake_run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
        calls.append(command)
        if len(command) >= 2 and command[1] == "push":
            return "push ok"
        if command and command[0].endswith("ssh.exe"):
            return "remote ok"
        return ""

    monkeypatch.setattr(deploy, "run", fake_run)

    deploy.main()

    out = capsys.readouterr().out
    assert "WARNING: local workspace is dirty" in out
    assert any(len(command) >= 2 and command[1] == "push" for command in calls)
