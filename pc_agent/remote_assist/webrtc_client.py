from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import aiohttp
from loguru import logger

from .input_controller import InputController, InputControllerError
from .screen_track import ScreenCaptureTrack


def count_sdp_candidates(sdp: str | None) -> int:
    if not sdp:
        return 0
    return sum(1 for line in str(sdp).splitlines() if line.startswith("a=candidate:"))


def candidate_summary(candidate: str | None) -> dict[str, str | None]:
    if not candidate:
        return {"type": None, "protocol": None}
    parts = str(candidate).removeprefix("candidate:").split()
    protocol = parts[2].lower() if len(parts) > 2 else None
    candidate_type = None
    if "typ" in parts:
        index = parts.index("typ")
        if index + 1 < len(parts):
            candidate_type = parts[index + 1]
    return {"type": candidate_type, "protocol": protocol}


class RemoteAssistWebRTCClient:
    def __init__(
        self,
        *,
        signaling_url: str,
        token: str,
        ice_servers: list[dict[str, Any]] | None = None,
        mode: str = "view_only",
        connection_timeout_sec: int = 30,
        on_state_change: Callable[[str], None] | None = None,
    ):
        self.signaling_url = signaling_url
        self.token = token
        self.ice_servers = ice_servers or []
        self.mode = mode
        self.connection_timeout_sec = max(5, int(connection_timeout_sec))
        self.on_state_change = on_state_change
        self.input_controller = InputController(mode_enabled=mode == "interactive_control")
        self._closed = False
        self._pc = None
        self._ws = None
        self._failure_message: str | None = None
        self._session_ended = False

    async def run(self) -> None:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp

        logger.info(
            "Remote Assist WebRTC starting: mode={} ice_servers={}",
            self.mode,
            len(self.ice_servers),
        )
        ice = [
            RTCIceServer(urls=item.get("urls"), username=item.get("username"), credential=item.get("credential"))
            for item in self.ice_servers
            if item.get("urls")
        ]
        self._pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ice))
        self._pc.addTrack(ScreenCaptureTrack.create())
        connected_event = asyncio.Event()
        ice_gathering_complete = asyncio.Event()
        timeout_task: asyncio.Task | None = None

        async def fail_and_close(message: str) -> None:
            if self._closed:
                return
            self._failure_message = message
            logger.warning("Remote Assist WebRTC closing as failed: {}", message)
            try:
                if self._ws is not None and not self._ws.closed:
                    await self._ws.send_json({"type": "session.error", "payload": {"error_code": "WEBRTC_FAILED", "error": message}})
            except Exception as exc:
                logger.debug(f"Remote Assist failure signal failed: {exc}")
            await self.stop()

        async def wait_for_connection() -> None:
            try:
                await asyncio.wait_for(connected_event.wait(), timeout=self.connection_timeout_sec)
            except asyncio.TimeoutError:
                await fail_and_close(f"WebRTC connection timeout after {self.connection_timeout_sec}s")

        async with aiohttp.ClientSession() as session:
            ws_url = self._with_query(self.signaling_url, role="agent", token=self.token)
            logger.info("Remote Assist signaling connecting as agent")
            async with session.ws_connect(ws_url, heartbeat=20, max_msg_size=256 * 1024) as ws:
                self._ws = ws
                logger.info("Remote Assist signaling connected as agent")

                @self._pc.on("icecandidate")
                async def on_icecandidate(candidate):
                    if candidate is not None and not self._closed:
                        logger.debug("Remote Assist local ICE candidate gathered")
                        candidate_sdp = candidate.to_sdp()
                        if not candidate_sdp.startswith("candidate:"):
                            candidate_sdp = f"candidate:{candidate_sdp}"
                        await ws.send_json(
                            {
                                "type": "webrtc.ice_candidate",
                                "payload": {
                                    "candidate": candidate_sdp,
                                    "sdpMid": candidate.sdpMid,
                                    "sdpMLineIndex": candidate.sdpMLineIndex,
                                },
                            }
                        )

                @self._pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    if not self._closed:
                        state = self._pc.connectionState
                        logger.info("Remote Assist peer connection state: {}", state)
                        self._emit_state(state)
                        await ws.send_json({"type": "webrtc.connection_state", "payload": {"state": state}})
                        if state in {"connected", "completed"}:
                            connected_event.set()
                        elif state == "failed":
                            await fail_and_close("WebRTC peer connection failed")

                @self._pc.on("iceconnectionstatechange")
                async def on_iceconnectionstatechange():
                    logger.info("Remote Assist ICE connection state: {}", self._pc.iceConnectionState)

                @self._pc.on("icegatheringstatechange")
                async def on_icegatheringstatechange():
                    state = self._pc.iceGatheringState
                    logger.info("Remote Assist ICE gathering state: {}", state)
                    if state == "complete":
                        ice_gathering_complete.set()

                @self._pc.on("datachannel")
                def on_datachannel(channel):
                    if channel.label != "control":
                        logger.warning(f"Remote Assist rejected data channel: label={channel.label}")
                        try:
                            channel.close()
                        except Exception:
                            pass
                        return

                    @channel.on("message")
                    def on_control_message(raw_message):
                        try:
                            if isinstance(raw_message, bytes):
                                raw_message = raw_message.decode("utf-8")
                            message = json.loads(str(raw_message))
                            result = self.input_controller.handle_message(message)
                            channel.send(json.dumps({"type": "control.ack", "payload": result}))
                        except InputControllerError as exc:
                            channel.send(json.dumps({"type": "control.error", "payload": {"error_code": exc.code, "error": exc.message}}))
                        except Exception as exc:
                            logger.exception(f"Remote Assist control message failed: {exc}")
                            channel.send(json.dumps({"type": "control.error", "payload": {"error_code": "CONTROL_FAILED", "error": str(exc)}}))

                await ws.send_json({"type": "session.ready", "payload": {"role": "agent", "mode": self.mode}})
                self._emit_state("signaling_connected")
                async for msg in ws:
                    if self._closed:
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    message = json.loads(msg.data)
                    message_type = message.get("type")
                    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
                    if message_type == "webrtc.offer":
                        logger.info("Remote Assist offer received")
                        offer = RTCSessionDescription(sdp=payload["sdp"], type=payload["type"])
                        await self._pc.setRemoteDescription(offer)
                        answer = await self._pc.createAnswer()
                        await self._pc.setLocalDescription(answer)
                        if self._pc.iceGatheringState == "complete":
                            ice_gathering_complete.set()
                        try:
                            await asyncio.wait_for(ice_gathering_complete.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Remote Assist ICE gathering timed out before answer: local_candidates={}",
                                count_sdp_candidates(self._pc.localDescription.sdp if self._pc.localDescription else None),
                            )
                        await ws.send_json({"type": "webrtc.answer", "payload": {"sdp": self._pc.localDescription.sdp, "type": self._pc.localDescription.type}})
                        logger.info(
                            "Remote Assist answer sent: local_candidates={}",
                            count_sdp_candidates(self._pc.localDescription.sdp if self._pc.localDescription else None),
                        )
                        if timeout_task is None or timeout_task.done():
                            timeout_task = asyncio.create_task(wait_for_connection())
                    elif message_type == "webrtc.ice_candidate" and payload.get("candidate"):
                        summary = candidate_summary(str(payload.get("candidate") or ""))
                        logger.info(
                            "Remote Assist remote ICE candidate received: type={} protocol={}",
                            summary["type"],
                            summary["protocol"],
                        )
                        candidate_text = str(payload["candidate"])
                        if candidate_text.startswith("candidate:"):
                            candidate_text = candidate_text.split(":", 1)[1]
                        candidate = candidate_from_sdp(candidate_text)
                        candidate.sdpMid = payload.get("sdpMid")
                        candidate.sdpMLineIndex = payload.get("sdpMLineIndex")
                        await self._pc.addIceCandidate(candidate)
                    elif message_type == "session.end":
                        self._session_ended = True
                        break
                    elif message_type == "session.error":
                        logger.warning("Remote Assist signaling error from peer: {}", payload)
                        if not self._failure_message:
                            self._failure_message = str(payload.get("error") or payload.get("error_code") or "Remote Assist signaling error")
                        break
        if timeout_task is not None:
            timeout_task.cancel()
        if self._failure_message and not self._session_ended:
            raise RuntimeError(self._failure_message)

    async def stop(self) -> None:
        self._closed = True
        try:
            if self._ws is not None:
                await self._ws.close()
        except Exception as exc:
            logger.debug(f"Remote Assist signaling close failed: {exc}")
        try:
            if self._pc is not None:
                await self._pc.close()
        except Exception as exc:
            logger.debug(f"Remote Assist peer close failed: {exc}")

    def _emit_state(self, state: str) -> None:
        if self.on_state_change is None:
            return
        try:
            self.on_state_change(state)
        except Exception as exc:
            logger.debug(f"Remote Assist state callback failed: {exc}")

    @staticmethod
    def _with_query(url: str, **params: str) -> str:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        query.update(params)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
