# PyInstaller spec for release launcher (Windows, no console).
# Build: pyinstaller pyinstaller_launcher_win_release.spec
# Output: dist/launcher.exe
import sys
from pathlib import Path

pc_agent_root = Path(SPECPATH)
project_root = pc_agent_root.parent
sys.path.insert(0, str(project_root))

a = Analysis(
    [str(pc_agent_root / "launcher_portable_main.py")],
    pathex=[str(project_root)],
    hiddenimports=[
        "pc_agent.auth.token_source",
        "pc_agent.config.config_loader",
        "pc_agent.core.database",
        "pc_agent.core.identity",
        "pc_agent.core.machine_identity",
        "pc_agent.core.runtime_paths",
        "pc_agent.core.single_instance",
        "pc_agent.launcher.installer",
        "pc_agent.version",
    ],
    datas=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
