"""
Пример использования команды exec_script с автоматическим пробросом модулей.

Этот пример демонстрирует, как динамические скрипты могут использовать
загруженные модули без явного импорта.
"""

import asyncio
from loguru import logger
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.database import db_manager


async def example_1_simple_module_usage():
    """
    Пример 1: Простое использование модулей в скрипте.
    """
    logger.info("=" * 70)
    logger.info("🧪 Пример 1: Простое использование модулей")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Скрипт, который использует модуль 'system' напрямую
    result = await orchestrator.handle_command({
        'cmd': 'exec_script',
        'code': '''
async def run():
    # Модуль 'system' доступен автоматически!
    data = await system.collect()
    
    logger.info(f"Получены данные: CPU={data['cpu']}%, RAM={data['ram']}%")
    
    return {
        'cpu': data['cpu'],
        'ram': data['ram'],
        'disk': data['disk']
    }
'''
    })
    
    logger.success(f"Результат: {result}")
    await orchestrator.shutdown()


async def example_2_multiple_modules():
    """
    Пример 2: Использование нескольких модулей одновременно.
    """
    logger.info("\n" + "=" * 70)
    logger.info("🧪 Пример 2: Использование нескольких модулей")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system", "screen"]
    )
    
    await orchestrator.initialize()
    
    # Скрипт, который использует несколько модулей
    result = await orchestrator.handle_command({
        'cmd': 'exec_script',
        'code': '''
async def run():
    import json
    
    # Используем оба модуля
    sys_data = await system.collect()
    screen_data = await screen.collect()
    
    logger.info(f"System: CPU={sys_data['cpu']}%, RAM={sys_data['ram']}%")
    logger.info(f"Screen: Screenshot captured, size={len(screen_data.get('screenshot', ''))}")
    
    return {
        'system': {
            'cpu': sys_data['cpu'],
            'ram': sys_data['ram']
        },
        'screen': {
            'has_screenshot': 'screenshot' in screen_data,
            'screenshot_size': len(screen_data.get('screenshot', ''))
        }
    }
'''
    })
    
    logger.success(f"Результат: {result}")
    await orchestrator.shutdown()


async def example_3_conditional_logic():
    """
    Пример 3: Условная логика на основе данных модулей.
    """
    logger.info("\n" + "=" * 70)
    logger.info("🧪 Пример 3: Условная логика")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system", "screen"]
    )
    
    await orchestrator.initialize()
    
    # Скрипт с условной логикой
    result = await orchestrator.handle_command({
        'cmd': 'exec_script',
        'code': '''
async def run():
    # Получаем системные данные
    sys_data = await system.collect()
    
    cpu = sys_data['cpu']
    ram = sys_data['ram']
    
    logger.info(f"Current load: CPU={cpu}%, RAM={ram}%")
    
    # Если нагрузка высокая, делаем скриншот для диагностики
    if cpu > 50 or ram > 70:
        logger.warning("⚠️ High system load detected! Capturing screenshot...")
        screen_data = await screen.collect()
        
        return {
            'alert': 'high_load',
            'cpu': cpu,
            'ram': ram,
            'screenshot_captured': True,
            'screenshot_size': len(screen_data.get('screenshot', ''))
        }
    else:
        logger.info("✅ System load is normal")
        return {
            'alert': 'ok',
            'cpu': cpu,
            'ram': ram,
            'screenshot_captured': False
        }
'''
    })
    
    logger.success(f"Результат: {result}")
    await orchestrator.shutdown()


async def example_4_process_provider():
    """
    Пример 4: Использование ProcessProvider в скрипте.
    """
    logger.info("\n" + "=" * 70)
    logger.info("🧪 Пример 4: Использование ProcessProvider")
    logger.info("=" * 70)
    
    orchestrator = AgentOrchestrator(
        db_manager=db_manager,
        enabled_modules=["system"]
    )
    
    await orchestrator.initialize()
    
    # Скрипт, который использует ProcessProvider
    result = await orchestrator.handle_command({
        'cmd': 'exec_script',
        'code': '''
async def run():
    # ProcessProvider доступен автоматически
    provider = ProcessProvider.get_instance()
    
    # Получаем информацию об активном окне
    active_win = provider.get_active_window()
    
    logger.info(f"Active window: {active_win['title']}")
    logger.info(f"Process: {active_win['process_name']}")
    
    # Также можем использовать модули
    sys_data = await system.collect()
    
    return {
        'active_window': {
            'title': active_win['title'],
            'process': active_win['process_name']
        },
        'system': {
            'cpu': sys_data['cpu'],
            'ram': sys_data['ram']
        }
    }
'''
    })
    
    logger.success(f"Результат: {result}")
    await orchestrator.shutdown()


async def main():
    """
    Главная функция для запуска всех примеров.
    """
    try:
        # Запускаем все примеры по очереди
        await example_1_simple_module_usage()
        await example_2_multiple_modules()
        await example_3_conditional_logic()
        await example_4_process_provider()
        
        logger.info("\n" + "=" * 70)
        logger.success("✅ Все примеры выполнены успешно!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Ошибка во время выполнения примеров: {e}")
        logger.exception(e)


if __name__ == "__main__":
    asyncio.run(main())






