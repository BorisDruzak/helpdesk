"""
Пример использования универсального контроллера AgentOrchestrator.

Этот скрипт демонстрирует различные способы использования оркестратора
для обработки команд агента.
"""

import asyncio
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.database import db_manager


async def example_basic_usage():
    """
    Пример базового использования оркестратора.
    """
    logger.info("=" * 70)
    logger.info("📚 Пример 1: Базовое использование")
    logger.info("=" * 70)
    
    # Создаем оркестратор
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    # Инициализируем
    await orchestrator.initialize()
    
    # Отправляем команду ping
    result = await orchestrator.handle_command({'cmd': 'ping'})
    logger.info(f"Ping результат: {result}")
    
    # Завершаем работу
    await orchestrator.shutdown()


async def example_collect_data():
    """
    Пример сбора данных с модулей.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📚 Пример 2: Сбор данных")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Собираем данные со всех модулей
    result = await orchestrator.handle_command({'cmd': 'collect'})
    logger.info(f"Собранные данные: {result['data']}")
    
    # Собираем данные с конкретного модуля
    result = await orchestrator.handle_command({
        'cmd': 'collect',
        'modules': ['system']
    })
    logger.info(f"Данные от system: {result['data']['system']}")
    
    await orchestrator.shutdown()


async def example_list_modules():
    """
    Пример получения списка модулей.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📚 Пример 3: Список модулей")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Получаем список модулей
    result = await orchestrator.handle_command({'cmd': 'list_modules'})
    
    logger.info(f"Всего модулей: {result['data']['total_count']}")
    for module in result['data']['modules']:
        logger.info(f"  - {module['name']}: {module['description']}")
    
    await orchestrator.shutdown()


async def example_error_handling():
    """
    Пример обработки ошибок.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📚 Пример 4: Обработка ошибок")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Неизвестная команда
    result = await orchestrator.handle_command({'cmd': 'unknown_command'})
    logger.info(f"Неизвестная команда: {result}")
    
    # Пустая команда
    result = await orchestrator.handle_command({})
    logger.info(f"Пустая команда: {result}")
    
    # Несуществующий модуль
    result = await orchestrator.handle_command({
        'cmd': 'collect',
        'modules': ['nonexistent_module']
    })
    logger.info(f"Несуществующий модуль: {result}")
    
    await orchestrator.shutdown()


async def example_integration_with_websocket():
    """
    Пример интеграции с WebSocket агентом.
    
    Этот пример показывает, как можно использовать оркестратор
    для обработки команд, поступающих через WebSocket.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📚 Пример 5: Интеграция с WebSocket")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Симулируем получение команд через WebSocket
    websocket_commands = [
        {'cmd': 'ping'},
        {'cmd': 'collect'},
        {'cmd': 'list_modules'},
    ]
    
    for command in websocket_commands:
        logger.info(f"\n📨 Обработка команды: {command}")
        result = await orchestrator.handle_command(command)
        logger.info(f"✅ Результат: {result['status']}")
        
        # В реальном приложении здесь бы отправлялся ответ через WebSocket
        # await websocket.send_json(result)
    
    await orchestrator.shutdown()


async def main():
    """
    Главная функция для запуска всех примеров.
    """
    logger.info("🚀 Запуск примеров использования AgentOrchestrator\n")
    
    # Запускаем все примеры
    await example_basic_usage()
    await example_collect_data()
    await example_list_modules()
    await example_error_handling()
    await example_integration_with_websocket()
    
    logger.info("\n" + "=" * 70)
    logger.success("✅ Все примеры выполнены успешно!")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

