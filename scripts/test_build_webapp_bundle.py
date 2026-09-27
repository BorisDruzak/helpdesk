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


def test_bundle_digest_changes_with_content_and_relative_name(tmp_path):
    (tmp_path / "index.html").write_text("one")
    first = build_webapp_bundle.bundle_digest(tmp_path)
    (tmp_path / "index.html").write_text("two")
    second = build_webapp_bundle.bundle_digest(tmp_path)
    (tmp_path / "index.html").rename(tmp_path / "other.html")
    third = build_webapp_bundle.bundle_digest(tmp_path)
    assert len({first, second, third}) == 3


def test_archive_content_digest_matches_files_and_rejects_links(tmp_path):
    import tarfile
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("hello")
    (dist / "assets/app.js").write_text("export {}")
    archive = tmp_path / "bundle.tar.gz"
    build_webapp_bundle.create_archive(dist, archive)
    assert build_webapp_bundle.archive_bundle_digest(archive) == build_webapp_bundle.bundle_digest(dist)
    with tarfile.open(archive, "w:gz") as handle:
        item = tarfile.TarInfo("dist/escape"); item.type = tarfile.SYMTYPE; item.linkname = "../../private"
        handle.addfile(item)
    with pytest.raises(ValueError):
        build_webapp_bundle.archive_bundle_digest(archive)
