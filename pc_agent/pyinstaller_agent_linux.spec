# PyInstaller spec for agent (Linux). Build: pyinstaller pyinstaller_agent_linux.spec
# Output: dist/pc_agent/ (onedir, contains pc_agent)
import sys
from pathlib import Path

pc_agent_root = Path(SPECPATH)
project_root = pc_agent_root.parent
sys.path.insert(0, str(project_root))

# Путь к плагинам Qt задаётся в runtime_hook_qt_plugin_path.py.
# Если GUI не отображается при запуске из dist, задайте QT_PLUGIN_PATH вручную (см. BUILD_AND_RUN_LINUX.md).
_datas = [
    (str(pc_agent_root / "config" / "settings.default.yaml"), "pc_agent/config"),
]

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
    ],
    datas=_datas,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(pc_agent_root / "runtime_hook_qt_plugin_path.py")],
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
