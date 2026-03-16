"""
Модуль настройки системы логирования на основе библиотеки loguru.
Обеспечивает двойное логирование: в консоль и в файл с ротацией.
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logging():
    """
    Настраивает систему логирования для приложения.
    
    Конфигурация:
    - Консоль (stderr): уровень INFO и выше
    - Файл logs/agent.log: уровень DEBUG и выше с ротацией
    
    Особенности:
    - Автоматическое создание директории logs, если она не существует
    - Ротация файла логов при достижении 10 MB
    - Автоматическое сжатие старых логов в zip-архивы
    - UTF-8 кодировка для корректной работы на всех платформах
    """
    # Удаляем стандартный обработчик loguru
    # По умолчанию loguru пишет в stderr, мы настроим свои обработчики
    logger.remove()
    
    # Обработчик для консоли (stderr)
    # Уровень INFO - показываем только важные сообщения
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    
    # Определяем директорию для логов
    # Используем абсолютный путь относительно корня проекта
    current_dir = Path(__file__).resolve().parent.parent  # поднимаемся до pc_agent/
    logs_dir = current_dir / "logs"
    
    # Создаем директорию logs, если она не существует
    # exist_ok=True предотвращает ошибку, если директория уже есть
    logs_dir.mkdir(exist_ok=True)
    
    # Путь к файлу логов
    log_file = logs_dir / "agent.log"
    
    # Обработчик для файла с расширенными настройками
    logger.add(
        log_file,
        level="DEBUG",  # Записываем все сообщения, включая отладочные
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",  # Ротация при достижении 10 мегабайт
        compression="zip",  # Сжимаем старые логи для экономии места
        encoding="utf-8",  # UTF-8 кодировка (критично для Windows)
        enqueue=True,  # Асинхронная запись для безопасности в многопоточной среде
        backtrace=True,  # Включаем полный traceback для исключений
        diagnose=True  # Добавляем значения переменных в traceback
    )
    
    logger.info("Система логирования инициализирована")
    logger.debug(f"Логи сохраняются в: {log_file}")


# Инициализируем логирование при импорте модуля
setup_logging()

