#!/usr/bin/env python3
"""
Build Windows artifacts for pc_agent remote update flow:
- launcher.exe
- agent onedir build (pc_agent.exe + dependencies)
- install_root layout
- update ZIP artifact for server upload
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PC_AGENT_DIR = Path(__file__).resolve().parent


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"[build_windows_release] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _read_agent_version() -> str:
    version_py = (PC_AGENT_DIR / "version.py").read_text(encoding="utf-8")
    match = re.search(r'AGENT_VERSION\s*=\s*"([^"]+)"', version_py)
    if not match:
        raise RuntimeError("Could not parse AGENT_VERSION from pc_agent/version.py")
    return match.group(1)


def _zip_dir(src_dir: Path, dst_zip: Path) -> None:
    dst_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in src_dir.rglob("*"):
            if item.is_file():
                zf.write(item, item.relative_to(src_dir).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows release for pc_agent")
    parser.add_argument("--version", type=str, default=None, help="Override AGENT_VERSION")
    parser.add_argument("--channel", type=str, default="stable", help="Release channel name")
    parser.add_argument("--target", type=str, default="windows_amd64", help="Server target value")
    parser.add_argument("--clean", action="store_true", help="Clean pyinstaller build/dist first")
    args = parser.parse_args()

    version = args.version or _read_agent_version()
    channel = args.channel.strip() or "stable"
    target = args.target.strip() or "windows_amd64"

    build_dir = PC_AGENT_DIR / "build"
    dist_dir = PC_AGENT_DIR / "dist"
    if args.clean:
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(dist_dir, ignore_errors=True)

    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", "pyinstaller_agent_win.spec"], cwd=PC_AGENT_DIR)
    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", "pyinstaller_launcher_win.spec"], cwd=PC_AGENT_DIR)

    built_agent_dir = dist_dir / "pc_agent"
    built_launcher = dist_dir / "launcher.exe"
    if not (built_agent_dir / "pc_agent.exe").exists():
        raise RuntimeError(f"Agent build missing: {built_agent_dir / 'pc_agent.exe'}")
    if not built_launcher.exists():
        raise RuntimeError(f"Launcher build missing: {built_launcher}")

    release_root = dist_dir / "release" / target / channel / version
    install_root = release_root / "install"
    version_dir = install_root / "versions" / version
    artifact_zip = release_root / f"pc_agent-{target}-{version}.zip"

    shutil.rmtree(release_root, ignore_errors=True)
    version_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(built_launcher, install_root / "launcher.exe")

    for item in built_agent_dir.iterdir():
        dst = version_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)

    current_json = {"version": version, "previous": version}
    (install_root / "current.json").write_text(
        json.dumps(current_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _zip_dir(version_dir, artifact_zip)

    print(f"[build_windows_release] Version: {version}")
    print(f"[build_windows_release] Install root: {install_root}")
    print(f"[build_windows_release] Agent version dir: {version_dir}")
    print(f"[build_windows_release] Update artifact: {artifact_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
