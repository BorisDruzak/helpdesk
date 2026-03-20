"""
Module Manager Service
Управление модульными пакетами с версиями.
Перед установкой (переносом в store) выполняется smoke-проверка: загрузка, register, list_tools.
"""

import json
import hashlib
import zipfile
import shutil
import io
import sys
import re
from pathlib import Path
from uuid import uuid4
from typing import Optional


def _sha256_bytes(data: bytes) -> str:
    """Вычисляет SHA256 хеш для байтовых данных."""
    return hashlib.sha256(data).hexdigest()


def _safe_mkdir(path: Path) -> None:
    """Безопасно создаёт директорию, если она не существует."""
    path.mkdir(parents=True, exist_ok=True)


_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?P<suffix>[-+][0-9A-Za-z.-]+)?$"
)


def _version_sort_key(version: str):
    """
    Сортирует semver корректно, а legacy-версии — лексикографически после semver.
    """
    match = _SEMVER_RE.match(version or "")
    if not match:
        return (1, version)
    return (
        0,
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        match.group("suffix") or "",
    )


class ModuleManager:
    """
    Менеджер модульных пакетов с версионированием.
    
    Управляет установкой, активацией и получением информации о модулях.
    """
    
    def __init__(self, data_dir: str, temp_dir: str):
        """
        Инициализация ModuleManager.
        
        Args:
            data_dir: Директория для хранения данных (здесь будет modules_store)
            temp_dir: Временная директория для распаковки архивов
        """
        self.data_dir = Path(data_dir)
        self.temp_dir = Path(temp_dir)
        # Backward compatibility: caller may pass either data_root or modules_store path.
        if self.data_dir.name == "modules_store":
            self.data_root = self.data_dir.parent
            self.store_root = self.data_dir
        else:
            self.data_root = self.data_dir
            self.store_root = self.data_dir / "modules_store"
        
        # Создаём необходимые директории
        _safe_mkdir(self.store_root)
        _safe_mkdir(self.temp_dir)
        self._migrate_legacy_nested_store()

    def _migrate_legacy_nested_store(self) -> None:
        """
        Миграция legacy-структуры:
        <data_root>/modules_store/modules_store/<module>/<version> -> <data_root>/modules_store/<module>/<version>.
        """
        legacy_root = self.store_root / "modules_store"
        if not legacy_root.is_dir():
            return

        for item in legacy_root.iterdir():
            # Защита от рекурсивного мусора.
            if item.name == "modules_store":
                continue
            target = self.store_root / item.name
            if target.exists():
                continue
            shutil.move(str(item), str(target))

        # Удаляем legacy-каталог, если он пуст.
        try:
            legacy_root.rmdir()
        except OSError:
            pass

    def _run_smoke(self, module_root: Path, module_name: str, entrypoint: str) -> None:
        """
        Smoke-проверка модуля перед установкой: загрузка, register, list_tools.
        При ошибке выбрасывает исключение — установка не выполняется.

        КРИТИЧНО: ModuleRegistry — singleton; создаём изолированный временный экземпляр,
        минуя __new__-синглтон, чтобы не загрязнять глобальный registry агента.
        """
        from pc_agent.core.loader import DynamicModuleLoader
        from pc_agent.core.registry import ModuleRegistry
        module_path_str = str(module_root.resolve())
        path_inserted = module_path_str not in sys.path
        if path_inserted:
            sys.path.insert(0, module_path_str)
        try:
            loader = DynamicModuleLoader(data_root=self.data_root)
            # Изолированный экземпляр, не связанный с глобальным singleton:
            registry = object.__new__(ModuleRegistry)
            registry._manifest = {}
            registry._instances = {}
            registry._initialized = True
            instance = loader.load_module_from_path(module_name, module_root, entrypoint=entrypoint)
            registry.register(instance)
            registry.get_tools_flat()
        finally:
            if path_inserted and sys.path and sys.path[0] == module_path_str:
                sys.path.pop(0)
    
    def install_zip_bytes(
        self, 
        zip_bytes: bytes, 
        expected_sha256: Optional[str] = None,
        replace_if_different_sha: bool = False
    ) -> dict:
        """
        Устанавливает модуль из ZIP-архива в байтовом формате.
        
        Args:
            zip_bytes: Байты ZIP-архива с модулем
            expected_sha256: Ожидаемый SHA256 хеш архива (опционально)
            replace_if_different_sha: Если True, при конфликте SHA (та же name+version, другой хеш)
                удалить существующий каталог и установить заново; иначе — ValueError INSTALL_CONFLICT_SHA.
        
        Returns:
            dict с информацией об установленном модуле:
            {
                "module_name": str,
                "module_version": str,
                "path": str,
                "manifest": dict
            }
        
        Raises:
            ValueError: Если хеш не совпадает, manifest.json отсутствует или некорректен,
                       или версия уже установлена
            IOError: Если не удалось распаковать или переместить файлы
        """
        # Вычисляем SHA архива (для идемпотентности по SHA, Этап 5)
        actual_sha256 = _sha256_bytes(zip_bytes)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            raise ValueError(
                f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )
        
        # Создаём временную директорию для распаковки
        tmp_dir = self.temp_dir / f"mod_install_{uuid4()}"
        try:
            _safe_mkdir(tmp_dir)
            
            # Распаковываем ZIP во временную директорию
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # Читаем manifest.json (обязателен)
            manifest_path = tmp_dir / "manifest.json"
            if not manifest_path.exists():
                raise ValueError("manifest.json not found in archive")
            
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in manifest.json: {e}")
            
            # Извлекаем module_name и module_version (обязательны)
            module_name = manifest.get("module_name")
            module_version = manifest.get("module_version")
            
            if not module_name:
                raise ValueError("module_name is required in manifest.json")
            if not module_version:
                raise ValueError("module_version is required in manifest.json")
            
            # Проверка платформы: если в manifest указаны platforms и не "any", текущая ОС должна входить
            platforms = manifest.get("platforms")
            if platforms is not None and isinstance(platforms, list) and len(platforms) > 0:
                if "any" not in [str(p).lower() for p in platforms]:
                    current = (sys.platform or "").lower()
                    if current.startswith("linux"):
                        current = "linux"
                    elif current.startswith("darwin"):
                        current = "darwin"
                    elif "win" in current:
                        current = "win32"
                    allowed = [str(p).lower() for p in platforms]
                    if current not in allowed:
                        raise ValueError(
                            f"Module not supported on this OS: current={current!r}, supported={allowed}"
                        )
            
            entrypoint = (manifest.get("entrypoint") or "module:register").strip()
            # Smoke-проверка перед установкой: загрузка, register, list_tools
            self._run_smoke(tmp_dir, module_name, entrypoint)
            
            # Целевой путь для установки
            target_path = self.store_root / module_name / module_version
            sha_file = target_path / ".sha256"
            
            # Идемпотентность по SHA (Этап 5): same name+version+same sha -> success/no-op
            if target_path.exists():
                if sha_file.exists():
                    try:
                        current_sha = sha_file.read_text(encoding="utf-8").strip()
                    except Exception:
                        current_sha = None
                    if current_sha == actual_sha256:
                        # Тот же пакет уже установлен — возвращаем успех без переустановки
                        with open(target_path / "manifest.json", "r", encoding="utf-8") as f:
                            existing_manifest = json.load(f)
                        return {
                            "module_name": module_name,
                            "module_version": module_version,
                            "path": str(target_path),
                            "manifest": existing_manifest,
                        }
                    else:
                        # Конфликт SHA: та же версия, другой хеш
                        if replace_if_different_sha:
                            # По явному флагу — удаляем старый каталог и продолжаем установку
                            shutil.rmtree(target_path)
                            # target_path больше не существует — ниже создаём заново
                        else:
                            raise ValueError(
                                f"INSTALL_CONFLICT_SHA: Module {module_name} version {module_version} "
                                f"already installed with different SHA (installed={current_sha}, requested={actual_sha256})"
                            )
                else:
                    # Старая установка без .sha256 — как раньше
                    raise ValueError(
                        f"Module {module_name} version {module_version} already installed at {target_path}"
                    )
            
            # Создаём родительскую директорию для модуля
            _safe_mkdir(target_path.parent)
            
            # Перемещаем tmp_dir в целевой путь (атомарно насколько возможно)
            # Используем rename для атомарности, если возможно
            try:
                tmp_dir.rename(target_path)
            except OSError:
                # Если rename не работает (например, разные файловые системы),
                # используем копирование и удаление
                shutil.copytree(tmp_dir, target_path)
                shutil.rmtree(tmp_dir)
            
            # Сохраняем SHA для идемпотентности (Этап 5)
            (target_path / ".sha256").write_text(actual_sha256, encoding="utf-8")
            
            return {
                "module_name": module_name,
                "module_version": module_version,
                "path": str(target_path),
                "manifest": manifest
            }
            
        except Exception as e:
            # Очищаем временную директорию в случае ошибки
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
    
    def activate(self, module_name: str, module_version: str) -> Path:
        """
        Активирует указанную версию модуля.
        
        Args:
            module_name: Имя модуля
            module_version: Версия модуля для активации
        
        Returns:
            Path к активной версии модуля
        
        Raises:
            ValueError: Если модуль или версия не найдены
        """
        # Проверяем, что версия установлена
        version_path = self.store_root / module_name / module_version
        if not version_path.exists():
            raise ValueError(
                f"Module {module_name} version {module_version} not found at {version_path}"
            )
        
        # Создаём директорию модуля, если её нет
        module_dir = self.store_root / module_name
        _safe_mkdir(module_dir)
        
        # Записываем current.json
        current_json_path = module_dir / "current.json"
        current_data = {"version": module_version}
        
        with open(current_json_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        
        return version_path
    
    def deactivate(self, module_name: str) -> None:
        """
        Деактивирует модуль, удаляя current.json.
        
        Args:
            module_name: Имя модуля для деактивации
        """
        current_json_path = self.store_root / module_name / "current.json"
        if current_json_path.exists():
            current_json_path.unlink()
    
    def rollback(self, module_name: str) -> Optional[Path]:
        """
        Откатывает модуль на предыдущую версию.
        
        Args:
            module_name: Имя модуля для отката
        
        Returns:
            Path к предыдущей версии модуля или None, если откат невозможен
        """
        info = self.list_installed()
        # Находим модуль по имени
        module_info = None
        for module in info.get("modules", []):
            if module["name"] == module_name:
                module_info = module
                break
        
        if not module_info:
            return None
        
        active = module_info.get("active")
        versions = module_info.get("versions", [])
        
        # Если active None -> вернуть None
        if active is None:
            return None
        
        # Находим индекс active в versions
        try:
            idx = versions.index(active)
        except ValueError:
            # active не найден в versions
            return None
        
        # Если idx > 0 -> previous = versions[idx-1]
        if idx > 0:
            previous = versions[idx - 1]
            # Вызываем self.activate(module_name, previous) и возвращаем путь
            return self.activate(module_name, previous)
        
        # Если предыдущей нет -> вернуть None
        return None
    
    def get_active_path(self, module_name: str) -> Optional[Path]:
        """
        Получает путь к активной версии модуля.
        
        Args:
            module_name: Имя модуля
        
        Returns:
            Path к активной версии или None, если активная версия не установлена
        """
        current_json_path = self.store_root / module_name / "current.json"
        
        if not current_json_path.exists():
            return None
        
        try:
            with open(current_json_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            
            version = current_data.get("version")
            if not version:
                return None
            
            version_path = self.store_root / module_name / version
            if version_path.exists():
                return version_path
            else:
                # Версия указана, но директория не существует
                return None
                
        except (json.JSONDecodeError, IOError):
            return None
    
    def list_installed(self) -> dict:
        """
        Returns all installed package modules with available versions and active marker.

        Output format:
        {
            "modules": [
                {
                    "name": str,
                    "active": str | None,
                    "versions": [str, ...]
                },
                ...
            ]
        }
        """
        modules_list = []

        if not self.store_root.exists():
            return {"modules": []}

        # Walk all module directories in store_root.
        for module_dir in self.store_root.iterdir():
            if not module_dir.is_dir():
                continue
            # Ignore legacy nested store directory if it still exists.
            if module_dir.name == "modules_store":
                continue

            module_name = module_dir.name

            # Collect all valid versions (must contain manifest.json).
            versions = []
            for item in module_dir.iterdir():
                if item.is_dir() and (item / "manifest.json").exists():
                    versions.append(item.name)

            versions.sort(key=_version_sort_key)

            # Do not report module as installed if no valid versions exist on disk.
            if not versions:
                self._remove_module_dir_if_empty(module_name)
                continue

            current_json_path = module_dir / "current.json"
            active_version = None
            if current_json_path.exists():
                try:
                    with open(current_json_path, 'r', encoding='utf-8') as f:
                        current_data = json.load(f)
                        active_version = current_data.get("version")
                except (json.JSONDecodeError, IOError):
                    pass

            # If current.json points to missing version, clear stale active marker.
            if active_version and active_version not in versions:
                active_version = None
                try:
                    current_json_path.unlink()
                except OSError:
                    pass

            modules_list.append({
                "name": module_name,
                "active": active_version,
                "versions": versions
            })

        modules_list.sort(key=lambda x: x["name"])

        return {"modules": modules_list}
    
    def remove_version(self, module_name: str, version: str) -> bool:
        """
        Удаляет конкретную версию модуля (если не active).
        
        Returns:
            True if removed, False if not found or active
        """
        module_dir = self.store_root / module_name / version
        if not module_dir.exists():
            return False
        
        # Check if active
        current_json_path = self.store_root / module_name / "current.json"
        if current_json_path.exists():
            with open(current_json_path, 'r') as f:
                current_data = json.load(f)
                if current_data.get("version") == version:
                    raise ValueError(f"Cannot remove active version {version} of {module_name}")
        
        # Remove directory
        shutil.rmtree(module_dir)
        self._remove_module_dir_if_empty(module_name)
        return True

    def _remove_module_dir_if_empty(self, module_name: str) -> None:
        """Удаляет каталог модуля, если в нём не осталось версий (остался пустым или только current.json)."""
        module_base_dir = self.store_root / module_name
        if not module_base_dir.exists():
            return
        remaining = [p for p in module_base_dir.iterdir() if p.name != "current.json"]
        if not remaining:
            try:
                if (module_base_dir / "current.json").exists():
                    (module_base_dir / "current.json").unlink()
                shutil.rmtree(module_base_dir)
            except OSError:
                pass

    def remove_version_force(self, module_name: str, version: str) -> bool:
        """
        Удаляет версию модуля с диска даже если она активна (для отката при сбое загрузки).
        Сначала деактивирует модуль, затем удаляет каталог.
        
        Returns:
            True если каталог удалён, False если каталога не было
        """
        module_dir = self.store_root / module_name / version
        if not module_dir.exists():
            return False
        current_json_path = self.store_root / module_name / "current.json"
        if current_json_path.exists():
            try:
                with open(current_json_path, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
                    if current_data.get("version") == version:
                        current_json_path.unlink()
            except (json.JSONDecodeError, IOError):
                pass
        shutil.rmtree(module_dir)
        self._remove_module_dir_if_empty(module_name)
        return True

    def remove_module(self, module_name: str) -> bool:
        """
        Удаляет все версии модуля (если не active).
        
        Returns:
            True if removed, False if not found or active
        """
        module_base_dir = self.store_root / module_name
        if not module_base_dir.exists():
            return False
        
        # Check if any version is active
        current_json_path = module_base_dir / "current.json"
        if current_json_path.exists():
            raise ValueError(f"Cannot remove module {module_name}: has active version")
        
        # Remove entire module directory
        shutil.rmtree(module_base_dir)
        return True

    def garbage_collect(self, module_name: str, keep: int = 2) -> list:
        """
        GC: оставляет не более `keep` последних версий (current + prev).
        Удаляет все версии старше текущей и предыдущей.

        Args:
            module_name: Имя модуля
            keep: Количество версий для сохранения (default 2: current+prev)

        Returns:
            Список удалённых версий
        """
        module_dir = self.store_root / module_name
        if not module_dir.exists():
            return []

        # Собираем версии с валидным manifest.json
        versions = sorted(
            [
                item.name
                for item in module_dir.iterdir()
                if item.is_dir() and (item / "manifest.json").exists()
            ],
            key=_version_sort_key,
        )

        if len(versions) <= keep:
            return []

        # Читаем активную версию
        current_json_path = module_dir / "current.json"
        active_version = None
        if current_json_path.exists():
            try:
                with open(current_json_path, "r", encoding="utf-8") as f:
                    active_version = json.load(f).get("version")
            except (json.JSONDecodeError, IOError):
                pass

        # Определяем сохраняемые версии: последние `keep` отсортированных,
        # но active_version должна быть среди сохраняемых
        to_keep_set = set(versions[-keep:])
        if active_version:
            to_keep_set.add(active_version)

        removed = []
        for version in versions:
            if version not in to_keep_set:
                try:
                    shutil.rmtree(module_dir / version)
                    removed.append(version)
                except OSError as e:
                    pass  # Не блокируем GC из-за одной ошибки

        return removed
