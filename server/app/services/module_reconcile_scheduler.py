"""
Периодический планировщик reconcile для модульной системы.

Запускает reconcile_all_devices каждые RECONCILE_INTERVAL_SEC секунд.
При массовом reconnect — backoff + jitter для снижения нагрузки.
"""

import asyncio
import random
from loguru import logger

RECONCILE_INTERVAL_SEC = 300  # 5 минут


async def start_reconcile_scheduler(state: object) -> None:
    """
    Корутина для фоновой периодической сверки desired vs actual состояния модулей.
    Запускать через asyncio.create_task().
    """
    logger.info(f"[reconcile_scheduler] Started (interval={RECONCILE_INTERVAL_SEC}s)")
    # Jitter при старте — чтобы не совпасть с другими задачами
    await asyncio.sleep(random.uniform(10, 30))

    while True:
        try:
            from modules.reconcile import reconcile_all_devices
            stats = await reconcile_all_devices(state=state, reason="periodic")
            if stats.get("devices", 0) > 0:
                logger.info(f"[reconcile_scheduler] periodic run: {stats}")
        except asyncio.CancelledError:
            logger.info("[reconcile_scheduler] Cancelled, shutting down")
            break
        except Exception as e:
            logger.error(f"[reconcile_scheduler] Error: {e}", exc_info=True)

        # Jitter: ±10% от интервала
        jitter = random.uniform(-0.1, 0.1) * RECONCILE_INTERVAL_SEC
        await asyncio.sleep(RECONCILE_INTERVAL_SEC + jitter)
