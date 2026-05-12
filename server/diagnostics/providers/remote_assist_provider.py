from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from app.db import get_session
from app.repos.remote_access_repo import RemoteAccessRepo
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from remote_assist.service import RemoteAssistError, RemoteAssistService, remote_session_to_dict


def _actor_id(actor: Any) -> str:
    return str(getattr(actor, "actor_id", None) or "system")


SessionRequester = Callable[..., Awaitable[Any]]
RequestSender = Callable[..., Awaitable[str]]
SessionsLoader = Callable[[str, int], Awaitable[list[Any]]]

REQUEST_MODES = {
    "remote_assist.request_view": "view_only",
    "remote_assist.request_control": "interactive_control",
}
ACTIVE_STATUSES = {"requested", "waiting_consent", "approved", "starting", "active"}
OK_STATUSES = {"ended"}
WARNING_STATUSES = {"requested", "waiting_consent", "approved", "starting", "active", "denied", "expired", "canceled"}
ERROR_STATUSES = {"failed"}


class RemoteAssistCapabilityProvider:
    def __init__(
        self,
        *,
        session_requester: Optional[SessionRequester] = None,
        request_sender: Optional[RequestSender] = None,
        sessions_loader: Optional[SessionsLoader] = None,
    ) -> None:
        self.session_requester = session_requester
        self.request_sender = request_sender
        self.sessions_loader = sessions_loader or self._load_sessions

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        if capability.id == "remote_assist.session.summary":
            return await self._session_summary(capability, **kwargs)
        if capability.id in REQUEST_MODES:
            return await self._request_session(capability, **kwargs)
        return {
            "status": "unsupported",
            "error_code": "CAPABILITY_TARGET_UNSUPPORTED",
            "message": f"Remote Assist capability '{capability.id}' is not implemented",
            "capability_id": capability.id,
            "ticket_id": str(kwargs.get("ticket_id") or "").strip() or None,
            "device_id": str(kwargs.get("device_id") or "").strip() or None,
        }

    async def _request_session(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        device_id = str(kwargs.get("device_id") or "").strip()
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        state = kwargs.get("state")
        actor = kwargs.get("actor")
        if not ticket_id or not device_id:
            return {
                "status": "error",
                "error_code": "TICKET_AND_DEVICE_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id and device_id are required",
            }
        mode = REQUEST_MODES[capability.id]
        if self.session_requester is None:
            try:
                remote_session, command_id = await self._request_and_send_with_service(
                    state=state,
                    ticket_id=ticket_id,
                    device_id=device_id,
                    operator_id=_actor_id(actor),
                    requester_id=params.get("requester_id"),
                    mode=mode,
                    reason=params.get("reason"),
                    duration_minutes=params.get("duration_minutes"),
                    media_options=params.get("media") if isinstance(params.get("media"), dict) else None,
                    feature_options=params.get("features") if isinstance(params.get("features"), dict) else None,
                )
            except RemoteAssistError as exc:
                return {
                    "status": "error",
                    "error_code": exc.error_code,
                    "capability_id": capability.id,
                    "message": exc.message,
                }
        else:
            try:
                remote_session = await self.session_requester(
                    state=state,
                    ticket_id=ticket_id,
                    device_id=device_id,
                    operator_id=_actor_id(actor),
                    requester_id=params.get("requester_id"),
                    mode=mode,
                    reason=params.get("reason"),
                    duration_minutes=params.get("duration_minutes"),
                    media_options=params.get("media") if isinstance(params.get("media"), dict) else None,
                    feature_options=params.get("features") if isinstance(params.get("features"), dict) else None,
                )
                command_id = await self._send_request(remote_session, state=state)
            except RemoteAssistError as exc:
                return {
                    "status": "error",
                    "error_code": exc.error_code,
                    "capability_id": capability.id,
                    "message": exc.message,
                }
        payload = remote_session_to_dict(remote_session)
        diagnostic_status = self._status_from_session(remote_session)
        result = {
            "status": "created",
            "diagnostic_status": diagnostic_status,
            "capability_id": capability.id,
            "session_id": remote_session.id,
            "command_id": command_id,
            "output": payload,
            "summary": f"Remote Assist session requested: {remote_session.mode}",
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"remote_assist:{remote_session.id}", "status": diagnostic_status},
            capability,
            {"status": diagnostic_status, "summary": result["summary"], "output": result["output"]},
        ).to_dict()
        return result

    async def _request_and_send_with_service(self, **kwargs: Any) -> tuple[Any, str]:
        async with get_session() as session:
            service = RemoteAssistService(session)
            try:
                remote_session = await service.request_session(**kwargs)
                command_id = await service.send_request_to_agent(state=kwargs.get("state"), remote_session=remote_session)
                await session.commit()
                return remote_session, command_id
            except RemoteAssistError:
                await session.rollback()
                raise
            except Exception as exc:
                await session.rollback()
                raise RemoteAssistError("REMOTE_ASSIST_REQUEST_FAILED", "Remote Assist request failed") from exc

    async def _send_request(self, remote_session: Any, **kwargs: Any) -> str:
        if self.request_sender is not None:
            return await self.request_sender(remote_session, **kwargs)
        async with get_session() as session:
            service = RemoteAssistService(session)
            command_id = await service.send_request_to_agent(state=kwargs.get("state"), remote_session=remote_session)
            await session.commit()
            return command_id

    async def _session_summary(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        sessions = await self.sessions_loader(ticket_id, self._limit(params.get("limit"), default=20))
        output = self._summary_output(ticket_id, sessions)
        diagnostic_status = self._status_from_summary(output)
        result = {
            "status": "success",
            "diagnostic_status": diagnostic_status,
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "output": output,
            "summary": f"Remote Assist sessions: {output['counts']['total']} total, {output['counts']['active']} active",
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"remote_assist_summary:{ticket_id}", "status": diagnostic_status},
            capability,
            {"status": diagnostic_status, "summary": result["summary"], "output": result["output"]},
        ).to_dict()
        return result

    async def _load_sessions(self, ticket_id: str, limit: int) -> list[Any]:
        async with get_session() as session:
            sessions = await RemoteAccessRepo(session).list_for_ticket(ticket_id, limit=limit)
            await session.commit()
            return sessions

    def _summary_output(self, ticket_id: str, sessions: list[Any]) -> Dict[str, Any]:
        serialized = [remote_session_to_dict(item) for item in sessions]
        counts = {
            "total": len(sessions),
            "active": sum(1 for item in sessions if str(getattr(item, "status", "") or "") in ACTIVE_STATUSES),
            "completed": sum(1 for item in sessions if str(getattr(item, "status", "") or "") in OK_STATUSES),
            "denied": sum(1 for item in sessions if str(getattr(item, "status", "") or "") == "denied"),
            "failed": sum(1 for item in sessions if str(getattr(item, "status", "") or "") in ERROR_STATUSES),
        }
        return {
            "ticket_id": ticket_id,
            "counts": counts,
            "latest_session": serialized[0] if serialized else None,
            "active_sessions": [
                item for item, raw in zip(serialized, sessions) if str(getattr(raw, "status", "") or "") in ACTIVE_STATUSES
            ],
            "sessions": serialized,
        }

    def _status_from_summary(self, output: Dict[str, Any]) -> str:
        counts = output.get("counts") if isinstance(output.get("counts"), dict) else {}
        if int(counts.get("failed") or 0) > 0:
            return "error"
        if int(counts.get("active") or 0) > 0 or int(counts.get("denied") or 0) > 0:
            return "warning"
        if int(counts.get("completed") or 0) > 0:
            return "ok"
        return "unknown"

    def _status_from_session(self, session: Any) -> str:
        status = str(getattr(session, "status", "") or "").strip().lower()
        if status in ERROR_STATUSES:
            return "error"
        if status in WARNING_STATUSES:
            return "warning"
        if status in OK_STATUSES:
            return "ok"
        return "unknown"

    def _limit(self, raw: Any, *, default: int) -> int:
        try:
            return max(1, min(int(raw), 50))
        except (TypeError, ValueError):
            return default
