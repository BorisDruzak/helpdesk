from __future__ import annotations

import json
from typing import Any

import aiohttp
from loguru import logger

from .input_controller import InputController, InputControllerError
from .screen_track import ScreenCaptureTrack


class RemoteAssistWebRTCClient:
    def __init__(
        self,
        *,
        signaling_url: str,
        token: str,
        ice_servers: list[dict[str, Any]] | None = None,
        mode: str = "view_only",
    ):
        self.signaling_url = signaling_url
        self.token = token
        self.ice_servers = ice_servers or []
        self.mode = mode
        self.input_controller = InputController(mode_enabled=mode == "interactive_control")
        self._closed = False
        self._pc = None
        self._ws = None

    async def run(self) -> None:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp

        ice = [
            RTCIceServer(urls=item.get("urls"), username=item.get("username"), credential=item.get("credential"))
            for item in self.ice_servers
            if item.get("urls")
        ]
        self._pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ice))
        self._pc.addTrack(ScreenCaptureTrack.create())

        async with aiohttp.ClientSession() as session:
            ws_url = self._with_query(self.signaling_url, role="agent", token=self.token)
            async with session.ws_connect(ws_url, heartbeat=20, max_msg_size=256 * 1024) as ws:
                self._ws = ws

                @self._pc.on("icecandidate")
                async def on_icecandidate(candidate):
                    if candidate is not None and not self._closed:
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
                        await ws.send_json({"type": "webrtc.connection_state", "payload": {"state": self._pc.connectionState}})

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
                async for msg in ws:
                    if self._closed:
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    message = json.loads(msg.data)
                    message_type = message.get("type")
                    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
                    if message_type == "webrtc.offer":
                        offer = RTCSessionDescription(sdp=payload["sdp"], type=payload["type"])
                        await self._pc.setRemoteDescription(offer)
                        answer = await self._pc.createAnswer()
                        await self._pc.setLocalDescription(answer)
                        await ws.send_json({"type": "webrtc.answer", "payload": {"sdp": self._pc.localDescription.sdp, "type": self._pc.localDescription.type}})
                    elif message_type == "webrtc.ice_candidate" and payload.get("candidate"):
                        candidate_text = str(payload["candidate"])
                        if candidate_text.startswith("candidate:"):
                            candidate_text = candidate_text.split(":", 1)[1]
                        candidate = candidate_from_sdp(candidate_text)
                        candidate.sdpMid = payload.get("sdpMid")
                        candidate.sdpMLineIndex = payload.get("sdpMLineIndex")
                        await self._pc.addIceCandidate(candidate)
                    elif message_type == "session.end":
                        break

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

    @staticmethod
    def _with_query(url: str, **params: str) -> str:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        query.update(params)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
