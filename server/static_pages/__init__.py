"""
Static Pages module - обработка HTML страниц.
"""

from .handlers import (
    handle_index,
    handle_admin_page,
    handle_login_page,
    handle_support_page,
    handle_ticket_page,
    handle_ticket_page_by_id,
)

__all__ = [
    'handle_index',
    'handle_admin_page',
    'handle_login_page',
    'handle_support_page',
    'handle_ticket_page',
    'handle_ticket_page_by_id'
]
