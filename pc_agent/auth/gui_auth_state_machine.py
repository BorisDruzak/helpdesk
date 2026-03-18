from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol, Tuple

from loguru import logger


class _AgentProtocol(Protocol):
    auth_token: Optional[str]
    db_manager: object
    identity_manager: object

    def _connection_rejected_flag_path(self) -> Path: ...
    async def request_connection_flow(self, wait_for_approval_seconds: int = 600) -> Tuple[bool, bool]: ...


class GuiAuthState(str, Enum):
    NO_TOKEN = "NoToken"
    REQUEST_SENT = "RequestSent"
    POLLING = "Polling"
    REJECTED = "Rejected"
    TOKEN_READY = "TokenReady"
    WS_CONNECTING = "WsConnecting"


class GuiAuthStateMachine:
    """
    Координирует GUI auth flow в явных состояниях, чтобы избежать гонок
    между request_connection_flow, опросом БД и переходом к WS.
    """

    def __init__(self, agent: _AgentProtocol) -> None:
        self.agent = agent
        self.state = GuiAuthState.NO_TOKEN
        self._connection_task: Optional[asyncio.Task] = None

    def transition(self, new_state: GuiAuthState, reason: str) -> None:
        old_state = self.state
        self.state = new_state
        logger.info(f"[GuiAuthStateMachine] {old_state.value} -> {new_state.value}: {reason}")

    def should_request_connection(self) -> bool:
        flag_path = self.agent._connection_rejected_flag_path()
        if self.agent.auth_token:
            return False
        if flag_path.exists():
            self.transition(GuiAuthState.REJECTED, "rejected flag exists")
            return False
        return True

    def start_connection_flow(self, gui_auth_complete: asyncio.Event) -> None:
        if self._connection_task and not self._connection_task.done():
            return
        self.transition(GuiAuthState.REQUEST_SENT, "starting request_connection_flow")

        async def _run() -> None:
            try:
                ok, rejected = await self.agent.request_connection_flow(wait_for_approval_seconds=600)
                if ok:
                    self.transition(GuiAuthState.TOKEN_READY, "server approved device")
                    gui_auth_complete.set()
                    return
                if rejected:
                    self.transition(GuiAuthState.REJECTED, "server rejected device")
                    flag_path = self.agent._connection_rejected_flag_path()
                    try:
                        flag_path.parent.mkdir(parents=True, exist_ok=True)
                        flag_path.write_text("rejected", encoding="utf-8")
                    except Exception as exc:
                        logger.warning(f"[GuiAuthStateMachine] failed to persist reject flag: {exc}")
                    return
                self.transition(GuiAuthState.POLLING, "request flow ended without token")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.transition(GuiAuthState.POLLING, f"request flow failed: {exc}")

        self._connection_task = asyncio.create_task(_run(), name="gui_auth_state_machine.connection_flow")

    async def wait_for_gui_auth(self, gui_auth_complete: asyncio.Event, timeout_seconds: int = 620) -> None:
        self.transition(GuiAuthState.POLLING, "waiting for GUI auth completion")
        try:
            await asyncio.wait_for(gui_auth_complete.wait(), timeout=timeout_seconds)
            self.transition(GuiAuthState.TOKEN_READY, "GUI auth completion event set")
        except asyncio.TimeoutError:
            logger.warning("[GuiAuthStateMachine] timeout waiting for GUI auth completion")

    async def load_token_from_db(self, retries: int = 10, delay: float = 0.1) -> Optional[str]:
        if not getattr(self.agent, "db_manager", None) or not getattr(self.agent, "identity_manager", None):
            return None
        device_id = getattr(self.agent.identity_manager, "uuid", None)
        if not device_id:
            return None
        for _ in range(max(1, retries)):
            token = await self.agent.db_manager.get_auth_token(device_id)
            if token:
                self.transition(GuiAuthState.TOKEN_READY, "token loaded from DB")
                return token
            await asyncio.sleep(delay)
        return None

    async def cleanup(self) -> None:
        if self._connection_task and not self._connection_task.done():
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass

