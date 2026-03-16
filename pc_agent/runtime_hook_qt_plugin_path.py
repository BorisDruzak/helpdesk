# Runtime hook для PyInstaller: задаёт QT_PLUGIN_PATH, если в бандле есть qt_plugins
# (для будущего варианта с плагинами в бандле). Сейчас при отсутствии GUI задайте
# QT_PLUGIN_PATH вручную (см. pc_agent/docs/BUILD_AND_RUN_LINUX.md).
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _plugin_path = os.path.join(sys._MEIPASS, "qt_plugins")
    if os.path.isdir(_plugin_path):
        os.environ["QT_PLUGIN_PATH"] = _plugin_path
