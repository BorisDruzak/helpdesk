#!/usr/bin/env python3
"""Protocol V3 live WebSocket diagnostics.

The probe is intentionally narrow and safe:
- token comes only from PC_CLIENT_AGENT_TOKEN or getpass;
- raw token is never printed;
- no local files are modified;
- cases are explicit so live evidence can be copied into PLANS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import aiohttp


DEFAULT_WS_URL = "wss://example.test:9443/ws"
DEFAULT_DEVICE_ID = "7a3429ec-1c0b-5495-9aad-b284f08ae965"
DEFAULT_MACHINE_ID = DEFAULT_DEVICE_ID
DEFAULT_INSTALL_ID = "a34642e5-e3d2-4ae4-90a0-480c4a188cf1"
DEFAULT_TOOLSET_HASH = "464075d978b3230f"
DEFAULT_LIVE_TICKET_ID = "68de6816-471b-48ba-88e3-fa691264bba3"

FULL_CAPABILITIES = [
    "protocol_v3",
    "envelope_v3",
    "trace_correlation",
    "deterministic_event_id",
    "agent_seq_per_ticket",
    "device_seq_per_device",
    "ticket_context",
    "job_context",
    "idempotency_keys",
    "nack_support",
    "outbox_ack_v3",
    "retry_policy",
    "outbox_batch_v1",
    "reconcile_tickets",
    "scheduled_tasks",
    "attachment_refs",
    "consent_flow",
    "rpc_request",
    "rpc_response",
    "outbox_item",
    "job_events",
    "device_events",
]


def _configure_stdio() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _token_from_env_or_prompt(required: bool) -> str:
    token = os.environ.get("PC_CLIENT_AGENT_TOKEN", "").strip()
    if token:
        return token
    if not required:
        return ""
    token = getpass.getpass("PC_CLIENT_AGENT_TOKEN: ").strip()
    if not token:
        raise SystemExit("token required")
    return token


def _token_evidence(token: str) -> dict[str, str | int | bool]:
    if not token:
        return {"present": False}
    return {
        "present": True,
        "prefix": token[:8],
        "sha256_12": hashlib.sha256(token.encode("utf-8")).hexdigest()[:12],
        "length": len(token),
    }


def _handshake(
    *,
    token: str,
    protocol_version: str | None = "ws_ticket_v3",
    capabilities: list[str] | None = None,
    device_id: str = DEFAULT_DEVICE_ID,
    machine_id: str = DEFAULT_MACHINE_ID,
    install_id: str = DEFAULT_INSTALL_ID,
    toolset_hash: str | None = DEFAULT_TOOLSET_HASH,
    client_kind: str = "diagnostic_probe",
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    payload = {
        "token": token,
        "uuid": machine_id,
        "device_id": device_id,
        "machine_id": machine_id,
        "install_id": install_id,
        "machine_id_source": "live_ws_v3_probe",
        "hostname": "ADMIN-2-PROBE",
        "os": "Windows",
        "agent_version": "3.1.61",
        "db_schema_version": 9,
        "tools_version": "tools_v1",
        "toolset_hash": toolset_hash,
        "tools_count": 6,
        "modules": ["system", "screen", "diag_logs", "inventory", "presence"],
        "modules_inventory": [],
        "client_kind": client_kind,
    }
    msg: dict[str, Any] = {
        "type": "handshake",
        "request_id": request_id,
        "device_id": device_id,
        "trace_id": trace_id,
        "payload": payload,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "agent",
            "client_kind": client_kind,
            "capabilities": list(FULL_CAPABILITIES if capabilities is None else capabilities),
            "supported_message_types": [
                "handshake",
                "handshake_ack",
                "outbox_item",
                "outbox_batch",
                "outbox_ack",
                "command_ack",
                "command_result",
            ],
        },
        "token": token,
        "agent_version": "3.1.61",
        "tools_version": "tools_v1",
        "supported_message_types": ["handshake", "outbox_batch", "command_ack", "command_result"],
        "modules": ["system", "screen", "diag_logs", "inventory", "presence"],
    }
    if protocol_version is not None:
        msg["protocol_version"] = protocol_version
    return msg


def _guard_live_runtime_probe(*, client_kind: str, allow_live_agent_session: bool) -> None:
    if client_kind != "agent_runtime" or allow_live_agent_session:
        return
    raise SystemExit(
        "Refusing to open an agent_runtime raw probe without --allow-live-agent-session. "
        "Use the default diagnostic_probe mode for live diagnostics, or use a dedicated "
        "diagnostic runtime token/device with the explicit override."
    )


async def _recv_until_terminal(ws: aiohttp.ClientWebSocketResponse, timeout: float) -> dict[str, Any]:
    try:
        message = await asyncio.wait_for(ws.receive(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"event": "timeout"}
    if message.type == aiohttp.WSMsgType.TEXT:
        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError:
            payload = {"raw": message.data[:500]}
        return {"event": "text", "payload": payload}
    if message.type == aiohttp.WSMsgType.CLOSE:
        return {"event": "close", "close_code": message.data, "close_reason": message.extra, "ws_close_code": ws.close_code}
    if message.type == aiohttp.WSMsgType.CLOSED:
        return {"event": "closed", "close_code": ws.close_code}
    if message.type == aiohttp.WSMsgType.ERROR:
        return {"event": "error", "close_code": ws.close_code, "error": str(ws.exception())}
    return {"event": str(message.type), "close_code": ws.close_code}


async def _recv_many(ws: aiohttp.ClientWebSocketResponse, *, timeout: float, max_messages: int = 8) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for _ in range(max_messages):
        item = await _recv_until_terminal(ws, timeout=timeout)
        messages.append(item)
        if item.get("event") in {"timeout", "close", "closed", "error"}:
            break
    return messages


def _outbox_item(
    *,
    case: str,
    outbox_id: str,
    run_id: str | None = None,
    ticket_id: str | None = DEFAULT_LIVE_TICKET_ID,
    event_ticket_id: str | None = DEFAULT_LIVE_TICKET_ID,
    agent_seq: int | None = None,
    device_seq: int | None = None,
    trace_id: str | None = None,
    actor_role: str = "agent",
    item_type: str = "job_event",
    event_name: str = "chat_message",
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event": event_name,
        "text": f"live malformed probe {case}",
        "from": "user",
        "probe_case": case,
    }
    if run_id:
        event["probe_run_id"] = run_id
    if event_ticket_id is not None:
        event["ticket_id"] = event_ticket_id
    message: dict[str, Any] = {
        "type": "outbox_item",
        "request_id": str(uuid.uuid4()),
        "device_id": DEFAULT_DEVICE_ID,
        "protocol_version": "ws_ticket_v3",
        "payload": {
            "outbox_id": outbox_id,
            "item_type": item_type,
            "event": event,
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": actor_role,
        },
    }
    if trace_id is not None:
        message["trace_id"] = trace_id
    if ticket_id is not None:
        message["ticket_id"] = ticket_id
    if agent_seq is not None:
        message["payload"]["agent_seq"] = agent_seq
    if device_seq is not None:
        message["payload"]["device_seq"] = device_seq
    return message


def _malformed_case(case: str, ticket_id: str, outbox_num: int, *, run_id: str, seq_base: int) -> dict[str, Any]:
    outbox_id = f"live-p0-10-{run_id}-{case}-{outbox_num}"
    trace_id = str(uuid.uuid4())
    unknown_ticket = str(uuid.uuid4())
    cases = {
        "both_seq": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=ticket_id,
            event_ticket_id=ticket_id,
            agent_seq=seq_base + outbox_num,
            device_seq=seq_base + outbox_num,
            trace_id=trace_id,
        ),
        "neither_seq": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=None,
            event_ticket_id=None,
            trace_id=trace_id,
        ),
        "unknown_ticket": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=unknown_ticket,
            event_ticket_id=unknown_ticket,
            agent_seq=seq_base + 100 + outbox_num,
            trace_id=trace_id,
        ),
        "missing_trace_id": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=ticket_id,
            event_ticket_id=ticket_id,
            agent_seq=seq_base + 200 + outbox_num,
            trace_id=None,
        ),
        "wrong_actor_role": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=ticket_id,
            event_ticket_id=ticket_id,
            agent_seq=seq_base + 300 + outbox_num,
            trace_id=trace_id,
            actor_role="user",
        ),
        "top_ticket_only": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=ticket_id,
            event_ticket_id=None,
            device_seq=seq_base + 400 + outbox_num,
            trace_id=trace_id,
        ),
        "unknown_item_type": lambda: _outbox_item(
            case=case,
            outbox_id=outbox_id,
            run_id=run_id,
            ticket_id=ticket_id,
            event_ticket_id=ticket_id,
            agent_seq=seq_base + 500 + outbox_num,
            trace_id=trace_id,
            item_type="unknown_live_probe_type",
            event_name="unknown_live_probe_event",
        ),
    }
    return cases[case]()


def _build_mixed_batch_items(
    *,
    run_id: str,
    ticket_id: str,
    valid_agent_seq: int,
    duplicate_agent_seq: int,
    valid_device_seq: int,
    invalid_seq_base: int,
    valid_device_event: str = "probe_device_event",
) -> list[dict[str, Any]]:
    unknown_ticket = str(uuid.uuid4())
    valid_ticket = _outbox_item(
        case="p1_1_e_valid_ticket",
        outbox_id=f"p1e-{run_id}-valid-ticket",
        run_id=run_id,
        ticket_id=ticket_id,
        event_ticket_id=ticket_id,
        agent_seq=valid_agent_seq,
        trace_id=str(uuid.uuid4()),
        event_name="chat_message",
    )
    valid_ticket["payload"]["event"]["text"] = f"P1.1.E valid batch ticket marker {run_id}"

    duplicate_ticket = _outbox_item(
        case="p1_1_e_duplicate_ticket",
        outbox_id=f"p1e-{run_id}-duplicate-ticket",
        run_id=run_id,
        ticket_id=ticket_id,
        event_ticket_id=ticket_id,
        agent_seq=duplicate_agent_seq,
        trace_id=str(uuid.uuid4()),
        event_name="chat_message",
    )
    duplicate_ticket["payload"]["event"]["text"] = f"P1.1.E duplicate batch ticket marker {run_id}"

    both_seq = _outbox_item(
        case="p1_1_e_invalid_both_seq",
        outbox_id=f"p1e-{run_id}-both-seq",
        run_id=run_id,
        ticket_id=ticket_id,
        event_ticket_id=ticket_id,
        agent_seq=invalid_seq_base + 1,
        device_seq=invalid_seq_base + 1,
        trace_id=str(uuid.uuid4()),
        event_name="chat_message",
    )

    unknown_ticket_item = _outbox_item(
        case="p1_1_e_unknown_ticket",
        outbox_id=f"p1e-{run_id}-unknown-ticket",
        run_id=run_id,
        ticket_id=unknown_ticket,
        event_ticket_id=unknown_ticket,
        agent_seq=invalid_seq_base + 2,
        trace_id=str(uuid.uuid4()),
        event_name="chat_message",
    )

    valid_device = _outbox_item(
        case="p1_1_e_valid_device",
        outbox_id=f"p1e-{run_id}-valid-device",
        run_id=run_id,
        ticket_id=None,
        event_ticket_id=None,
        device_seq=valid_device_seq,
        trace_id=str(uuid.uuid4()),
        event_name=valid_device_event,
    )
    valid_device["payload"]["event"].update(
        {
            "text": f"P1.1.E valid batch device marker {run_id}",
            "reason": "p1_1_e_valid_device_batch",
            "p1_case": "P1.1.E.valid_device",
        }
    )

    device_with_ticket = _outbox_item(
        case="p1_1_e_invalid_device_ticket_context",
        outbox_id=f"p1e-{run_id}-device-with-ticket",
        run_id=run_id,
        ticket_id=ticket_id,
        event_ticket_id=None,
        device_seq=invalid_seq_base + 3,
        trace_id=str(uuid.uuid4()),
        event_name=valid_device_event,
    )

    return [
        valid_ticket,
        duplicate_ticket,
        both_seq,
        unknown_ticket_item,
        valid_device,
        device_with_ticket,
    ]


def _batch_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload") or {}
    return {
        "outbox_id": payload.get("outbox_id"),
        "agent_seq": payload.get("agent_seq"),
        "device_seq": payload.get("device_seq"),
        "ticket_id": item.get("ticket_id"),
        "trace_id": item.get("trace_id"),
        "event": payload.get("event"),
    }


def _received_outbox_ids(messages: list[dict[str, Any]], message_type: str) -> set[str]:
    ids: set[str] = set()
    for item in messages:
        payload = item.get("payload") if item.get("event") == "text" else None
        if not isinstance(payload, dict) or payload.get("type") != message_type:
            continue
        outbox_ids = (payload.get("payload") or {}).get("outbox_ids") or []
        ids.update(str(outbox_id) for outbox_id in outbox_ids)
    return ids


async def _run_invalid_case(args: argparse.Namespace, case: str) -> dict[str, Any]:
    real_token = _token_from_env_or_prompt(required=False)
    cases = {
        "wrong_protocol": {"protocol_version": "ws_ticket_v2"},
        "missing_protocol_v3": {"capabilities": [c for c in FULL_CAPABILITIES if c != "protocol_v3"]},
        "missing_envelope_v3": {"capabilities": [c for c in FULL_CAPABILITIES if c != "envelope_v3"]},
        "missing_outbox_ack_v3": {"capabilities": [c for c in FULL_CAPABILITIES if c != "outbox_ack_v3"]},
        "missing_token": {"token": ""},
        "invalid_token": {"token": "invalid-token-for-live-probe"},
    }
    kwargs = dict(cases[case])
    token = kwargs.pop("token", real_token)
    msg = _handshake(token=token, client_kind=args.client_kind, **kwargs)
    evidence = {
        "case": case,
        "ws_url": args.ws_url,
        "request_id": msg.get("request_id"),
        "trace_id": msg.get("trace_id"),
        "token": _token_evidence(token),
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(args.ws_url, ssl=False, heartbeat=10) as ws:
            await ws.send_json(msg)
            result = await _recv_until_terminal(ws, timeout=args.timeout)
            if result.get("event") == "text":
                result["next"] = await _recv_until_terminal(ws, timeout=1.0)
            evidence["result"] = result
            if ws.close_code and "close_code" not in result:
                evidence["close_code"] = ws.close_code
    return evidence


def _observed_close_code(evidence: dict[str, Any]) -> int | None:
    result = evidence.get("result", {})
    return result.get("close_code") or result.get("next", {}).get("close_code") or evidence.get("close_code")


def _has_text_payload_type(messages: list[dict[str, Any]], message_type: str) -> bool:
    return any(item.get("payload", {}).get("type") == message_type for item in messages if item.get("event") == "text")


def _first_close_code(messages: list[dict[str, Any]]) -> int | None:
    for item in messages:
        code = item.get("close_code")
        if code:
            return code
    return None


async def run_invalid(args: argparse.Namespace) -> int:
    _guard_live_runtime_probe(
        client_kind=args.client_kind,
        allow_live_agent_session=args.allow_live_agent_session,
    )
    cases = [
        "wrong_protocol",
        "missing_protocol_v3",
        "missing_envelope_v3",
        "missing_outbox_ack_v3",
        "missing_token",
        "invalid_token",
    ] if args.case == "all" else [args.case]
    items = [await _run_invalid_case(args, case) for case in cases]
    evidence: dict[str, Any] = {
        "command": "invalid-handshake",
        "ws_url": args.ws_url,
        "expected_close_code": args.expect_close_code,
        "items": items,
    }
    print(json.dumps(evidence if args.case == "all" else items[0], ensure_ascii=False, indent=2))
    return 0 if all(_observed_close_code(item) == args.expect_close_code for item in items) else 2


async def run_double(args: argparse.Namespace) -> int:
    if args.client_kind != "agent_runtime":
        raise SystemExit(
            "double-connect supersede verification requires --client-kind agent_runtime "
            "and a dedicated diagnostic runtime token/device."
        )
    _guard_live_runtime_probe(
        client_kind=args.client_kind,
        allow_live_agent_session=args.allow_live_agent_session,
    )
    token = _token_from_env_or_prompt(required=True)
    first_msg = _handshake(token=token, client_kind=args.client_kind)
    second_msg = _handshake(token=token, client_kind=args.client_kind)
    evidence: dict[str, Any] = {
        "case": "double_connect",
        "ws_url": args.ws_url,
        "token": _token_evidence(token),
        "first_request_id": first_msg["request_id"],
        "first_trace_id": first_msg["trace_id"],
        "second_request_id": second_msg["request_id"],
        "second_trace_id": second_msg["trace_id"],
        "expected_supersede_close_code": args.expect_supersede_close_code,
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(args.ws_url, ssl=False, heartbeat=10) as first:
            await first.send_json(first_msg)
            first_messages = await _recv_many(first, timeout=args.timeout, max_messages=6)
            evidence["first_messages"] = first_messages
            evidence["first_result"] = first_messages[0] if first_messages else {}
            async with session.ws_connect(args.ws_url, ssl=False, heartbeat=10) as second:
                await second.send_json(second_msg)
                second_messages = await _recv_many(second, timeout=args.timeout, max_messages=6)
                evidence["second_messages"] = second_messages
                evidence["second_result"] = second_messages[0] if second_messages else {}
                first_after_second = await _recv_many(first, timeout=args.timeout, max_messages=6)
                evidence["first_after_second_messages"] = first_after_second
                evidence["first_after_second"] = first_after_second[-1] if first_after_second else {}
                await second.close()
            evidence["first_close_code_final"] = first.close_code
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    first_close = _first_close_code(evidence.get("first_after_second_messages", [])) or evidence.get("first_close_code_final")
    ok = (
        _has_text_payload_type(evidence.get("first_messages", []), "handshake_ack")
        and _has_text_payload_type(evidence.get("second_messages", []), "handshake_ack")
        and first_close == args.expect_supersede_close_code
    )
    return 0 if ok else 2


async def run_malformed_outbox(args: argparse.Namespace) -> int:
    _guard_live_runtime_probe(
        client_kind=args.client_kind,
        allow_live_agent_session=args.allow_live_agent_session,
    )
    token = _token_from_env_or_prompt(required=True)
    cases = [
        "both_seq",
        "neither_seq",
        "unknown_ticket",
        "missing_trace_id",
        "wrong_actor_role",
        "top_ticket_only",
        "unknown_item_type",
    ] if args.case == "all" else [args.case]
    run_id = (args.run_id or uuid.uuid4().hex[:8]).strip()
    seq_base = args.seq_base or (100000 + (int(uuid.uuid4().hex[:6], 16) % 800000))
    handshake = _handshake(token=token, client_kind=args.client_kind)
    evidence: dict[str, Any] = {
        "case": "malformed_outbox",
        "run_id": run_id,
        "seq_base": seq_base,
        "requested_cases": cases,
        "ws_url": args.ws_url,
        "ticket_id": args.ticket_id,
        "token": _token_evidence(token),
        "handshake_request_id": handshake["request_id"],
        "handshake_trace_id": handshake["trace_id"],
        "items": [],
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(args.ws_url, ssl=False, heartbeat=10) as ws:
            await ws.send_json(handshake)
            evidence["handshake_result"] = await _recv_until_terminal(ws, timeout=args.timeout)
            for index, case in enumerate(cases, start=1):
                item = _malformed_case(case, args.ticket_id, index, run_id=run_id, seq_base=seq_base)
                await ws.send_json(item)
                received = await _recv_many(ws, timeout=args.timeout, max_messages=4)
                evidence["items"].append({
                    "case": case,
                    "outbox_id": item.get("payload", {}).get("outbox_id"),
                    "request_id": item.get("request_id"),
                    "trace_id": item.get("trace_id"),
                    "actor_role": (item.get("meta") or {}).get("actor_role"),
                    "payload_keys": sorted((item.get("payload") or {}).keys()),
                    "event": item.get("payload", {}).get("event"),
                    "received": received,
                })
            await ws.close()
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    # This is a live diagnostic probe; callers inspect per-case ACK/NACK evidence.
    return 0


async def run_mixed_batch(args: argparse.Namespace) -> int:
    _guard_live_runtime_probe(
        client_kind=args.client_kind,
        allow_live_agent_session=args.allow_live_agent_session,
    )
    token = _token_from_env_or_prompt(required=True)
    run_id = (args.run_id or uuid.uuid4().hex[:8]).strip()
    invalid_seq_base = args.invalid_seq_base or (900000 + (int(uuid.uuid4().hex[:5], 16) % 90000))
    items = _build_mixed_batch_items(
        run_id=run_id,
        ticket_id=args.ticket_id,
        valid_agent_seq=args.valid_agent_seq,
        duplicate_agent_seq=args.duplicate_agent_seq,
        valid_device_seq=args.valid_device_seq,
        invalid_seq_base=invalid_seq_base,
        valid_device_event=args.valid_device_event,
    )
    handshake = _handshake(token=token, client_kind=args.client_kind)
    batch_message = {
        "type": "outbox_items_batch",
        "request_id": str(uuid.uuid4()),
        "device_id": DEFAULT_DEVICE_ID,
        "protocol_version": "ws_ticket_v3",
        "trace_id": str(uuid.uuid4()),
        "payload": {"items": items},
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "agent",
        },
    }
    expected_ack_ids = {
        f"p1e-{run_id}-valid-ticket",
        f"p1e-{run_id}-duplicate-ticket",
        f"p1e-{run_id}-valid-device",
    }
    expected_nack_ids = {
        f"p1e-{run_id}-both-seq",
        f"p1e-{run_id}-unknown-ticket",
        f"p1e-{run_id}-device-with-ticket",
    }
    evidence: dict[str, Any] = {
        "case": "p1_1_e_mixed_batch",
        "run_id": run_id,
        "ws_url": args.ws_url,
        "ticket_id": args.ticket_id,
        "valid_device_event": args.valid_device_event,
        "token": _token_evidence(token),
        "handshake_request_id": handshake["request_id"],
        "handshake_trace_id": handshake["trace_id"],
        "batch_request_id": batch_message["request_id"],
        "batch_trace_id": batch_message["trace_id"],
        "expected_ack_ids": sorted(expected_ack_ids),
        "expected_nack_ids": sorted(expected_nack_ids),
        "sent_items": [_batch_item_summary(item) for item in items],
    }
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(args.ws_url, ssl=False, heartbeat=10) as ws:
            await ws.send_json(handshake)
            evidence["handshake_result"] = await _recv_until_terminal(ws, timeout=args.timeout)
            await ws.send_json(batch_message)
            received = await _recv_many(ws, timeout=args.timeout, max_messages=args.max_messages)
            evidence["received"] = received
            await ws.close()

    acked = _received_outbox_ids(evidence["received"], "outbox_ack")
    nacked = _received_outbox_ids(evidence["received"], "outbox_nack")
    unexpected_commands = [
        item.get("payload")
        for item in evidence["received"]
        if item.get("event") == "text" and (item.get("payload") or {}).get("type") == "command"
    ]
    evidence["observed_ack_ids"] = sorted(acked)
    evidence["observed_nack_ids"] = sorted(nacked)
    evidence["unexpected_command_count"] = len(unexpected_commands)
    if unexpected_commands:
        evidence["unexpected_commands"] = [
            {
                "request_id": command.get("request_id"),
                "trace_id": command.get("trace_id"),
                "command": (command.get("payload") or {}).get("command"),
            }
            for command in unexpected_commands
            if isinstance(command, dict)
        ]
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    ok = (
        expected_ack_ids.issubset(acked)
        and expected_nack_ids.issubset(nacked)
        and not unexpected_commands
    )
    return 0 if ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live Protocol V3 WS probe")
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--client-kind",
        choices=["diagnostic_probe", "agent_runtime"],
        default="diagnostic_probe",
        help="diagnostic_probe is isolated from live command dispatch; agent_runtime requires explicit override.",
    )
    parser.add_argument(
        "--allow-live-agent-session",
        action="store_true",
        help="Allow raw probe to register as agent_runtime. Use only with a dedicated diagnostic runtime token/device.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    invalid = sub.add_parser("invalid-handshake")
    invalid.add_argument(
        "--case",
        required=True,
        choices=[
            "all",
            "wrong_protocol",
            "missing_protocol_v3",
            "missing_envelope_v3",
            "missing_outbox_ack_v3",
            "missing_token",
            "invalid_token",
        ],
    )
    invalid.add_argument("--expect-close-code", type=int, default=4003)

    double = sub.add_parser("double-connect")
    double.add_argument("--expect-supersede-close-code", type=int, default=4002)
    malformed = sub.add_parser("malformed-outbox")
    malformed.add_argument(
        "--case",
        default="all",
        choices=[
            "all",
            "both_seq",
            "neither_seq",
            "unknown_ticket",
            "missing_trace_id",
            "wrong_actor_role",
            "top_ticket_only",
            "unknown_item_type",
        ],
    )
    malformed.add_argument("--ticket-id", default=DEFAULT_LIVE_TICKET_ID)
    malformed.add_argument("--run-id", default=None)
    malformed.add_argument("--seq-base", type=int, default=None)
    mixed = sub.add_parser("mixed-batch")
    mixed.add_argument("--ticket-id", required=True)
    mixed.add_argument("--run-id", default=None)
    mixed.add_argument("--valid-agent-seq", type=int, required=True)
    mixed.add_argument("--duplicate-agent-seq", type=int, required=True)
    mixed.add_argument("--valid-device-seq", type=int, required=True)
    mixed.add_argument("--invalid-seq-base", type=int, default=None)
    mixed.add_argument(
        "--valid-device-event",
        default="probe_device_event",
        help=(
            "Neutral device event used for the valid device item. Avoid tools_changed "
            "for raw probes against a real device because it triggers list_tools."
        ),
    )
    mixed.add_argument("--max-messages", type=int, default=10)
    return parser


def main() -> int:
    _configure_stdio()
    args = build_parser().parse_args()
    if args.command == "invalid-handshake":
        return asyncio.run(run_invalid(args))
    if args.command == "double-connect":
        return asyncio.run(run_double(args))
    if args.command == "malformed-outbox":
        return asyncio.run(run_malformed_outbox(args))
    if args.command == "mixed-batch":
        return asyncio.run(run_mixed_batch(args))
    raise SystemExit(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
