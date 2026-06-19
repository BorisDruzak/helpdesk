"""Default Service Catalog entries and fallback projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


FALLBACK_SERVICE_CODE = "other"
FALLBACK_OFFERING_CODE = "unknown"
FALLBACK_FULL_CODE = "other.unknown"
FALLBACK_TEMPLATE_KEY = "general_request"

DEFAULT_SERVICE_CATALOG_SERVICES: tuple[dict[str, Any], ...] = (
    {
        "code": "workplace",
        "public_title": "Рабочее место",
        "short_description": "Ноутбук, ПК, монитор, периферия",
        "visibility": "public",
        "business_criticality": "medium",
        "reporting_category": "end_user_computing",
        "sort_order": 10,
    },
    {
        "code": "access",
        "public_title": "Доступы",
        "short_description": "Учетные записи, роли, права доступа",
        "visibility": "public",
        "business_criticality": "medium",
        "reporting_category": "identity_access",
        "sort_order": 20,
    },
    {
        "code": "network",
        "public_title": "Сеть",
        "short_description": "Wi-Fi, интернет, VPN",
        "visibility": "public",
        "business_criticality": "high",
        "reporting_category": "connectivity",
        "sort_order": 30,
    },
    {
        "code": "mail",
        "public_title": "Почта",
        "short_description": "Почтовые ящики, Outlook, рассылки",
        "visibility": "public",
        "business_criticality": "medium",
        "reporting_category": "communications",
        "sort_order": 40,
    },
    {
        "code": "requester_setup",
        "public_title": "Настройка кабинета",
        "short_description": "Профиль пользователя, устройства и первичная привязка",
        "visibility": "public",
        "business_criticality": "medium",
        "reporting_category": "requester_setup",
        "sort_order": 50,
    },
    {
        "code": FALLBACK_SERVICE_CODE,
        "public_title": "Другое / Не знаю",
        "short_description": "Если вы не знаете, к какой услуге отнести обращение",
        "visibility": "public",
        "business_criticality": "medium",
        "reporting_category": "uncategorized",
        "sort_order": 999,
    },
)

DEFAULT_SERVICE_CATALOG_OFFERINGS: tuple[dict[str, Any], ...] = (
    {
        "service_code": "workplace",
        "code": "laptop_broken",
        "public_title": "Сломался ноутбук",
        "short_description": "Ноутбук не включается или работает нестабильно",
        "request_type": "incident",
        "request_template_key": "breakage",
        "visibility": "public",
        "reporting_category": "workplace_incidents",
        "sort_order": 10,
    },
    {
        "service_code": "workplace",
        "code": "software_install",
        "public_title": "Установить ПО",
        "short_description": "Установка или обновление программного обеспечения",
        "request_type": "service_request",
        "request_template_key": "software_install",
        "visibility": "public",
        "reporting_category": "software",
        "sort_order": 20,
    },
    {
        "service_code": "workplace",
        "code": "printer_issue",
        "public_title": "Проблема с принтером",
        "short_description": "Печать, очередь, сканирование или неисправность принтера",
        "request_type": "incident",
        "request_template_key": "printer",
        "visibility": "public",
        "reporting_category": "printing",
        "sort_order": 30,
    },
    {
        "service_code": "access",
        "code": "grant_access",
        "public_title": "Выдать доступ",
        "short_description": "Нужны права, роль или доступ к системе",
        "request_type": "access_request",
        "request_template_key": "access",
        "visibility": "public",
        "reporting_category": "identity_access",
        "sort_order": 10,
    },
    {
        "service_code": "access",
        "code": "reset_password",
        "public_title": "Сбросить пароль",
        "short_description": "Не получается войти или восстановить учетную запись",
        "request_type": "access_request",
        "request_template_key": "access",
        "visibility": "public",
        "reporting_category": "identity_access",
        "sort_order": 20,
    },
    {
        "service_code": "network",
        "code": "vpn_issue",
        "public_title": "VPN не подключается",
        "short_description": "Проблемы с VPN или удаленным доступом",
        "request_type": "incident",
        "request_template_key": "network",
        "visibility": "public",
        "reporting_category": "connectivity",
        "sort_order": 10,
    },
    {
        "service_code": "network",
        "code": "internet_issue",
        "public_title": "Нет интернета",
        "short_description": "Нет сети, Wi-Fi или доступа к интернету",
        "request_type": "incident",
        "request_template_key": "network",
        "visibility": "public",
        "reporting_category": "connectivity",
        "sort_order": 20,
    },
    {
        "service_code": "mail",
        "code": "mailbox_issue",
        "public_title": "Проблема с почтой",
        "short_description": "Не приходит, не отправляется или неправильно работает почта",
        "request_type": "incident",
        "request_template_key": "mail_issue",
        "visibility": "public",
        "reporting_category": "communications",
        "sort_order": 10,
    },
    {
        "service_code": "requester_setup",
        "code": "profile_completion_help",
        "public_title": "Помощь с заполнением профиля",
        "short_description": "Заявка на помощь с обязательными полями профиля пользователя",
        "request_type": "service_request",
        "request_template_key": "profile_completion_help",
        "visibility": "public",
        "reporting_category": "requester_setup",
        "sort_order": 960,
    },
    {
        "service_code": "requester_setup",
        "code": "agent_binding_help",
        "public_title": "Помощь с привязкой устройства",
        "short_description": "Заявка на помощь с привязкой устройства или агента к аккаунту",
        "request_type": "service_request",
        "request_template_key": "agent_binding_help",
        "visibility": "public",
        "reporting_category": "requester_setup",
        "sort_order": 970,
    },
    {
        "service_code": FALLBACK_SERVICE_CODE,
        "code": FALLBACK_OFFERING_CODE,
        "public_title": "Не знаю, куда отнести обращение",
        "short_description": "Поддержка уточнит категорию после получения обращения",
        "request_type": "service_request",
        "request_template_key": FALLBACK_TEMPLATE_KEY,
        "visibility": "public",
        "reporting_category": "uncategorized",
        "sort_order": 999,
    },
)


def fallback_service_dict() -> dict[str, Any]:
    return deepcopy(next(item for item in DEFAULT_SERVICE_CATALOG_SERVICES if item["code"] == FALLBACK_SERVICE_CODE))


def fallback_offering_dict() -> dict[str, Any]:
    offering = deepcopy(
        next(
            item
            for item in DEFAULT_SERVICE_CATALOG_OFFERINGS
            if item["service_code"] == FALLBACK_SERVICE_CODE
            and item["code"] == FALLBACK_OFFERING_CODE
        )
    )
    offering["full_code"] = FALLBACK_FULL_CODE
    return offering
