from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
for import_path in (str(ROOT), str(SERVER_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

DEFAULT_PACK_PATH = ROOT / "test_data_packs" / "web_first_phase_e.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _device_key_candidates(device: dict[str, Any]) -> set[str]:
    metadata = _metadata(device.get("device_metadata"))
    values = {
        device.get("device_id"),
        device.get("hostname"),
        metadata.get("phase_e_agent_key"),
        metadata.get("phase_e_key"),
        metadata.get("vm_agent_key"),
        metadata.get("agent_key"),
    }
    return {_as_text(value) for value in values if _as_text(value)}


def _person_key_candidates(person: dict[str, Any]) -> set[str]:
    metadata = _metadata(person.get("metadata_json"))
    values = {
        person.get("profile_key"),
        person.get("external_id"),
        person.get("email"),
        person.get("display_name"),
        metadata.get("phase_e_user_key"),
        metadata.get("test_user_key"),
        metadata.get("user_key"),
    }
    return {_as_text(value) for value in values if _as_text(value)}


def _find_required_device(agent_key: str, devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    metadata_matches = [
        device
        for device in devices
        if _as_text(_metadata(device.get("device_metadata")).get("phase_e_agent_key")) == agent_key
        or _as_text(_metadata(device.get("device_metadata")).get("vm_agent_key")) == agent_key
    ]
    if metadata_matches:
        return metadata_matches[0]
    for device in devices:
        if agent_key in _device_key_candidates(device):
            return device
    return None


def _expected_os_match(raw_os: Any, expected_os: Any) -> bool:
    raw = _as_text(raw_os).lower()
    expected = _as_text(expected_os).lower()
    return bool(expected and (raw == expected or expected in raw))


def _normalize_os(raw_os: Any, expected_os: Any) -> str:
    expected = _as_text(expected_os).lower()
    if _expected_os_match(raw_os, expected):
        return expected
    return _as_text(raw_os).lower()


def _primary_binding_for_requester(device: dict[str, Any], requester_key: str) -> dict[str, Any] | None:
    bindings = device.get("bindings") or []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        if binding.get("status") != "active" or binding.get("relationship_type") != "primary_user":
            continue
        person = binding.get("person") if isinstance(binding.get("person"), dict) else {}
        if requester_key in _person_key_candidates(person):
            return binding
    return None


def _manual_review(device: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(device.get("device_metadata"))
    review = metadata.get("manual_contamination_review") or metadata.get("phase_e_contamination_review")
    return review if isinstance(review, dict) else {}


def _module_snapshot(device: dict[str, Any]) -> dict[str, Any]:
    snapshot = device.get("toolset_snapshot") if isinstance(device.get("toolset_snapshot"), dict) else {}
    tools = snapshot.get("tools")
    payload: dict[str, Any] = {
        "collected": bool(snapshot),
        "snapshot_id": snapshot.get("snapshot_id"),
        "captured_at": snapshot.get("captured_at"),
        "module_count": int(snapshot.get("tool_count") or 0),
    }
    if isinstance(tools, list):
        payload["modules"] = tools
    return payload


def build_phase_e_vm_snapshot(
    pack: dict[str, Any],
    inventory: dict[str, Any],
    *,
    collected_at: str | None = None,
    source: str = "live_db_readonly",
) -> dict[str, Any]:
    devices = [item for item in inventory.get("devices", []) if isinstance(item, dict)]
    runtime = inventory.get("runtime") if isinstance(inventory.get("runtime"), dict) else {}
    connected_device_ids = {_as_text(item) for item in runtime.get("connected_device_ids", []) if _as_text(item)}

    agents: list[dict[str, Any]] = []
    missing: list[str] = []
    for required in pack.get("vm_agents", []):
        key = _as_text(required.get("key"))
        if not key:
            continue
        device = _find_required_device(key, devices)
        if device is None:
            missing.append(key)
            continue

        requester_key = _as_text(required.get("bound_requester"))
        binding = _primary_binding_for_requester(device, requester_key)
        device_id = _as_text(device.get("device_id"))
        raw_os = device.get("os")
        agents.append(
            {
                "key": key,
                "os": _normalize_os(raw_os, required.get("os")),
                "device_id": device_id,
                "registry_device": {
                    "source": required.get("device_id_source") or "live_registry",
                    "device_id": device_id,
                    "hostname": device.get("hostname"),
                    "os": raw_os,
                    "agent_version": device.get("agent_version"),
                },
                "bound_requester": requester_key if binding is not None else None,
                "primary_active_binding": binding is not None,
                "agent_online": device_id in connected_device_ids,
                "module_snapshot": _module_snapshot(device),
                "manual_contamination_review": _manual_review(device),
            }
        )

    return {
        "schema": "web_first_phase_e_vm_snapshot_v1",
        "collected_at": collected_at or _now_iso(),
        "source": source,
        "agents": agents,
        "missing_required_agents": missing,
        "runtime": {
            "source": runtime.get("source"),
            "snapshot_id": runtime.get("snapshot_id"),
            "connected_device_ids": sorted(connected_device_ids),
        },
        "observed_device_count": len(devices),
    }


async def collect_inventory_from_db(database_url: str | None = None) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db import get_session, init_db, shutdown_db
    from app.db.models import Device, DeviceToolsetSnapshot, DeviceUserBinding, RegistryPerson, ServerRuntimeSnapshot
    from config import DATABASE_URL

    await init_db(database_url or DATABASE_URL)
    try:
        async with get_session() as session:
            devices = (await session.execute(select(Device).where(Device.deleted_at.is_(None)))).scalars().all()
            runtime_row = (
                await session.execute(
                    select(ServerRuntimeSnapshot)
                    .where(ServerRuntimeSnapshot.process_kind == "server")
                    .order_by(ServerRuntimeSnapshot.collected_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            device_ids = [device.device_id for device in devices]
            bindings_by_device: dict[str, list[Any]] = {device_id: [] for device_id in device_ids}
            people_by_id: dict[str, Any] = {}
            snapshots_by_device: dict[str, Any] = {}
            if device_ids:
                bindings = (
                    await session.execute(select(DeviceUserBinding).where(DeviceUserBinding.device_id.in_(device_ids)))
                ).scalars().all()
                person_ids = sorted({_as_text(binding.person_id) for binding in bindings if _as_text(binding.person_id)})
                if person_ids:
                    people = (await session.execute(select(RegistryPerson).where(RegistryPerson.person_id.in_(person_ids)))).scalars().all()
                    people_by_id = {person.person_id: person for person in people}
                for binding in bindings:
                    bindings_by_device.setdefault(binding.device_id, []).append(binding)

                snapshots = (
                    await session.execute(
                        select(DeviceToolsetSnapshot)
                        .where(DeviceToolsetSnapshot.device_id.in_(device_ids))
                        .order_by(DeviceToolsetSnapshot.device_id, DeviceToolsetSnapshot.captured_at.desc())
                    )
                ).scalars().all()
                for snapshot in snapshots:
                    snapshots_by_device.setdefault(snapshot.device_id, snapshot)

            runtime_payload = runtime_row.snapshot if runtime_row is not None else {}
            connected = runtime_payload.get("connected_agents") if isinstance(runtime_payload, dict) else {}
            connected_device_ids = list(connected.keys()) if isinstance(connected, dict) else []
            return {
                "runtime": {
                    "source": "server_runtime_snapshots",
                    "snapshot_id": runtime_row.id if runtime_row is not None else None,
                    "connected_device_ids": connected_device_ids,
                },
                "devices": [
                    _device_to_inventory(
                        device,
                        bindings_by_device.get(device.device_id, []),
                        people_by_id,
                        snapshots_by_device.get(device.device_id),
                    )
                    for device in devices
                ],
            }
    finally:
        await shutdown_db()


def _device_to_inventory(device: Any, bindings: list[Any], people_by_id: dict[str, Any], snapshot: Any | None) -> dict[str, Any]:
    return {
        "device_id": device.device_id,
        "hostname": device.hostname,
        "os": device.os,
        "agent_version": device.agent_version,
        "device_metadata": device.device_metadata or {},
        "bindings": [
            {
                "relationship_type": binding.relationship_type,
                "status": binding.status,
                "person": _person_to_inventory(people_by_id.get(binding.person_id)),
            }
            for binding in bindings
        ],
        "toolset_snapshot": _toolset_to_inventory(snapshot),
    }


def _person_to_inventory(person: Any | None) -> dict[str, Any]:
    if person is None:
        return {}
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "email": person.email,
        "external_id": person.external_id,
        "profile_key": person.profile_key,
        "metadata_json": person.metadata_json or {},
    }


def _toolset_to_inventory(snapshot: Any | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    toolset = snapshot.toolset_json or {}
    tools = toolset.get("tools") if isinstance(toolset, dict) else None
    return {
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
        "tool_count": snapshot.tool_count,
        "tools": tools if isinstance(tools, list) else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect read-only Phase E VM-agent snapshot evidence.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK_PATH)
    parser.add_argument("--inventory-json", type=Path, help="Use pre-collected inventory JSON instead of project DB.")
    parser.add_argument("--database-url", default=None, help="DATABASE_URL override. Defaults to env/server/.env.")
    parser.add_argument("--output", type=Path, help="Write snapshot JSON to this path.")
    parser.add_argument("--json", action="store_true", help="Print snapshot JSON to stdout.")
    args = parser.parse_args(argv)

    pack = _load_json(args.pack)
    inventory = (
        _load_json(args.inventory_json)
        if args.inventory_json
        else asyncio.run(collect_inventory_from_db(args.database_url))
    )
    snapshot = build_phase_e_vm_snapshot(pack, inventory)
    rendered = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.json or not args.output:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
