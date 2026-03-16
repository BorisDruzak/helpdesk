"""
Сервис проверки доступа к артефактам (скриншоты, запись экрана).

Проверка прав: агент — по device_id; UI — по привязке артефакта к тикету.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext, AuthType
from app.db.models import Artifact
from app.repos.artifacts_repo import ArtifactsRepo
from app.repos.ticket_events_repo import TicketEventsRepo


# Коды причины недоступности артефакта (для выбора 404/410/403)
NOT_FOUND = "not_found"
EXPIRED = "expired"
FORBIDDEN = "forbidden"


class ArtifactService:
    """
    Проверка доступа к артефактам для скачивания.

    - Агент (AGENT_TOKEN): доступ только к своим артефактам (artifact.device_id == actor_id).
    - UI (UI_TOKEN): доступ к артефактам, привязанным к тикету (ticket существует).
      Артефакты без ticket_id для UI недоступны.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._artifacts_repo = ArtifactsRepo(session)
        self._ticket_repo = TicketEventsRepo(session)

    async def get_artifact_for_download(
        self,
        artifact_id: str,
        auth_context: AuthContext,
        ticket_id_from_request: Optional[str] = None,
    ) -> Tuple[Optional[Artifact], Optional[str]]:
        """
        Возвращает артефакт и причину отказа (если доступ запрещён).

        ticket_id_from_request: опционально переданный из запроса ticket_id (для артефактов без ticket_id в БД — проверка по событиям тикета).

        Returns:
            (artifact, None) — доступ разрешён.
            (None, NOT_FOUND) — артефакт не найден (404).
            (None, EXPIRED) — TTL истёк (410).
            (None, FORBIDDEN) — нет прав (403).
        """
        artifact = await self._artifacts_repo.get_by_id(artifact_id)
        if not artifact:
            return None, NOT_FOUND

        now = datetime.now(timezone.utc)
        if artifact.expires_at is not None and artifact.expires_at < now:
            return None, EXPIRED

        if auth_context.auth_type == AuthType.AGENT_TOKEN:
            if artifact.device_id != auth_context.actor_id:
                return None, FORBIDDEN
            return artifact, None

        if auth_context.auth_type == AuthType.UI_TOKEN:
            if artifact.ticket_id:
                ticket = await self._ticket_repo.get_ticket(artifact.ticket_id)
                if not ticket:
                    logger.warning(
                        f"[ArtifactService] FORBIDDEN: artifact {artifact_id} has ticket_id={artifact.ticket_id} but ticket not found"
                    )
                    return None, FORBIDDEN
                return artifact, None
            # Артефакт без ticket_id (старые загрузки): разрешаем, если передан ticket_id и тикет содержит этот артефакт в событиях
            if ticket_id_from_request:
                ticket = await self._ticket_repo.get_ticket(ticket_id_from_request)
                if not ticket:
                    logger.warning(
                        f"[ArtifactService] FORBIDDEN: ticket_id_from_request={ticket_id_from_request!r} not found"
                    )
                    return None, FORBIDDEN
                contains = await self._ticket_repo.ticket_contains_artifact(ticket_id_from_request, artifact_id)
                if contains:
                    return artifact, None
                logger.warning(
                    f"[ArtifactService] FORBIDDEN: artifact {artifact_id} not found in ticket_events for ticket_id={ticket_id_from_request!r}"
                )
            else:
                logger.warning(
                    f"[ArtifactService] FORBIDDEN: UI access to artifact {artifact_id} without ticket_id in DB and no ticket_id in request"
                )
            return None, FORBIDDEN

        return None, FORBIDDEN
