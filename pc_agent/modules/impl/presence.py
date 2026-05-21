"""
Privacy-safe workplace presence collector.

The collector reports only coarse endpoint/session state. It does not capture
keystrokes, mouse coordinates, window titles, screenshots, browser history,
URLs, clipboard contents, documents, or messages.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import getpass
import platform
import time
from typing import Any

import psutil

from pc_agent.core.registry import exposed_tool
from pc_agent.modules.base_module import BaseCollector
from shared.builtin_tool_descriptors import (
    PRESENCE_COLLECT_OUTPUT_CONTRACT,
    PRESENCE_COLLECT_OUTPUT_SCHEMA,
    PRESENCE_COLLECT_PRESENTATION_SCHEMA,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_from_epoch(epoch_seconds: float | int | None) -> str:
    if not epoch_seconds:
        return ""
    return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _today_utc() -> str:
    return date.today().isoformat()


class PresenceCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "presence"

    def _warn(self, warnings: list[str], message: str, exc: BaseException | None = None) -> None:
        warnings.append(message if exc is None else f"{message}: {exc}")

    def _agent_uptime_seconds(self) -> int:
        try:
            return max(0, int(time.time() - psutil.Process().create_time()))
        except Exception:
            return 0

    def _current_user(self, warnings: list[str]) -> str:
        try:
            return getpass.getuser()
        except Exception as exc:
            self._warn(warnings, "current session user is unavailable", exc)
            return ""

    def _windows_idle_seconds(self, warnings: list[str]) -> tuple[int | None, str]:
        try:
            import ctypes
            from ctypes import wintypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

            last_input = LASTINPUTINFO()
            last_input.cbSize = ctypes.sizeof(last_input)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
                self._warn(warnings, "Windows last-input state is unavailable")
                return None, ""
            tick_count = ctypes.windll.kernel32.GetTickCount()
            idle_ms = max(0, int(tick_count - last_input.dwTime))
            idle_seconds = idle_ms // 1000
            last_input_at = time.time() - idle_seconds
            return idle_seconds, _iso_from_epoch(last_input_at)
        except Exception as exc:
            self._warn(warnings, "Windows idle state is unavailable", exc)
            return None, ""

    def _collect_session_state(self, warnings: list[str]) -> dict[str, Any]:
        current_user = self._current_user(warnings)
        os_name = platform.system().lower()
        idle_seconds: int | None = None
        last_input_at = ""
        locked = False
        session_state = "unknown"

        if os_name == "windows":
            idle_seconds, last_input_at = self._windows_idle_seconds(warnings)
            if idle_seconds is not None:
                session_state = "idle" if idle_seconds >= 300 else "active"
        elif os_name == "linux":
            self._warn(
                warnings,
                "Linux idle/lock detection is platform-dependent and is not available without a desktop-session helper",
            )
        else:
            self._warn(warnings, "presence session state is not implemented for this OS")

        return {
            "current_user": current_user,
            "session_state": session_state,
            "locked": locked,
            "idle_seconds": int(idle_seconds or 0),
            "last_input_at": last_input_at,
            "session_started_at": "",
        }

    def _today_summary(self, session: dict[str, Any]) -> dict[str, Any]:
        idle_seconds = int(session.get("idle_seconds") or 0)
        state = str(session.get("session_state") or "unknown")
        locked_seconds = idle_seconds if state == "locked" else 0
        active_seconds = 0 if state in {"idle", "locked", "unknown"} else max(0, 300 - idle_seconds)
        return {
            "date": _today_utc(),
            "active_seconds": active_seconds,
            "idle_seconds": idle_seconds if state == "idle" else 0,
            "locked_seconds": locked_seconds,
            "offline_seconds": 0,
            "unknown_seconds": idle_seconds if state == "unknown" else 0,
        }

    @exposed_tool(
        name="collect",
        description="Collect privacy-safe workplace presence and session state",
        risk_level="safe_readonly",
        output_schema=PRESENCE_COLLECT_OUTPUT_SCHEMA,
        output_contract=PRESENCE_COLLECT_OUTPUT_CONTRACT,
        presentation_schema=PRESENCE_COLLECT_PRESENTATION_SCHEMA,
    )
    async def collect(self) -> dict[str, Any]:
        warnings: list[str] = []
        with self.trace_span("tool.entry", details={"tool": "presence.collect"}):
            session = self._collect_session_state(warnings)
            return {
                "schema_version": "1.0",
                "collected_at": _utc_now_iso(),
                "agent": {
                    "online": True,
                    "last_heartbeat_at": _utc_now_iso(),
                    "connection_state": "connected",
                    "agent_uptime_seconds": self._agent_uptime_seconds(),
                },
                "session": session,
                "today": self._today_summary(session),
                "warnings": warnings,
            }
