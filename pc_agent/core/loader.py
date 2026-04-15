"""
Dynamic loader for package modules stored in modules_store.

Loads modules from data/modules_store/<name>/<version> using an entrypoint
such as module:register. Supports class-based and function-based plugins.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Callable, Awaitable, Any, Dict

from pc_agent.modules.base_module import BaseCollector
from loguru import logger


class FunctionWrapper(BaseCollector):
    """Wraps an async function so it behaves like a BaseCollector instance."""

    def __init__(self, name: str, func: Callable[[], Awaitable[Dict[str, Any]]]):
        self._name = name
        self.func = func
        logger.debug(f"Created FunctionWrapper for module '{name}'")

    @property
    def name(self) -> str:
        return self._name

    async def collect(self) -> Dict[str, Any]:
        logger.debug(f"[{self.name}] Calling wrapped function")
        return await self.func()


class DynamicModuleLoader:
    """Loads package modules from modules_store paths."""

    def __init__(self, data_root: Optional[Path] = None):
        self._data_root = data_root
        self._loaded_module_keys_by_name: dict[str, set[str]] = {}
        logger.debug("DynamicModuleLoader initialized")

    def _remember_loaded_key(self, module_name: str, import_key: str) -> None:
        self._loaded_module_keys_by_name.setdefault(module_name, set()).add(import_key)

    def unload_module(self, module_name: str) -> None:
        """Remove tracked Python imports for a dynamic module."""
        for import_key in self._loaded_module_keys_by_name.pop(module_name, set()):
            sys.modules.pop(import_key, None)

    def reset_runtime_cache(self) -> None:
        """Clear all tracked dynamic imports before a registry rebuild."""
        for module_name in list(self._loaded_module_keys_by_name):
            self.unload_module(module_name)

    def _resolve_module_file(self, module_path: Path, import_name: str) -> Optional[Path]:
        parts = [part for part in import_name.split('.') if part]
        if not parts:
            return None

        py_candidate = module_path.joinpath(*parts).with_suffix('.py')
        if py_candidate.exists():
            return py_candidate

        package_candidate = module_path.joinpath(*parts, '__init__.py')
        if package_candidate.exists():
            return package_candidate

        return None

    def _load_module_object(self, module_name: str, module_path: Path, import_name: str):
        module_file = self._resolve_module_file(module_path, import_name)
        if module_file is not None:
            unique_name = (
                f"_pcagent_dynamic_{module_name}_{abs(hash(str(module_path.resolve())))}_"
                f"{import_name.replace('.', '_')}"
            )
            sys.modules.pop(unique_name, None)
            if module_file.name == '__init__.py':
                spec = importlib.util.spec_from_file_location(
                    unique_name,
                    module_file,
                    submodule_search_locations=[str(module_file.parent)],
                )
            else:
                spec = importlib.util.spec_from_file_location(unique_name, module_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create import spec for {module_file}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            self._remember_loaded_key(module_name, unique_name)
            spec.loader.exec_module(module)
            return module

        if import_name in sys.modules:
            del sys.modules[import_name]
        module = importlib.import_module(import_name)
        self._remember_loaded_key(module_name, import_name)
        return module

    def load_module_from_path(self, module_name: str, module_path: Path, entrypoint: str | None = None) -> BaseCollector:
        logger.info(f"Loading module '{module_name}' from '{module_path}'")

        if not module_path.exists():
            error_msg = f"Module path does not exist: {module_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        agent_dir = Path(__file__).resolve().parent.parent
        project_root = agent_dir.parent

        module_path_str = str(module_path.resolve())
        if module_path_str in sys.path:
            sys.path.remove(module_path_str)
        sys.path.insert(0, module_path_str)

        agent_dir_str = str(agent_dir.resolve())
        if agent_dir_str in sys.path:
            sys.path.remove(agent_dir_str)
        sys.path.insert(1, agent_dir_str)
        logger.debug(f"Ensured agent directory in sys.path: {agent_dir_str}")

        project_root_str = str(project_root.resolve())
        if project_root_str in sys.path:
            sys.path.remove(project_root_str)
        sys.path.insert(2, project_root_str)
        logger.debug(f"Ensured project root in sys.path: {project_root_str}")

        logger.debug(f"Moved '{module_path_str}' to the front of sys.path")

        self.unload_module(module_name)

        try:
            if entrypoint and ':' in entrypoint:
                entry_module_name, func_name = [part.strip() for part in entrypoint.split(':', 1)]
                logger.debug(
                    f"Using entrypoint module='{entry_module_name}', function='{func_name}'"
                )
                module = self._load_module_object(module_name, module_path, entry_module_name)

                if not hasattr(module, func_name):
                    error_msg = f"Function '{func_name}' not found in module '{entry_module_name}'"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                func = getattr(module, func_name)
                if not callable(func):
                    error_msg = f"'{func_name}' in module '{entry_module_name}' is not callable"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                instance = func()
                base_for_check = getattr(module, 'BaseCollector', BaseCollector)
                if not isinstance(instance, base_for_check) and not isinstance(instance, BaseCollector):
                    error_msg = (
                        f"Function '{func_name}' in module '{entry_module_name}' did not return BaseCollector"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                logger.success(f"Module '{module_name}' loaded via entrypoint '{entrypoint}'")
                return instance

            module_py_path = module_path / 'module.py'
            if module_py_path.exists():
                logger.debug("Found module.py, importing it directly from file path")
                module = self._load_module_object(module_name, module_path, 'module')
            else:
                logger.debug(f"module.py not found, importing '{module_name}'")
                module = self._load_module_object(module_name, module_path, module_name)

            logger.success("Module imported successfully")

            base_for_check = getattr(module, 'BaseCollector', BaseCollector)
            collector_class = None
            has_run_function = hasattr(module, 'run')

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if not isinstance(attr, type) or attr in (BaseCollector, base_for_check):
                    continue
                if issubclass(attr, base_for_check) or issubclass(attr, BaseCollector):
                    collector_class = attr
                    break

            if collector_class:
                instance = collector_class()
                logger.success(
                    f"Created instance of {collector_class.__name__} for module '{module_name}'"
                )
                return instance

            if has_run_function:
                import inspect
                run_func = getattr(module, 'run')
                if inspect.iscoroutinefunction(run_func):
                    wrapper = FunctionWrapper(module_name, run_func)
                    logger.success(f"Created FunctionWrapper for module '{module_name}'")
                    return wrapper
                error_msg = f"Function 'run' in module '{module_name}' must be async"
                logger.error(error_msg)
                raise ValueError(error_msg)

            error_msg = f"Module '{module_name}' has no collector class and no async run()"
            logger.error(error_msg)
            raise ValueError(error_msg)

        except ImportError as exc:
            logger.error(f"Failed to import module '{module_name}': {exc}")
            raise
        except Exception as exc:
            logger.error(f"Error while loading module '{module_name}': {exc}")
            raise
