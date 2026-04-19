#!/usr/bin/env python3
"""Drive a named local Windows agent instance through localhost automation endpoints."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parent.parent
INSTANCE_ROOT = WORKSPACE / ".local-agent" / "instances"


def _configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _load_instance(name: str) -> dict[str, Any]:
    path = INSTANCE_ROOT / name / "instance.json"
    if not path.exists():
        raise SystemExit(f"Unknown local agent instance: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _ui_base_url(instance_name: str) -> str:
    payload = _load_instance(instance_name)
    port = int(payload.get("ui_port") or 0)
    if not port:
        raise SystemExit(f"Instance '{instance_name}' does not have ui_port in instance.json")
    return f"http://127.0.0.1:{port}"


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc


def _parse_json_argument(raw: str | None, *, field_name: str) -> Any:
    if not raw:
        return None
    if raw == "-":
        raw = sys.stdin.read()
    elif raw.startswith("@"):
        path = Path(raw[1:]).expanduser()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"{field_name} file could not be read: {path} ({exc})") from exc
    raw = raw.strip()
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    # PowerShell native piping may surface the UTF-8 BOM as mojibake text.
    if raw.startswith("п»ї"):
        raw = raw[3:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} must be valid JSON: {exc}") from exc


def _print_result(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


def _automation_status(instance_name: str) -> int:
    return _print_result(_request_json("GET", f"{_ui_base_url(instance_name)}/ui/automation/status"))


def _automation_run(instance_name: str, payload: dict[str, Any]) -> int:
    return _print_result(_request_json("POST", f"{_ui_base_url(instance_name)}/ui/automation/run", payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drive local GUI agent automation for a named instance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Read automation status from a named instance")
    status.add_argument("instance")

    run = subparsers.add_parser("run", help="Run a raw automation action")
    run.add_argument("instance")
    run.add_argument("action")
    run.add_argument(
        "--payload-json",
        default=None,
        help="Additional JSON object merged into the payload; use '-' for stdin or '@path' for a file",
    )

    profile = subparsers.add_parser("upsert-profile", help="Create or update the active requester profile")
    profile.add_argument("instance")
    profile.add_argument("--profile-id", default=None)
    profile.add_argument("--display-name", default="")
    profile.add_argument("--full-name", default="")
    profile.add_argument("--building", default="")
    profile.add_argument("--room", default="")
    profile.add_argument("--phone", default="")
    profile.add_argument("--no-set-active", action="store_true")

    create = subparsers.add_parser("create-ticket", help="Create a ticket through GUI automation")
    create.add_argument("instance")
    create.add_argument("--title", default="Support Request")
    create.add_argument("--description", required=True)
    create.add_argument("--urgency", action="store_true")
    create.add_argument("--importance", action="store_true")
    create.add_argument("--urgency-reason", default=None)
    create.add_argument("--importance-reason", default=None)
    create.add_argument("--form-key", default=None)
    create.add_argument("--form-pack-key", default=None)
    create.add_argument("--form-pack-version", default=None)
    create.add_argument("--ticket-type", default=None)
    create.add_argument(
        "--form-payload-json",
        default=None,
        help="JSON object for smart-form fields; use '-' for stdin or '@path' for a file",
    )
    create.add_argument(
        "--tags-json",
        default=None,
        help="Optional JSON array of tags; use '-' for stdin or '@path' for a file",
    )

    send = subparsers.add_parser("send-message", help="Send a ticket message through GUI automation")
    send.add_argument("instance")
    send.add_argument("--ticket-id", default=None)
    send.add_argument("--text", required=True)
    send.add_argument("--from-role", default="user")
    send.add_argument("--metadata-json", default=None, help="JSON object; use '-' for stdin or '@path' for a file")
    send.add_argument("--reply-to-json", default=None, help="JSON object; use '-' for stdin or '@path' for a file")

    run_tool = subparsers.add_parser("run-tool", help="Run a ticket tool through GUI automation")
    run_tool.add_argument("instance")
    run_tool.add_argument("--ticket-id", default=None)
    run_tool.add_argument("--tool-name", required=True)
    run_tool.add_argument("--params-json", default=None, help="JSON object; use '-' for stdin or '@path' for a file")

    inject = subparsers.add_parser("inject-event", help="Inject an SSE-like event into the GUI")
    inject.add_argument("instance")
    inject.add_argument("--event-json", required=True, help="JSON object; use '-' for stdin or '@path' for a file")

    capture_screenshot = subparsers.add_parser("capture-screenshot", help="Request screenshot tool from the active or specified ticket")
    capture_screenshot.add_argument("instance")
    capture_screenshot.add_argument("--ticket-id", default=None)

    capture_video = subparsers.add_parser("capture-video", help="Request screen recording tool from the active or specified ticket")
    capture_video.add_argument("instance")
    capture_video.add_argument("--ticket-id", default=None)
    capture_video.add_argument("--duration-sec", type=int, default=60)

    attach = subparsers.add_parser("attach-files", help="Upload local files into the active or specified ticket")
    attach.add_argument("instance")
    attach.add_argument("--ticket-id", default=None)
    attach.add_argument("files", nargs="+")

    snapshot = subparsers.add_parser("snapshot-ticket", help="Fetch a ticket snapshot through GUI automation")
    snapshot.add_argument("instance")
    snapshot.add_argument("--ticket-id", default=None)
    snapshot.add_argument("--limit", type=int, default=120)

    confirm = subparsers.add_parser("confirm-resolution", help="Confirm resolved ticket and close it from requester side")
    confirm.add_argument("instance")
    confirm.add_argument("--ticket-id", default=None)
    confirm.add_argument("--reason", default="requester_confirmed_resolution")

    logs = subparsers.add_parser("collect-logs", help="Collect focused action/runtime logs through GUI automation")
    logs.add_argument("instance")
    logs.add_argument("--source", default="agent")
    logs.add_argument("--limit", type=int, default=80)
    logs.add_argument("--action-id", default=None)
    logs.add_argument("--parent-action-id", default=None)
    logs.add_argument("--ticket-id", default=None)
    logs.add_argument("--operation-id", default=None)
    logs.add_argument("--message-id", default=None)
    logs.add_argument("--tool-name", default=None)
    logs.add_argument("--status", default=None)
    logs.add_argument("--text", default=None)
    logs.add_argument("--trace-source", default=None)

    support = subparsers.add_parser("request-support", help="Call the existing local request_support endpoint")
    support.add_argument("instance")
    support.add_argument("--title", default="Support needed")
    support.add_argument("--reason", default="user_requested")
    support.add_argument("--severity", default="warning")
    support.add_argument("--context-json", default=None, help="JSON object; use '-' for stdin or '@path' for a file")

    return parser


def main() -> int:
    _configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        return _automation_status(args.instance)

    if args.command == "run":
        extra = _parse_json_argument(args.payload_json, field_name="payload-json")
        if extra is not None and not isinstance(extra, dict):
            raise SystemExit("--payload-json must be a JSON object")
        payload = {"action": args.action}
        if isinstance(extra, dict):
            payload.update(extra)
        return _automation_run(args.instance, payload)

    if args.command == "upsert-profile":
        payload = {
            "action": "profile.upsert",
            "display_name": args.display_name,
            "full_name": args.full_name,
            "building": args.building,
            "room": args.room,
            "phone": args.phone,
            "set_active": not args.no_set_active,
        }
        if args.profile_id:
            payload["profile_id"] = args.profile_id
        return _automation_run(args.instance, payload)

    if args.command == "create-ticket":
        form_payload = _parse_json_argument(args.form_payload_json, field_name="form-payload-json")
        if form_payload is not None and not isinstance(form_payload, dict):
            raise SystemExit("--form-payload-json must be a JSON object")
        tags = _parse_json_argument(args.tags_json, field_name="tags-json")
        if tags is not None and not isinstance(tags, list):
            raise SystemExit("--tags-json must be a JSON array")
        payload = {
            "action": "ticket.create",
            "title": args.title,
            "description": args.description,
            "urgency": args.urgency,
            "importance": args.importance,
        }
        if args.urgency_reason:
            payload["urgency_reason"] = args.urgency_reason
        if args.importance_reason:
            payload["importance_reason"] = args.importance_reason
        if args.form_key:
            payload["form_key"] = args.form_key
        if args.form_pack_key:
            payload["form_pack_key"] = args.form_pack_key
        if args.form_pack_version:
            payload["form_pack_version"] = args.form_pack_version
        if args.ticket_type:
            payload["ticket_type"] = args.ticket_type
        if form_payload is not None:
            payload["form_payload"] = form_payload
        if tags is not None:
            payload["tags"] = tags
        return _automation_run(args.instance, payload)

    if args.command == "send-message":
        metadata = _parse_json_argument(args.metadata_json, field_name="metadata-json")
        reply_to = _parse_json_argument(args.reply_to_json, field_name="reply-to-json")
        if metadata is not None and not isinstance(metadata, dict):
            raise SystemExit("--metadata-json must be a JSON object")
        if reply_to is not None and not isinstance(reply_to, dict):
            raise SystemExit("--reply-to-json must be a JSON object")
        payload = {
            "action": "ticket.message.send",
            "text": args.text,
            "from_role": args.from_role,
        }
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        if metadata is not None:
            payload["metadata"] = metadata
        if reply_to is not None:
            payload["reply_to"] = reply_to
        return _automation_run(args.instance, payload)

    if args.command == "run-tool":
        params = _parse_json_argument(args.params_json, field_name="params-json")
        if params is not None and not isinstance(params, dict):
            raise SystemExit("--params-json must be a JSON object")
        payload = {
            "action": "ticket.tool.run",
            "tool_name": args.tool_name,
        }
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        if params is not None:
            payload["params"] = params
        return _automation_run(args.instance, payload)

    if args.command == "inject-event":
        event = _parse_json_argument(args.event_json, field_name="event-json")
        if not isinstance(event, dict):
            raise SystemExit("--event-json must be a JSON object")
        return _automation_run(args.instance, {"action": "event.inject", "event": event})

    if args.command == "capture-screenshot":
        payload = {"action": "ticket.capture_screenshot"}
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        return _automation_run(args.instance, payload)

    if args.command == "capture-video":
        payload = {
            "action": "ticket.capture_video",
            "params": {"duration_sec": args.duration_sec},
        }
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        return _automation_run(args.instance, payload)

    if args.command == "attach-files":
        payload = {"action": "ticket.attach_files", "file_paths": args.files}
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        return _automation_run(args.instance, payload)

    if args.command == "snapshot-ticket":
        payload = {"action": "ticket.snapshot", "limit": args.limit}
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        return _automation_run(args.instance, payload)

    if args.command == "confirm-resolution":
        payload = {"action": "ticket.confirm_resolution", "reason": args.reason}
        if args.ticket_id:
            payload["ticket_id"] = args.ticket_id
        return _automation_run(args.instance, payload)

    if args.command == "collect-logs":
        payload = {
            "action": "logs.collect",
            "source": args.source,
            "limit": args.limit,
        }
        for field in (
            "action_id",
            "parent_action_id",
            "ticket_id",
            "operation_id",
            "message_id",
            "tool_name",
            "status",
            "text",
            "trace_source",
        ):
            value = getattr(args, field)
            if value:
                payload[field] = value
        return _automation_run(args.instance, payload)

    if args.command == "request-support":
        context = _parse_json_argument(args.context_json, field_name="context-json")
        if context is not None and not isinstance(context, dict):
            raise SystemExit("--context-json must be a JSON object")
        return _print_result(
            _request_json(
                "POST",
                f"{_ui_base_url(args.instance)}/ui/request_support",
                {
                    "title": args.title,
                    "reason": args.reason,
                    "severity": args.severity,
                    "context": context or {},
                },
            )
        )

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
