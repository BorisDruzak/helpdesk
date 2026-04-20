from pathlib import Path

import pytest

from scripts import build_webapp_bundle


def test_run_resolves_pnpm_cmd_on_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return str(tmp_path / "pnpm.cmd") if name == "pnpm.cmd" else None

    def fake_subprocess_run(command: list[str], *, cwd: Path, check: bool) -> None:
        seen.append(command)

    monkeypatch.setattr(build_webapp_bundle.os, "name", "nt")
    monkeypatch.setattr(build_webapp_bundle.shutil, "which", fake_which)
    monkeypatch.setattr(build_webapp_bundle.subprocess, "run", fake_subprocess_run)

    build_webapp_bundle.run(["pnpm", "--dir", "webapp", "run", "build"], cwd=tmp_path)

    assert seen == [[str(tmp_path / "pnpm.cmd"), "--dir", "webapp", "run", "build"]]


def test_resolve_command_fails_with_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_webapp_bundle.shutil, "which", lambda name: None)

    with pytest.raises(SystemExit, match="Required command not found on PATH: pnpm"):
        build_webapp_bundle.resolve_command("pnpm")
