from __future__ import annotations

from typing import Any, Dict

from app.db import get_session
from app.repos.remote_access_repo import RemoteAccessRepo
from diagnostics.capability_models import CapabilityDescriptor
from diagnostics.evidence import normalize_tool_result_to_evidence_stub
from remote_assist.service import RemoteAssistError, RemoteAssistService, remote_session_to_dict


def _actor_id(actor: Any) -> str:
    return str(getattr(actor, "actor_id", None) or "system")


class RemoteAssistCapabilityProvider:
    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        if capability.id == "remote_assist.session.summary":
            return await self._session_summary(capability, **kwargs)
        return await self._request_session(capability, **kwargs)

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
        mode = str(params.get("mode") or "view_only").strip() or "view_only"
        async with get_session() as session:
            service = RemoteAssistService(session)
            try:
                remote_session = await service.request_session(
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
                command_id = await service.send_request_to_agent(state=state, remote_session=remote_session)
                await session.commit()
            except RemoteAssistError as exc:
                await session.rollback()
                return {
                    "status": "error",
                    "error_code": exc.error_code,
                    "capability_id": capability.id,
                    "message": exc.message,
                }
        payload = remote_session_to_dict(remote_session)
        result = {
            "status": "created",
            "capability_id": capability.id,
            "session_id": remote_session.id,
            "command_id": command_id,
            "output": payload,
            "summary": f"Remote Assist session requested: {remote_session.mode}",
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"remote_assist:{remote_session.id}", "status": "created"},
            capability,
            result,
        ).to_dict()
        return result

    async def _session_summary(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        if not ticket_id:
            return {
                "status": "error",
                "error_code": "TICKET_ID_REQUIRED",
                "capability_id": capability.id,
                "message": "ticket_id is required",
            }
        async with get_session() as session:
            sessions = await RemoteAccessRepo(session).list_for_ticket(ticket_id, limit=20)
            output = {"ticket_id": ticket_id, "sessions": [remote_session_to_dict(item) for item in sessions]}
            await session.commit()
        result = {
            "status": "success",
            "capability_id": capability.id,
            "ticket_id": ticket_id,
            "output": output,
            "summary": f"Remote Assist sessions: {len(output['sessions'])}",
        }
        result["evidence_preview"] = normalize_tool_result_to_evidence_stub(
            {"operation_id": f"remote_assist_summary:{ticket_id}", "status": "succeeded"},
            capability,
            result,
        ).to_dict()
        return result
