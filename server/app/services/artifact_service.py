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

    - Агент (AGENT_TOKEN): базово только свои артефакты (artifact.device_id == actor_id);
      ticket-bound downloads are additionally scoped by active device binding in uploads.handlers.
    - Staff UI: доступ к артефактам, привязанным к существующему тикету.
    - User UI / public ticket token: только свой тикет.
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

        if auth_context.auth_type in {AuthType.UI_TOKEN, AuthType.PUBLIC_TICKET_TOKEN}:
            target_ticket_id = artifact.ticket_id or ticket_id_from_request
            if not target_ticket_id:
                logger.warning(
                    f"[ArtifactService] FORBIDDEN: UI/public access to artifact {artifact_id} without ticket binding"
                )
                return None, FORBIDDEN
            ticket = await self._ticket_repo.get_ticket(target_ticket_id)
            if not ticket:
                logger.warning(
                    f"[ArtifactService] FORBIDDEN: artifact {artifact_id} ticket_id={target_ticket_id} not found"
                )
                return None, FORBIDDEN
            if artifact.ticket_id != target_ticket_id:
                contains = await self._ticket_repo.ticket_contains_artifact(target_ticket_id, artifact_id)
                if not contains:
                    logger.warning(
                        f"[ArtifactService] FORBIDDEN: artifact {artifact_id} not found in ticket_events for ticket_id={target_ticket_id!r}"
                    )
                    return None, FORBIDDEN
            if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
                return (artifact, None) if auth_context.ticket_scope == target_ticket_id else (None, FORBIDDEN)
            if auth_context.actor_role in {"admin", "support", "auditor"}:
                return artifact, None
            if auth_context.actor_role == "user" and auth_context.actor_id == getattr(ticket, "requester_id", None):
                return artifact, None
            logger.warning(
                f"[ArtifactService] FORBIDDEN: actor_role={auth_context.actor_role} cannot download artifact {artifact_id}"
            )
            return None, FORBIDDEN

        return None, FORBIDDEN
