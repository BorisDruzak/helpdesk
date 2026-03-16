# PyInstaller spec for launcher (Windows). Build: pyinstaller pyinstaller_launcher_win.spec
# Output: dist/launcher.exe
import sys
from pathlib import Path

# SPECPATH = directory containing this .spec file (pc_agent/)
pc_agent_root = Path(SPECPATH)
project_root = pc_agent_root.parent
sys.path.insert(0, str(project_root))

a = Analysis(
    [str(pc_agent_root / "launcher" / "launcher_main.py")],
    pathex=[str(project_root)],
    hiddenimports=["pc_agent.core.runtime_paths", "pc_agent.launcher.installer", "pc_agent.version"],
    datas=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
