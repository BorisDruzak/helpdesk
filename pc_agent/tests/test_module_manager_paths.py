import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.core.module_manager import ModuleManager


def _make_version(store_root: Path, module_name: str, version: str) -> Path:
    """Вспомогательная функция для создания версии модуля на диске."""
    ver_path = store_root / module_name / version
    ver_path.mkdir(parents=True, exist_ok=True)
    (ver_path / "manifest.json").write_text(
        json.dumps({"module_name": module_name, "module_version": version}),
        encoding="utf-8",
    )
    return ver_path


class ModuleManagerPathTests(unittest.TestCase):
    def test_migrates_legacy_nested_modules_store(self):
        with tempfile.TemporaryDirectory() as td:
            data_root = Path(td)
            legacy_ver = data_root / "modules_store" / "modules_store" / "demo" / "1.0.0"
            legacy_ver.mkdir(parents=True, exist_ok=True)
            (legacy_ver / "manifest.json").write_text(
                json.dumps({"module_name": "demo", "module_version": "1.0.0"}),
                encoding="utf-8",
            )

            manager = ModuleManager(data_dir=str(data_root), temp_dir=str(data_root / "temp"))

            migrated_ver = manager.store_root / "demo" / "1.0.0"
            self.assertTrue((migrated_ver / "manifest.json").exists())
            self.assertFalse(legacy_ver.exists())

    def test_list_installed_skips_module_without_valid_versions(self):
        with tempfile.TemporaryDirectory() as td:
            data_root = Path(td)
            module_dir = data_root / "modules_store" / "ghost"
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "current.json").write_text(
                json.dumps({"version": "1.0.0"}), encoding="utf-8"
            )

            manager = ModuleManager(data_dir=str(data_root), temp_dir=str(data_root / "temp"))
            installed = manager.list_installed()

            self.assertEqual(installed, {"modules": []})
            self.assertFalse(module_dir.exists())

    def test_accepts_modules_store_as_data_dir_for_backward_compat(self):
        with tempfile.TemporaryDirectory() as td:
            data_root = Path(td)
            modules_store = data_root / "modules_store"
            legacy_ver = modules_store / "modules_store" / "demo" / "1.0.0"
            legacy_ver.mkdir(parents=True, exist_ok=True)
            (legacy_ver / "manifest.json").write_text(
                json.dumps({"module_name": "demo", "module_version": "1.0.0"}),
                encoding="utf-8",
            )

            manager = ModuleManager(data_dir=str(modules_store), temp_dir=str(data_root / "temp"))
            installed = manager.list_installed()

            self.assertEqual(manager.store_root, modules_store)
            self.assertEqual(
                installed,
                {"modules": [{"name": "demo", "active": None, "versions": ["1.0.0"]}]},
            )


class ModuleManagerGCTests(unittest.TestCase):
    """Тесты для метода garbage_collect (GC current+prev)."""

    def _make_manager(self, td: str) -> ModuleManager:
        data_root = Path(td)
        return ModuleManager(data_dir=str(data_root), temp_dir=str(data_root / "temp"))

    def test_gc_removes_old_versions_keeps_current_prev(self):
        """GC должен оставить только 2 последних версии, если keep=2."""
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]:
                _make_version(manager.store_root, "mymod", v)
            # Активируем 1.3.0
            manager.activate("mymod", "1.3.0")

            removed = manager.garbage_collect("mymod", keep=2)
            self.assertEqual(sorted(removed), ["1.0.0", "1.1.0"])
            # 1.2.0 и 1.3.0 должны остаться
            self.assertTrue((manager.store_root / "mymod" / "1.2.0").exists())
            self.assertTrue((manager.store_root / "mymod" / "1.3.0").exists())

    def test_gc_always_keeps_active_version(self):
        """Активная версия не удаляется даже если она старая."""
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.0.0", "1.1.0", "1.2.0"]:
                _make_version(manager.store_root, "mymod", v)
            manager.activate("mymod", "1.0.0")  # Активируем старую

            removed = manager.garbage_collect("mymod", keep=2)
            # 1.0.0 (active) + 1.2.0 (last) должны остаться
            self.assertNotIn("1.0.0", removed)
            self.assertNotIn("1.2.0", removed)

    def test_gc_no_op_if_few_versions(self):
        """GC не удаляет ничего, если версий <= keep."""
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.0.0", "1.1.0"]:
                _make_version(manager.store_root, "mymod", v)
            manager.activate("mymod", "1.1.0")

            removed = manager.garbage_collect("mymod", keep=2)
            self.assertEqual(removed, [])

    def test_gc_nonexistent_module_returns_empty(self):
        """GC на несуществующем модуле возвращает пустой список."""
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            removed = manager.garbage_collect("nonexistent", keep=2)
            self.assertEqual(removed, [])

    def test_list_installed_sorts_versions_as_semver(self):
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.10.0", "1.2.0", "1.9.0"]:
                _make_version(manager.store_root, "mymod", v)

            installed = manager.list_installed()
            self.assertEqual(
                installed["modules"][0]["versions"],
                ["1.2.0", "1.9.0", "1.10.0"],
            )

    def test_rollback_uses_semver_order(self):
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.10.0", "1.2.0", "1.9.0"]:
                _make_version(manager.store_root, "mymod", v)
            manager.activate("mymod", "1.10.0")

            previous = manager.rollback("mymod")

            self.assertIsNotNone(previous)
            self.assertEqual(previous.name, "1.9.0")

    def test_gc_uses_semver_order(self):
        with tempfile.TemporaryDirectory() as td:
            manager = self._make_manager(td)
            for v in ["1.10.0", "1.2.0", "1.9.0"]:
                _make_version(manager.store_root, "mymod", v)
            manager.activate("mymod", "1.10.0")

            removed = manager.garbage_collect("mymod", keep=2)

            self.assertEqual(removed, ["1.2.0"])


if __name__ == "__main__":
    unittest.main()
