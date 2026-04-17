import argparse

import pytest

import scripts.run_remote_migrations as run_remote_migrations


def test_parse_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_remote_migrations.sys, "argv", ["run_remote_migrations.py"])

    args = run_remote_migrations.parse_args()

    assert isinstance(args, argparse.Namespace)
    assert args.remote == run_remote_migrations.DEFAULT_REMOTE
    assert args.alembic_args == []


def test_main_passes_remote_and_default_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_remote_migrations,
        "parse_args",
        lambda: argparse.Namespace(remote="altserver@example", alembic_args=[]),
    )

    recorded = {}

    def fake_run(command: list[str]) -> object:
        recorded["command"] = command

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(run_remote_migrations.subprocess, "run", fake_run)
    monkeypatch.setattr(run_remote_migrations, "ssh_cmd", lambda: ["ssh", "-i", "key"])

    assert run_remote_migrations.main() == 0
    assert recorded["command"] == [
        "ssh",
        "-i",
        "key",
        "altserver@example",
        (
            "cd /var/chat_bot/pc_client/server && "
            "/var/chat_bot/pc_client/server/venv/bin/python scripts/run_migrations.py "
            "upgrade head"
        ),
    ]


def test_main_passes_custom_alembic_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_remote_migrations,
        "parse_args",
        lambda: argparse.Namespace(remote="altserver@example", alembic_args=["current"]),
    )

    recorded = {}

    def fake_run(command: list[str]) -> object:
        recorded["command"] = command

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(run_remote_migrations.subprocess, "run", fake_run)
    monkeypatch.setattr(run_remote_migrations, "ssh_cmd", lambda: ["ssh"])

    assert run_remote_migrations.main() == 0
    assert recorded["command"][-1].endswith("scripts/run_migrations.py current")
