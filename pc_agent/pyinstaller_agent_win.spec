# PyInstaller spec for agent (Windows). Build: pyinstaller pyinstaller_agent_win.spec
# Output: dist/pc_agent/ (onedir, contains pc_agent.exe)
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

pc_agent_root = Path(SPECPATH)
project_root = pc_agent_root.parent
sys.path.insert(0, str(project_root))

remote_assist_hiddenimports = []
for package_name in ("aiortc", "aioice", "av", "pylibsrtp"):
    try:
        remote_assist_hiddenimports.extend(collect_submodules(package_name))
    except Exception:
        remote_assist_hiddenimports.append(package_name)

a = Analysis(
    [str(pc_agent_root / "ws_agent.py")],
    pathex=[str(project_root), str(pc_agent_root)],
    hiddenimports=[
        "pc_agent.version",
        "pc_agent.core.runtime_paths",
        "pc_agent.config.config_loader",
        "qasync",
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "modules.impl.system",
        "modules.impl.screen",
        "modules.impl.input",
        "modules.impl.diag_logs",
    ] + remote_assist_hiddenimports,
    datas=[
        (str(pc_agent_root / "config" / "settings.default.yaml"), "pc_agent/config"),
    ],
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
    [],
    exclude_binaries=True,
    name="pc_agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pc_agent",
)
