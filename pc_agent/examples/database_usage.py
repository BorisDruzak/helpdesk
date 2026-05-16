#!/usr/bin/env python3
"""
Примеры использования DatabaseManager в различных сценариях.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from pc_agent.core.database import db_manager
from loguru import logger


async def example_1_basic_usage():
    """
    Пример 1: Базовое использование - добавление и получение событий.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 1: Базовое использование")
    logger.info("=" * 60)
    
    # Инициализация БД
    await db_manager.init_db()
    
    # Добавление событий от разных модулей
    await db_manager.add_event(
        module="system",
        data={
            "cpu_percent": 45.2,
            "memory_percent": 62.8,
            "disk_usage": 75.3
        }
    )
    
    await db_manager.add_event(
        module="screen",
        data={
            "resolution": "1920x1080",
            "format": "png"
        },
        file_path="/tmp/screenshots/screen_001.png"
    )
    
    # Получение событий для отправки
    events = await db_manager.get_pending_batch(limit=10)
    logger.info(f"Получено {len(events)} событий для отправки")
    
    for event in events:
        logger.info(f"  ID: {event['id']}, Модуль: {event['module']}")
    
    logger.success("Пример 1 завершен\n")


async def example_2_batch_processing():
    """
    Пример 2: Пакетная обработка - отправка и обновление статуса.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 2: Пакетная обработка")
    logger.info("=" * 60)
    
    # Добавляем несколько событий
    for i in range(5):
        await db_manager.add_event(
            module="input",
            data={
                "activity_count": i * 10,
                "last_activity": f"keyboard_{i}"
            }
        )
    
    # Получаем пакет для отправки
    batch = await db_manager.get_pending_batch(limit=3)
    logger.info(f"Обрабатываем пакет из {len(batch)} событий")
    
    # Симулируем отправку на сервер
    event_ids = [event['id'] for event in batch]
    logger.info(f"Отправка событий с ID: {event_ids}")
    
    # После успешной отправки помечаем как отправленные
    updated = await db_manager.mark_as_sent(event_ids)
    logger.success(f"Обновлено {updated} событий")
    
    # Проверяем, сколько осталось pending
    remaining = await db_manager.get_pending_batch()
    logger.info(f"Осталось pending событий: {len(remaining)}")
    
    logger.success("Пример 2 завершен\n")


async def example_3_statistics():
    """
    Пример 3: Получение статистики по базе данных.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 3: Статистика")
    logger.info("=" * 60)
    
    stats = await db_manager.get_statistics()
    
    logger.info(f"Всего записей: {stats['total']}")
    logger.info(f"По статусам: {stats['by_status']}")
    logger.info(f"По модулям: {stats['by_module']}")
    
    logger.success("Пример 3 завершен\n")


async def example_4_cleanup():
    """
    Пример 4: Очистка старых записей.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 4: Очистка старых записей")
    logger.info("=" * 60)
    
    # Показываем статистику до очистки
    stats_before = await db_manager.get_statistics()
    logger.info(f"До очистки: {stats_before['total']} записей")
    
    # Очищаем записи старше 0 часов (для демонстрации)
    # В реальном приложении используйте 24 или более часов
    deleted = await db_manager.cleanup_sent_events(max_age_hours=0)
    logger.info(f"Удалено {deleted} старых записей")
    
    # Показываем статистику после очистки
    stats_after = await db_manager.get_statistics()
    logger.info(f"После очистки: {stats_after['total']} записей")
    
    logger.success("Пример 4 завершен\n")


async def example_5_error_handling():
    """
    Пример 5: Обработка ошибок.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 5: Обработка ошибок")
    logger.info("=" * 60)
    
    try:
        # Попытка добавить событие с некорректными данными
        # (в данном случае все данные корректны, но показываем структуру)
        await db_manager.add_event(
            module="test",
            data={"test": "value"}
        )
        logger.success("Событие добавлено успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении события: {e}")
    
    try:
        # Попытка обновить несуществующие ID
        result = await db_manager.mark_as_sent([9999, 10000])
        logger.info(f"Обновлено записей: {result}")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении: {e}")
    
    logger.success("Пример 5 завершен\n")


async def example_6_module_integration():
    """
    Пример 6: Интеграция с модулем сбора данных.
    """
    logger.info("=" * 60)
    logger.info("ПРИМЕР 6: Интеграция с модулем")
    logger.info("=" * 60)
    
    # Симулируем работу модуля screen
    async def screen_module_collect():
        """Симуляция сбора данных модулем screen."""
        logger.info("Модуль screen: делаю скриншот...")
        
        # Здесь был бы реальный код снятия скриншота
        screenshot_path = "/tmp/screenshot_123.png"
        screenshot_data = {
            "resolution": "1920x1080",
            "format": "png",
            "size_bytes": 245678
        }
        
        # Сохраняем событие в БД
        event_id = await db_manager.add_event(
            module="screen",
            data=screenshot_data,
            file_path=screenshot_path
        )
        
        logger.success(f"Скриншот сохранен в БД с ID: {event_id}")
        return event_id
    
    # Симулируем работу модуля system
    async def system_module_collect():
        """Симуляция сбора данных модулем system."""
        logger.info("Модуль system: собираю системную информацию...")
        
        # Здесь был бы реальный код сбора системной информации
        system_data = {
            "cpu_percent": 42.5,
            "memory_percent": 68.2,
            "disk_usage": 73.1,
            "uptime_hours": 48.5
        }
        
        # Сохраняем событие в БД
        event_id = await db_manager.add_event(
            module="system",
            data=system_data
        )
        
        logger.success(f"Системная информация сохранена в БД с ID: {event_id}")
        return event_id
    
    # Запускаем модули
    await screen_module_collect()
    await system_module_collect()
    
    # Проверяем статистику
    stats = await db_manager.get_statistics()
    logger.info(f"Статистика после работы модулей: {stats}")
    
    logger.success("Пример 6 завершен\n")


async def main():
    """
    Главная функция - запускает все примеры.
    """
    logger.info("\n" + "=" * 60)
    logger.info("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ DatabaseManager")
    logger.info("=" * 60 + "\n")
    
    # Инициализируем БД один раз
    await db_manager.init_db()
    
    # Запускаем примеры
    await example_1_basic_usage()
    await example_2_batch_processing()
    await example_3_statistics()
    await example_6_module_integration()
    await example_5_error_handling()
    
    # Очистка в конце
    await example_4_cleanup()
    
    logger.info("=" * 60)
    logger.success("ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ УСПЕШНО!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

