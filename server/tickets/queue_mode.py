"""Reversible queue partitioning; stored routing history is never rewritten."""
import config


def unified_queue_enabled() -> bool:
    return config.TICKET_QUEUE_MODE == "unified"


def unified_queue_code() -> str:
    return config.TICKET_TAKE_QUEUE_COMMON_CODE


UNIFIED_QUEUE_NAME = "Единая очередь"
