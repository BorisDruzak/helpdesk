from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from pc_agent.core import runtime_paths
from pc_agent.core.action_trace import get_action_trace_recorder
from pc_agent.core.runtime_logging import read_log_tail, format_log_tail

from .main_window import MainWindow
from .tray_manager import TrayManager


class GuiAutomationController:
    """Local automation surface for repeatable GUI/runtime testing."""

    def __init__(
        self,
        window: MainWindow,
        *,
        tray_manager: Optional[TrayManager] = None,
        request_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.window = window
        self.tray_manager = tray_manager
        self.request_exit = request_exit

    async def get_status(self) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        current_widget = self.window.main_content_stack.currentWidget()
        return {
            "window_visible": self.window.isVisible(),
            "window_minimized": self.window.isMinimized(),
            "window_active": self.window.isActiveWindow(),
            "sidebar_view": getattr(self.window, "_active_sidebar_view", "unknown"),
            "content_view": self._content_view_name(current_widget),
            "bridge_connected": bool(getattr(self.window, "_bridge_connected", False)),
            "connection_state": str(getattr(self.window, "_server_connection_state", "unknown")),
            "connection_detail": str(getattr(self.window, "_server_connection_detail", "")),
            "tray_available": bool(self.tray_manager and self.tray_manager.available),
            "has_active_profile": chat_panel.has_active_profile(),
            "active_profile_id": chat_panel._profiles_data.get("active_profile_id"),
            "profile_count": len(chat_panel._profiles()),
            "active_ticket_id": chat_panel.active_ticket_id,
            "ticket_count": len(chat_panel.tickets_cache),
            "ticket_ids": [
                str((row.get("ticket", row) or {}).get("ticket_id") or "")
                for row in chat_panel.tickets_cache[:20]
                if isinstance(row, dict)
            ],
            "form_pack_version": str((chat_panel.ticket_form_pack() or {}).get("version") or ""),
        }

    async def run_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("automation payload must be an object")

        action = str(payload.get("action") or "").strip().lower()
        if not action:
            raise ValueError("automation action is required")

        action_id = str(payload.get("action_id") or uuid.uuid4())
        trace = get_action_trace_recorder().context(
            source="gui_automation",
            action=action,
            category=action.split(".", 1)[0] or "automation",
            action_id=action_id,
            ticket_id=payload.get("ticket_id"),
            tool_name=payload.get("tool_name"),
        )
        get_action_trace_recorder().record(
            trace,
            stage="start",
            status="started",
            summary=f"automation {action}",
            details={"payload": payload},
        )

        logger.info(f"[ui-automation] action={action} action_id={action_id}")

        try:
            if action == "window.show":
                self._show_window()
                result = await self._result(action)
            elif action == "window.hide":
                self.window.hide()
                result = await self._result(action)
            elif action == "window.close":
                self.window.close()
                await asyncio.sleep(0.05)
                result = await self._result(action)
            elif action == "window.activate":
                self._show_window()
                result = await self._result(action)
            elif action == "window.minimize":
                self.window.showMinimized()
                result = await self._result(action)
            elif action == "window.exit":
                if not self.request_exit:
                    raise ValueError("window exit automation is not configured")
                self.request_exit()
                await asyncio.sleep(0.05)
                result = await self._result(action)
            elif action == "sidebar.select":
                view_name = str(payload.get("view") or "").strip().lower()
                if view_name not in {"tickets", "profile", "settings"}:
                    raise ValueError("sidebar.select requires view=tickets|profile|settings")
                self.window._select_sidebar_view(view_name, expand=bool(payload.get("expand", True)))
                result = await self._result(action, view=view_name)
            elif action == "profile.upsert":
                profile_result = self._upsert_profile(payload)
                self.window._render_profile_status()
                result = await self._result(action, **profile_result)
            elif action == "profile.select":
                profile_id = str(payload.get("profile_id") or "").strip()
                if not profile_id:
                    raise ValueError("profile.select requires profile_id")
                self._select_profile(profile_id)
                self.window._render_profile_status()
                result = await self._result(action, profile_id=profile_id)
            elif action == "ticket.form_pack.refresh":
                await self.window.chat_panel._async_refresh_ticket_form_pack(force=bool(payload.get("force", True)))
                result = await self._result(
                    action,
                    form_pack_version=str((self.window.chat_panel.ticket_form_pack() or {}).get("version") or ""),
                )
            elif action == "ticket.list.refresh":
                await self.window.chat_panel._async_refresh_ticket_list()
                result = await self._result(action, ticket_count=len(self.window.chat_panel.tickets_cache))
            elif action == "ticket.create":
                result = await self._create_ticket(payload, trace_parent_action_id=action_id)
            elif action == "ticket.open":
                result = await self._open_ticket(payload)
            elif action == "ticket.tool.run":
                result = await self._run_ticket_tool(payload, trace_parent_action_id=action_id)
            elif action == "ticket.message.send":
                result = await self._send_message(payload, trace_parent_action_id=action_id)
            elif action == "ticket.capture_screenshot":
                tool_payload = dict(payload)
                tool_payload["tool_name"] = "screen.collect"
                result = await self._run_ticket_tool(tool_payload, trace_parent_action_id=action_id)
            elif action == "ticket.capture_video":
                tool_payload = dict(payload)
                tool_payload["tool_name"] = "screen.record"
                tool_payload.setdefault("params", {"duration_sec": int(payload.get("duration_sec") or 60)})
                result = await self._run_ticket_tool(tool_payload, trace_parent_action_id=action_id)
            elif action == "ticket.attach_files":
                result = await self._attach_files(payload, trace_parent_action_id=action_id)
            elif action == "ticket.confirm_resolution":
                result = await self._confirm_resolution(payload, trace_parent_action_id=action_id)
            elif action == "ticket.snapshot":
                result = await self._ticket_snapshot(payload, trace_parent_action_id=action_id)
            elif action == "logs.collect":
                result = await self._collect_logs(payload, trace_parent_action_id=action_id)
            elif action == "event.inject":
                event = payload.get("event")
                if not isinstance(event, dict):
                    raise ValueError("event.inject requires event object")
                self.window.handle_event(event)
                result = await self._result(action, event_type=event.get("event_type") or event.get("event"))
            elif action == "runtime.refresh":
                runtime = await self.window._async_refresh_runtime_snapshot(update_panel=bool(payload.get("update_panel", False)))
                result = await self._result(action, runtime=runtime)
            else:
                raise ValueError(f"unsupported automation action: {action}")

            get_action_trace_recorder().record(
                trace,
                stage="finish",
                status="ok",
                summary=f"automation {action} completed",
                details={"result": result},
            )
            if isinstance(result, dict):
                result.setdefault("action_id", action_id)
            return result
        except Exception as exc:
            get_action_trace_recorder().record(
                trace,
                stage="finish",
                status="error",
                summary=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            raise

    async def _create_ticket(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        if not chat_panel.has_active_profile():
            raise ValueError("active requester profile is required before ticket.create")

        description = str(payload.get("description") or "").strip()
        if not description:
            raise ValueError("ticket.create requires description")

        form_payload = payload.get("form_payload")
        if form_payload is not None and not isinstance(form_payload, dict):
            raise ValueError("ticket.create form_payload must be an object")
        attachment_paths = [str(item) for item in (payload.get("attachment_paths") or []) if str(item).strip()]

        await chat_panel._async_refresh_ticket_form_pack(force=bool(payload.get("refresh_form_pack", True)))

        requester_profile, display_name = chat_panel._current_requester_payload()
        account_session = chat_panel._current_account_session()
        result = await chat_panel.ticket_client.create_ticket(
            description=description,
            title=str(payload.get("title") or "Support Request"),
            tags=list(payload.get("tags") or []),
            requester_profile=requester_profile,
            user_display_name=display_name,
            urgency=bool(payload.get("urgency")),
            importance=bool(payload.get("importance")),
            urgency_reason=payload.get("urgency_reason"),
            importance_reason=payload.get("importance_reason"),
            form_key=payload.get("form_key"),
            form_pack_key=payload.get("form_pack_key"),
            form_pack_version=payload.get("form_pack_version"),
            form_payload=form_payload,
            ticket_type=payload.get("ticket_type"),
            requester_account=account_session,
            trace_parent_action_id=trace_parent_action_id,
        )
        if result.get("status") != "ok":
            raise RuntimeError(json.dumps(result, ensure_ascii=False))

        ticket = result.get("ticket", {}) if isinstance(result.get("ticket"), dict) else {}
        ticket_id = str(ticket.get("ticket_id") or "")
        if not ticket_id:
            raise RuntimeError("ticket.create did not return ticket_id")
        if attachment_paths:
            await chat_panel._async_send_created_ticket_attachments(ticket_id, attachment_paths, trace_parent_action_id=trace_parent_action_id)

        chat_panel.active_ticket_id = ticket_id
        chat_panel._last_timeline_html = None
        chat_panel._last_detail_header_sig = None
        chat_panel._pending_ticket_snapshot = None
        chat_panel._reset_active_ticket_cache()
        chat_panel._ticket_detail_timer.start(chat_panel._ticket_detail_timer.interval())
        await chat_panel._async_refresh_ticket_list()
        await chat_panel._async_refresh_ticket_detail()
        chat_panel._show_chat_screen()
        chat_panel._ensure_timeline_bottom_follow()
        self.window._select_sidebar_view("tickets", expand=True)

        return await self._result(
            "ticket.create",
            ticket=ticket,
            ticket_id=ticket_id,
            public_access_code=result.get("public_access_code"),
            public_access_url=result.get("public_access_url"),
        )

    async def _open_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or "").strip()
        if not ticket_id:
            raise ValueError("ticket.open requires ticket_id")

        if not any(str((row.get("ticket", row) or {}).get("ticket_id") or "") == ticket_id for row in chat_panel.tickets_cache if isinstance(row, dict)):
            await chat_panel._async_refresh_ticket_list()

        chat_panel.active_ticket_id = ticket_id
        chat_panel._last_timeline_html = None
        chat_panel._last_detail_header_sig = None
        chat_panel._pending_ticket_snapshot = None
        chat_panel._reset_active_ticket_cache()
        chat_panel._ensure_timeline_bottom_follow()
        chat_panel._ticket_detail_timer.start(chat_panel._ticket_detail_timer.interval())
        await chat_panel._async_refresh_ticket_detail()
        chat_panel._show_chat_screen()
        self.window._select_sidebar_view("tickets", expand=True)
        return await self._result("ticket.open", ticket_id=ticket_id)

    async def _send_message(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or chat_panel.active_ticket_id or "").strip()
        text = str(payload.get("text") or "").strip()
        if not ticket_id:
            raise ValueError("ticket.message.send requires ticket_id or an active ticket")
        if not text:
            raise ValueError("ticket.message.send requires text")

        await chat_panel.ticket_client.send_message(
            ticket_id,
            text,
            from_role=str(payload.get("from_role") or "user"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
            reply_to=payload.get("reply_to") if isinstance(payload.get("reply_to"), dict) else None,
            account_session=chat_panel._current_account_session(),
            trace_parent_action_id=trace_parent_action_id,
        )
        chat_panel.active_ticket_id = ticket_id
        chat_panel._ensure_timeline_bottom_follow()
        chat_panel._show_chat_screen()
        chat_panel._refresh_ticket_detail_async()
        return await self._result("ticket.message.send", ticket_id=ticket_id, text_length=len(text))

    async def _run_ticket_tool(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or chat_panel.active_ticket_id or "").strip()
        tool_name = str(payload.get("tool_name") or "").strip()
        params = payload.get("params")
        if not ticket_id:
            raise ValueError("ticket.tool.run requires ticket_id or an active ticket")
        if not tool_name:
            raise ValueError("ticket.tool.run requires tool_name")
        if params is not None and not isinstance(params, dict):
            raise ValueError("ticket.tool.run params must be an object")

        account_session = chat_panel._current_account_session()
        result = await chat_panel.ticket_client.run_tool(
            device_id=chat_panel.device_id,
            ticket_id=ticket_id,
            tool_name=tool_name,
            params=params or {},
            account_session=account_session,
            trace_parent_action_id=trace_parent_action_id,
        )
        chat_panel.active_ticket_id = ticket_id
        chat_panel._ensure_timeline_bottom_follow()
        chat_panel._show_chat_screen()
        self.window._select_sidebar_view("tickets", expand=True)
        chat_panel._refresh_ticket_detail_async()
        return await self._result("ticket.tool.run", ticket_id=ticket_id, tool_name=tool_name, tool_result=result)

    async def _attach_files(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or chat_panel.active_ticket_id or "").strip()
        file_paths = [str(item) for item in (payload.get("file_paths") or []) if str(item).strip()]
        if not ticket_id:
            raise ValueError("ticket.attach_files requires ticket_id or an active ticket")
        if not file_paths:
            raise ValueError("ticket.attach_files requires file_paths")
        chat_panel.active_ticket_id = ticket_id
        await chat_panel._async_attach_files(file_paths, trace_parent_action_id=trace_parent_action_id)
        return await self._result("ticket.attach_files", ticket_id=ticket_id, file_count=len(file_paths))

    async def _confirm_resolution(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or chat_panel.active_ticket_id or "").strip()
        if not ticket_id:
            raise ValueError("ticket.confirm_resolution requires ticket_id or an active ticket")
        chat_panel.active_ticket_id = ticket_id
        await chat_panel.ticket_client.close_ticket(
            ticket_id,
            reason=str(payload.get("reason") or "requester_confirmed_resolution"),
            closed_by_role=str(payload.get("closed_by_role") or "user"),
            account_session=chat_panel._current_account_session(),
            trace_parent_action_id=trace_parent_action_id,
        )
        chat_panel._refresh_ticket_detail_async()
        chat_panel._refresh_ticket_list_async()
        return await self._result("ticket.confirm_resolution", ticket_id=ticket_id)

    async def _ticket_snapshot(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        ticket_id = str(payload.get("ticket_id") or chat_panel.active_ticket_id or "").strip()
        if not ticket_id:
            raise ValueError("ticket.snapshot requires ticket_id or an active ticket")
        snapshot = await chat_panel.ticket_client.get_ticket(
            ticket_id,
            limit=int(payload.get("limit") or 120),
            account_session=chat_panel._current_account_session(),
            trace_parent_action_id=trace_parent_action_id,
        )
        ticket = snapshot.get("ticket") if isinstance(snapshot.get("ticket"), dict) else {}
        messages = snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else []
        events = snapshot.get("events") if isinstance(snapshot.get("events"), list) else []
        trimmed_messages = [
            {
                "message_id": item.get("message_id"),
                "from_role": item.get("from_role"),
                "text": str(item.get("text") or "")[:240],
                "created_at": item.get("created_at") or item.get("ts"),
                "attachment_count": len(item.get("attachments") or item.get("attachment_refs") or []),
            }
            for item in messages[-20:]
            if isinstance(item, dict)
        ]
        trimmed_events = [
            {
                "event_id": item.get("event_id") or item.get("id"),
                "event_type": item.get("event_type") or item.get("event") or item.get("type"),
                "trace_id": item.get("trace_id"),
                "operation_id": item.get("operation_id"),
                "created_at": item.get("created_at") or item.get("ts"),
                "text": item.get("text") or item.get("message"),
            }
            for item in events[-30:]
            if isinstance(item, dict)
        ]
        return await self._result(
            "ticket.snapshot",
            ticket_id=ticket_id,
            ticket=ticket,
            message_count=len(messages),
            event_count=len(events),
            messages=trimmed_messages,
            events=trimmed_events,
        )

    async def _collect_logs(self, payload: dict[str, Any], *, trace_parent_action_id: Optional[str] = None) -> dict[str, Any]:
        recorder = get_action_trace_recorder()
        if getattr(recorder, "path", None):
            data_root = Path(recorder.path).parent.parent
        else:
            data_root = runtime_paths.resolve_data_root()
        logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))
        limit = max(1, min(int(payload.get("limit") or 80), 400))
        source = str(payload.get("source") or "agent").strip().lower()
        action_entries = recorder.search(
            limit=limit,
            action_id=payload.get("action_id"),
            parent_action_id=payload.get("parent_action_id"),
            ticket_id=payload.get("ticket_id"),
            operation_id=payload.get("operation_id"),
            message_id=payload.get("message_id"),
            tool_name=payload.get("tool_name"),
            status=payload.get("status"),
            text=payload.get("text"),
            source=payload.get("trace_source"),
        )
        agent_log_path = logs_dir / "agent.log"
        log_lines = [line.rstrip("\n") for line in read_log_tail(agent_log_path, limit)] if source in {"agent", "all"} else []
        launcher_candidates = [Path(data_root).parent / "launcher.log", Path(data_root) / "launcher.log"]
        launcher_log_path = next((candidate for candidate in launcher_candidates if candidate.exists()), launcher_candidates[0])
        launcher_lines = [line.rstrip("\n") for line in read_log_tail(launcher_log_path, limit)] if source in {"launcher", "all"} else []
        return await self._result(
            "logs.collect",
            action_entries=action_entries,
            action_trace_path=str(recorder.path) if getattr(recorder, "path", None) else None,
            agent_log_path=str(agent_log_path),
            agent_log_lines=log_lines,
            agent_log_text="\n".join(log_lines),
            launcher_log_path=str(launcher_log_path),
            launcher_log_lines=launcher_lines,
            launcher_log_text="\n".join(launcher_lines),
        )

    async def _result(self, action: str, **extra: Any) -> dict[str, Any]:
        result = {"status": "ok", "action": action, **extra}
        result["state"] = await self.get_status()
        return result

    def _show_window(self) -> None:
        if not self.window.isVisible():
            self.window.show()
        if self.window.isMinimized():
            self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _upsert_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        chat_panel = self.window.chat_panel
        profile_id = str(payload.get("profile_id") or "").strip() or str(uuid.uuid4())
        profile = {
            "id": profile_id,
            "display_name": str(payload.get("display_name") or "").strip(),
            "full_name": str(payload.get("full_name") or "").strip(),
            "building": str(payload.get("building") or "").strip(),
            "room": str(payload.get("room") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
        }
        profiles = [item for item in chat_panel._profiles() if item.get("id") != profile_id]
        profiles.append(profile)
        chat_panel._profiles_data["profiles"] = profiles
        if bool(payload.get("set_active", True)) or not chat_panel._profiles_data.get("active_profile_id"):
            chat_panel._profiles_data["active_profile_id"] = profile_id
        chat_panel._save_profiles()
        chat_panel._refresh_profile_selector()
        return {"profile_id": profile_id, "profile": profile}

    def _select_profile(self, profile_id: str) -> None:
        chat_panel = self.window.chat_panel
        for profile in chat_panel._profiles():
            if str(profile.get("id") or "") == profile_id:
                chat_panel._profiles_data["active_profile_id"] = profile_id
                chat_panel._save_profiles()
                chat_panel._refresh_profile_selector()
                return
        raise ValueError(f"unknown profile_id: {profile_id}")

    def _content_view_name(self, widget: Any) -> str:
        if widget is self.window.tickets_sidebar:
            return "tickets"
        if widget is self.window.chat_panel:
            return "chat"
        if widget is self.window.profile_sidebar:
            return "profile"
        if widget is getattr(self.window, "settings_page", None):
            return "settings"
        return "unknown"
