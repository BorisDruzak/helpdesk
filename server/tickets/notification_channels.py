"""External notification channel provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ExternalDeliveryResult:
    status: str = "sent"
    provider_message_id: str | None = None
    detail: str | None = None


class ExternalNotificationProvider(Protocol):
    async def send(
        self,
        *,
        channel: str,
        actor_id: str,
        ticket_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> ExternalDeliveryResult | dict[str, Any] | bool | None:
        """Send one external notification.

        Implementations are intentionally pluggable: production email/Telegram/VK
        providers can live outside the ticket runtime, while tests inject fakes.
        """


def normalize_delivery_result(value: ExternalDeliveryResult | dict[str, Any] | bool | None) -> dict[str, Any]:
    if isinstance(value, ExternalDeliveryResult):
        return {
            "delivery_status": value.status or "sent",
            "provider_message_id": value.provider_message_id,
            "detail": value.detail,
        }
    if isinstance(value, dict):
        status = str(value.get("delivery_status") or value.get("status") or "sent")
        return {
            "delivery_status": status,
            "provider_message_id": value.get("provider_message_id") or value.get("message_id"),
            "detail": value.get("detail"),
        }
    if value is False:
        return {"delivery_status": "skipped", "provider_message_id": None, "detail": None}
    return {"delivery_status": "sent", "provider_message_id": None, "detail": None}
