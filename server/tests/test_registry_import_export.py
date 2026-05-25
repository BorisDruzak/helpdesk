from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceInventoryBinding, RegistryAdminEvent, RegistryAsset, RegistryDepartment, RegistryLocation, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str, *, hostname: str = "import-pc") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname=hostname,
        os="Windows 11",
        capabilities={},
        device_metadata={"machine_id": device_id},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_registry_export_devices_and_people_csv(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Export User", full_name="Export User", source="manual", status="active")
        session.add(person)
        await session.flush()

        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="export-pc",
            hostname="export-pc",
            device_id=device_id,
            assigned_person_id=person.person_id,
            source="manual",
            status="active",
            discovery_payload={"agent_version": "3.1.59"},
        )
        session.add(asset)
        await session.flush()
        devices_csv = await RegistryAdminOperationsService(session).export_csv("devices")
        people_csv = await RegistryAdminOperationsService(session).export_csv("people")
        await session.commit()

    assert "device_id,hostname,active_person_name" in devices_csv
    assert device_id in devices_csv
    assert "person_id,full_name,display_name" in people_csv
    assert "Export User" in people_csv


@pytest.mark.asyncio
async def test_registry_people_import_preview_detects_errors_duplicates_and_apply_is_atomic(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    existing_id = str(uuid.uuid4())
    duplicate_csv = (
        "display_name,full_name,email,phone,status\n"
        "Imported User,Imported User Full,imported@example.test,+70000000001,active\n"
        ",Missing Name,missing@example.test,+70000000002,active\n"
        "Existing Mail,Existing Mail,existing@example.test,+70000000003,active\n"
        "File Duplicate A,File Duplicate A,filedup@example.test,+70000000004,active\n"
        "File Duplicate B,File Duplicate B,filedup@example.test,+70000000005,active\n"
    )
    clean_csv = (
        "person_id,display_name,full_name,email,phone,status\n"
        f"{existing_id},Existing Updated,Existing Updated,existing@example.test,+70000000999,active\n"
        ",Clean Import,Clean Import,clean@example.test,+70000000006,active\n"
    )

    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id=existing_id,
                display_name="Existing User",
                full_name="Existing User",
                email="existing@example.test",
                source="manual",
                status="active",
            )
        )
        await session.flush()
        service = RegistryAdminOperationsService(session)

        preview = await service.preview_import_csv("people", duplicate_csv)
        assert preview["dry_run"] is True
        assert preview["counts"]["creates"] == 1
        assert preview["counts"]["updates"] == 0
        assert preview["counts"]["errors"] == 1
        assert preview["counts"]["duplicates"] == 3
        assert preview["row_errors"][0]["row"] == 3
        assert preview["duplicate_keys"]

        with pytest.raises(ValueError, match="preview_id is required"):
            await service.apply_import_csv("people", duplicate_csv, actor_id="admin", reason="bad import")

        with pytest.raises(ValueError, match="import has validation errors or duplicates"):
            await service.apply_import_csv(
                "people",
                duplicate_csv,
                preview_id=preview["preview_id"],
                actor_id="admin",
                reason="bad import",
            )

        people_count = await session.scalar(select(func.count()).select_from(RegistryPerson))
        assert people_count == 1

        clean_preview = await service.preview_import_csv("people", clean_csv)
        applied = await service.apply_import_csv(
            "people",
            clean_csv,
            preview_id=clean_preview["preview_id"],
            actor_id="admin",
            reason="people import",
        )
        await session.commit()

    async with session_maker() as session:
        updated = await session.get(RegistryPerson, existing_id)
        imported = (await session.execute(select(RegistryPerson).where(RegistryPerson.email == "clean@example.test"))).scalar_one()
        event = (await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "registry_import_applied"))).scalar_one()

    assert applied["dry_run"] is False
    assert applied["counts"]["creates"] == 1
    assert applied["counts"]["updates"] == 1
    assert applied["operation_id"]
    assert applied["status"] == "success"
    assert applied["summary"]["success"] == 2
    assert applied["items"] == [
        {"row": 2, "id": existing_id, "entity_type": "person", "status": "success", "error_code": None, "message": None},
        {"row": 3, "id": None, "entity_type": "person", "status": "success", "error_code": None, "message": None},
    ]
    assert updated.display_name == "Existing Updated"
    assert updated.phone == "+70000000999"
    assert imported.display_name == "Clean Import"
    assert event.reason == "people import"
    assert event.payload["import_type"] == "people"


@pytest.mark.asyncio
async def test_registry_locations_departments_import_preview_and_apply(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    duplicate_csv = (
        "building,floor,room,display_name,status,notes\n"
        "HQ,4,401,HQ 4 / 401,active,existing duplicate\n"
        ",5,501,No building,active,missing building\n"
        "HQ,5,501,HQ 5 / 501,active,new room\n"
    )
    clean_locations = "building,floor,room,display_name,status,notes\nHQ,6,601,HQ 6 / 601,active,new import\n"
    clean_departments = "code,name,support_queue,status,notes\nOPS,Operations,L2,active,ops import\n"

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        await service.create_location({"building": "HQ", "floor": "4", "room": "401", "reason": "seed"}, actor_id="admin")
        await session.flush()

        preview = await service.preview_import_csv("locations", duplicate_csv)
        assert preview["counts"]["creates"] == 1
        assert preview["counts"]["duplicates"] == 1
        assert preview["counts"]["errors"] == 1

        locations_preview = await service.preview_import_csv("locations", clean_locations)
        departments_preview = await service.preview_import_csv("departments", clean_departments)
        locations = await service.apply_import_csv(
            "locations",
            clean_locations,
            preview_id=locations_preview["preview_id"],
            actor_id="admin",
            reason="locations import",
        )
        departments = await service.apply_import_csv(
            "departments",
            clean_departments,
            preview_id=departments_preview["preview_id"],
            actor_id="admin",
            reason="departments import",
        )
        await session.commit()

    async with session_maker() as session:
        location = (await session.execute(select(RegistryLocation).where(RegistryLocation.room == "601"))).scalar_one()
        department = (await session.execute(select(RegistryDepartment).where(RegistryDepartment.code == "OPS"))).scalar_one()
        events = (await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "registry_import_applied"))).scalars().all()

    assert locations["counts"]["creates"] == 1
    assert departments["counts"]["creates"] == 1
    assert location.display_name == "HQ 6 / 601"
    assert department.name == "Operations"
    assert {event.payload["import_type"] for event in events} == {"locations", "departments"}


@pytest.mark.asyncio
async def test_registry_device_inventory_mapping_import_updates_asset_inventory_and_blocks_bad_rows(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    csv_with_error = (
        "device_id,hostname,location_id,department_id,building,floor,room,department,responsible_user,inventory_number,status,tags,notes\n"
        f"{device_id},import-pc,LOC_ID,DEPT_ID,HQ,7,701,Support,Ivan,INV-1,active,\"shared;laptop\",normal\n"
        f"{uuid.uuid4()},missing-pc,LOC_ID,DEPT_ID,HQ,8,801,Support,Petr,INV-2,active,,missing\n"
    )

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        location = (await service.create_location({"building": "HQ", "floor": "7", "room": "701", "reason": "seed"}, actor_id="admin"))["location"]
        department = (await service.create_department({"code": "SUP", "name": "Support", "reason": "seed"}, actor_id="admin"))["department"]
        session.add(_device(device_id, hostname="import-pc"))
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="import-pc",
            hostname="import-pc",
            device_id=device_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        session.add(asset)
        await session.flush()
        csv_text = csv_with_error.replace("LOC_ID", location["location_id"]).replace("DEPT_ID", department["department_id"])

        preview = await service.preview_import_csv("device_inventory_mapping", csv_text)
        assert preview["counts"]["updates"] == 1
        assert preview["counts"]["errors"] == 1

        bad_preview = await service.preview_import_csv("device_inventory_mapping", csv_text)
        with pytest.raises(ValueError):
            await service.apply_import_csv(
                "device_inventory_mapping",
                csv_text,
                preview_id=bad_preview["preview_id"],
                actor_id="admin",
                reason="bad mapping",
            )

        clean_csv = "\n".join(csv_text.splitlines()[:2]) + "\n"
        clean_preview = await service.preview_import_csv("device_inventory_mapping", clean_csv)
        applied = await service.apply_import_csv(
            "device_inventory_mapping",
            clean_csv,
            preview_id=clean_preview["preview_id"],
            actor_id="admin",
            reason="mapping import",
        )
        await session.commit()

    async with session_maker() as session:
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory = await session.get(DeviceInventoryBinding, device_id)
        event = (
            await session.execute(
                select(RegistryAdminEvent).where(
                    RegistryAdminEvent.event_type == "registry_import_applied",
                    RegistryAdminEvent.payload["import_type"].astext == "device_inventory_mapping",
                )
            )
        ).scalar_one()

    assert applied["counts"]["updates"] == 1
    assert asset_row.location_id == location["location_id"]
    assert asset_row.department_id == department["department_id"]
    assert inventory.room == "701"
    assert inventory.department == "Support"
    assert inventory.inventory_number == "INV-1"
    assert inventory.tags == ["shared", "laptop"]
    assert event.reason == "mapping import"


@pytest.mark.asyncio
async def test_registry_import_api_rejects_binding_import_without_preview(test_client):
    response = await test_client.post(
        "/api/web/admin/registry/import/preview",
        json={"type": "bindings", "format": "csv", "csv_text": "binding_id,device_id\n1,2\n"},
        headers=ADMIN_HEADERS,
    )
    assert response.status == 400
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_registry_import_api_requires_matching_preview_id(test_client):
    csv_text = "display_name,email\nPreview Required,preview-required@example.test\n"
    preview_response = await test_client.post(
        "/api/web/admin/registry/import/preview",
        json={"type": "people", "format": "csv", "csv_text": csv_text},
        headers=ADMIN_HEADERS,
    )
    assert preview_response.status == 200
    preview_payload = await preview_response.json()
    preview_id = preview_payload["data"]["preview_id"]

    missing_response = await test_client.post(
        "/api/web/admin/registry/import/apply",
        json={"type": "people", "format": "csv", "csv_text": csv_text, "reason": "people import"},
        headers=ADMIN_HEADERS,
    )
    assert missing_response.status == 400
    missing_payload = await missing_response.json()
    assert missing_payload["error_code"] == "VALIDATION_ERROR"

    wrong_response = await test_client.post(
        "/api/web/admin/registry/import/apply",
        json={
            "type": "people",
            "format": "csv",
            "csv_text": csv_text,
            "preview_id": "wrong-preview",
            "reason": "people import",
        },
        headers=ADMIN_HEADERS,
    )
    assert wrong_response.status == 400
    wrong_payload = await wrong_response.json()
    assert wrong_payload["error_code"] == "VALIDATION_ERROR"

    apply_response = await test_client.post(
        "/api/web/admin/registry/import/apply",
        json={
            "type": "people",
            "format": "csv",
            "csv_text": csv_text,
            "preview_id": preview_id,
            "reason": "people import",
        },
        headers=ADMIN_HEADERS,
    )
    assert apply_response.status == 200
    apply_payload = await apply_response.json()
    assert apply_payload["data"]["operation_id"]
    assert apply_payload["data"]["items"][0]["status"] == "success"
