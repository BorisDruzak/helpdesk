"""
Модуль статического анализа кода для валидации плагинов.
Использует библиотеку ast для безопасного парсинга и анализа Python кода.
"""
import ast
from typing import Optional
from loguru import logger


class CodeValidator:
    """
    Статический анализатор кода для определения типа плагина.
    
    Поддерживает два типа плагинов:
    - 'class': Класс, наследующийся от BaseCollector
    - 'function': Асинхронная функция с именем 'run'
    """
    
    @staticmethod
    def validate(code: str) -> Optional[str]:
        """
        Валидирует и определяет тип плагина по исходному коду.
        
        Args:
            code (str): Исходный код Python для анализа
            
        Returns:
            Optional[str]: 
                - 'class' - если найден класс, наследующийся от BaseCollector
                - 'function' - если найдена асинхронная функция 'run'
                - None - если код невалидный или не соответствует ни одному типу
                
        Example:
            >>> code = '''
            ... class MyCollector(BaseCollector):
            ...     async def collect(self):
            ...         return {}
            ... '''
            >>> CodeValidator.validate(code)
            'class'
            
            >>> code = '''
            ... async def run():
            ...     return {"result": "ok"}
            ... '''
            >>> CodeValidator.validate(code)
            'function'
        """
        try:
            # Шаг 1: Попытка парсинга кода
            tree = ast.parse(code)
            logger.debug("Код успешно распарсен, начинаю анализ AST дерева")
            
        except SyntaxError as e:
            # Если синтаксическая ошибка - логируем и возвращаем None
            logger.error(f"Ошибка парсинга кода: {e}")
            return None
        
        # Шаг 2: Проходим по всем узлам AST дерева
        for node in ast.walk(tree):
            
            # Проверка на класс, наследующийся от BaseCollector
            if isinstance(node, ast.ClassDef):
                # Проверяем базовые классы
                for base in node.bases:
                    # Проверяем, что базовый класс имеет имя и это имя - BaseCollector
                    if isinstance(base, ast.Name) and base.id == 'BaseCollector':
                        logger.debug(f"Найден класс {node.name}, наследующийся от BaseCollector")
                        return 'class'
            
            # Проверка на асинхронную функцию с именем 'run'
            if isinstance(node, ast.AsyncFunctionDef):
                if node.name == 'run':
                    logger.debug(f"Найдена асинхронная функция 'run'")
                    return 'function'
        
        # Шаг 3: Если ничего не найдено - возвращаем None
        logger.debug("Код не соответствует ни одному типу плагина")
        return None

