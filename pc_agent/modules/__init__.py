"""
Фабрика модулей для динамической загрузки плагинов.

Этот модуль реализует паттерн Factory для создания экземпляров модулей-коллекторов
на основе их названий. Использует динамический импорт (importlib) для загрузки
модулей во время выполнения программы.
"""

import importlib
import inspect
from typing import List, Optional
from loguru import logger

from .base_module import BaseCollector


class ModuleFactory:
    """
    Фабрика для динамического создания экземпляров модулей-коллекторов.
    
    Основная задача фабрики - превратить список строк с именами модулей
    (например: ["screen", "system", "input"]) в список инициализированных
    объектов этих модулей.
    
    Преимущества динамической загрузки:
    1. Модули загружаются только если они нужны
    2. Легко добавлять новые модули без изменения кода фабрики
    3. Можно управлять списком модулей через конфигурацию
    4. Ошибки в одном модуле не ломают всю систему
    """
    
    @staticmethod
    def create_modules(module_names: List[str], extra_paths: Optional[List[str]] = None) -> List[BaseCollector]:
        """
        Создает список экземпляров модулей на основе их названий.
        
        Алгоритм работы:
        1. Для каждого имени модуля (например "screen")
        2. Сначала пытается загрузить из extra_paths (если указаны)
        3. Если не найден, формируется полный путь импорта: "modules.impl.screen"
        4. С помощью importlib динамически импортируется модуль
        5. В модуле ищется класс, наследующийся от BaseCollector
        6. Создается экземпляр найденного класса
        7. Экземпляр добавляется в результирующий список
        
        Если модуль не найден или произошла ошибка - модуль пропускается,
        но программа продолжает работу.
        
        Args:
            module_names: Список строк с именами модулей.
                         Например: ["screen", "system", "input"]
            extra_paths: Дополнительные пути для поиска модулей (опционально)
        
        Returns:
            List[BaseCollector]: Список инициализированных модулей.
                                Может быть пустым, если все модули упали с ошибкой.
        
        Example:
            >>> factory = ModuleFactory()
            >>> modules = factory.create_modules(["screen", "system"])
            >>> print(modules)
            [<Collector: screen>, <Collector: system>]
        """
        loaded_modules: List[BaseCollector] = []
        
        logger.info(f"Начинаю загрузку модулей: {module_names}")
        
        # Добавляем extra_paths в sys.path если они указаны
        import sys
        added_paths = []
        if extra_paths:
            for path in extra_paths:
                path_str = str(path)
                if path_str not in sys.path:
                    sys.path.insert(0, path_str)
                    added_paths.append(path_str)
                    logger.debug(f"Добавлен extra_path в sys.path: {path_str}")
        
        try:
            for module_name in module_names:
                try:
                    imported_module = None
                    
                    # Сначала пытаемся загрузить из extra_paths
                    if extra_paths:
                        imported_module = ModuleFactory._load_from_extra_paths(
                            module_name=module_name,
                            extra_paths=extra_paths,
                        )
                    
                    # Если не найден в extra_paths, пытаемся стандартный package path.
                    if imported_module is None:
                        module_path = f"pc_agent.modules.impl.{module_name}"
                        logger.debug(f"Попытка импорта модуля: {module_path}")
                        imported_module = importlib.import_module(module_path)
                        logger.debug(f"Модуль {module_path} успешно импортирован")
                    
                    # Поиск класса-коллектора
                    collector_class = ModuleFactory._find_collector_class(
                        imported_module, 
                        module_name
                    )
                    
                    if collector_class is None:
                        logger.error(
                            f"В модуле {module_name} не найден класс, "
                            f"наследующийся от BaseCollector"
                        )
                        continue
                    
                    # Создание экземпляра
                    collector_instance = collector_class()
                    logger.success(f"Модуль {collector_instance} успешно загружен")
                    loaded_modules.append(collector_instance)
                    
                except ModuleNotFoundError:
                    logger.error(
                        f"Модуль '{module_name}' не найден. "
                        f"Проверьте наличие файла modules/impl/{module_name}.py"
                    )
                    
                except ImportError as e:
                    logger.error(
                        f"Ошибка импорта модуля '{module_name}': {e}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Неожиданная ошибка при загрузке модуля '{module_name}': {e}",
                        exc_info=True
                    )
        finally:
            # Удаляем добавленные пути из sys.path
            for path in added_paths:
                if path in sys.path:
                    sys.path.remove(path)
                    logger.debug(f"Удален extra_path из sys.path: {path}")
        
        # Итоговая статистика
        logger.info(
            f"Загрузка модулей завершена. "
            f"Успешно: {len(loaded_modules)}/{len(module_names)}"
        )
        
        return loaded_modules

    @staticmethod
    def _load_from_extra_paths(module_name: str, extra_paths: List[str]):
        """
        Пытается импортировать модуль из extra_paths.

        Поддерживает обычное имя модуля и legacy-формат test_<module_name>.
        Возвращает импортированный модуль или None, если ни один кандидат не найден.
        """
        candidates = [module_name, f"test_{module_name}"]
        attempts = []

        for extra_path in extra_paths:
            for candidate in candidates:
                try:
                    logger.debug(
                        f"Пытаюсь загрузить модуль '{candidate}' из extra_path '{extra_path}'"
                    )
                    imported_module = importlib.import_module(candidate)
                    logger.debug(
                        f"Модуль '{candidate}' успешно загружен из extra_path '{extra_path}'"
                    )
                    return imported_module
                except ModuleNotFoundError:
                    attempts.append(f"{extra_path}:{candidate}:not_found")
                except ImportError as exc:
                    attempts.append(f"{extra_path}:{candidate}:import_error:{exc}")

        if attempts:
            logger.debug(
                f"Модуль '{module_name}' не найден в extra_paths. Проверены кандидаты: {attempts}"
            )
        return None
    
    @staticmethod
    def _find_collector_class(module, module_name: str) -> Optional[type]:
        """
        Находит класс-коллектор внутри импортированного модуля.
        
        Алгоритм:
        1. Получаем все объекты (классы, функции, переменные) из модуля
        2. Фильтруем только классы (inspect.isclass)
        3. Проверяем, что класс наследуется от BaseCollector
        4. Проверяем, что это не сам BaseCollector
        5. Возвращаем первый найденный класс
        
        Args:
            module: Импортированный модуль (результат importlib.import_module)
            module_name: Имя модуля (для логирования)
        
        Returns:
            Optional[type]: Найденный класс-коллектор или None
        
        Technical Details:
            inspect.getmembers() возвращает список кортежей (имя, объект)
            inspect.isclass() проверяет, является ли объект классом
            issubclass() проверяет наследование
        """
        logger.debug(f"Поиск класса-коллектора в модуле {module_name}")
        
        # Проверяем, что BaseCollector доступен
        try:
            from .base_module import BaseCollector as LocalBaseCollector
        except ImportError:
            logger.error(f"Не удалось импортировать BaseCollector для модуля {module_name}")
            return None
        
        # КРИТИЧНО: Пытаемся получить BaseCollector из самого модуля
        # Это нужно, потому что модуль может импортировать BaseCollector из другого пути
        # (например, modules.base_module вместо pc_agent.modules.base_module)
        module_base_collector = getattr(module, 'BaseCollector', None)
        if module_base_collector is None:
            # Если в модуле нет BaseCollector, используем локальный
            base_collector_class = LocalBaseCollector
        else:
            # Используем BaseCollector из модуля для проверки совместимости
            base_collector_class = module_base_collector
        
        # inspect.getmembers возвращает все атрибуты модуля
        # inspect.isclass фильтрует только классы
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Пропускаем встроенные типы
            if name in ('Any', 'Dict', 'List', 'Optional', 'BaseModel', 'Path'):
                continue
            # Пропускаем сам BaseCollector
            if name == 'BaseCollector':
                continue
            # Проверяем наследование через issubclass (полная цепочка MRO, не только __bases__).
            # Учитываем, что модуль может импортировать BaseCollector через другой путь
            # (modules.base_module vs pc_agent.modules.base_module) — оба варианта принимаем.
            try:
                is_subclass = (
                    issubclass(obj, base_collector_class) or
                    issubclass(obj, LocalBaseCollector)
                )
                is_not_base = obj is not base_collector_class and obj is not LocalBaseCollector
                if is_subclass and is_not_base:
                    logger.debug(f"Найден класс-коллектор: {name}")
                    return obj
            except TypeError as e:
                logger.debug(f"Ошибка при проверке {name}: {e}")
                continue
        
        # Если ничего не найдено
        return None


# Удобный алиас для импорта
# Теперь можно использовать: from pc_agent.modules import create_modules
create_modules = ModuleFactory.create_modules


# Экспортируемые символы модуля
__all__ = [
    'BaseCollector',      # Базовый класс для создания модулей
    'ModuleFactory',      # Фабрика для загрузки модулей
    'create_modules',     # Функция-алиас для быстрого создания модулей
]
