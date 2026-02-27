import os
import sys


def _prepend_env_path(var_name: str, path_value: str) -> None:
    current = os.environ.get(var_name, "")
    if current:
        os.environ[var_name] = path_value + os.pathsep + current
    else:
        os.environ[var_name] = path_value


if sys.platform.startswith("win"):
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    qt_root = os.path.join(base_dir, "PyQt6", "Qt6")
    qt_bin = os.path.join(qt_root, "bin")
    qt_plugins = os.path.join(qt_root, "plugins")
    qt_platforms = os.path.join(qt_plugins, "platforms")
    qt_translations = os.path.join(qt_root, "translations")

    if os.path.isdir(qt_bin):
        _prepend_env_path("PATH", qt_bin)
        try:
            os.add_dll_directory(qt_bin)
        except Exception:
            pass

    if os.path.isdir(qt_plugins):
        os.environ["QT_PLUGIN_PATH"] = qt_plugins

    if os.path.isdir(qt_platforms):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = qt_platforms

    if os.path.isdir(qt_translations):
        os.environ["QT_TRANSLATION_PATH"] = qt_translations
