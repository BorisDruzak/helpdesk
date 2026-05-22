from __future__ import annotations

from datetime import datetime, timezone
import uuid

from aiohttp import web
from loguru import logger
from pydantic import ValidationError

from app.db import get_session
from auth.middleware import require_auth
from inventory.service import DeviceInventoryService
from presence.service import DevicePresenceService, PRESENCE_TOOL_ID
from tools.service import ToolExecutionService
from web_api.dto.admin import (
    AdminBindingSuggestionApplyRequest,
    AdminBindingSuggestionItem,
    AdminBindingSuggestionReviewRequest,
    AdminBulkOperationsPayload,
    AdminBulkOperationSummary,
    AdminBulkRefreshRequest,
    AdminBulkRefreshResult,
    AdminDeviceInventoryBinding,
    AdminDeviceInventoryBindingHistoryItem,
    AdminDeviceInventoryBindingUpdateRequest,
    AdminDeviceInventoryCollectPayload,
    AdminDeviceInventoryHistoryItem,
    AdminDeviceInventoryLatestSnapshot,
    AdminDeviceInventoryPayload,
    AdminDeviceInventoryRefreshPolicy,
    AdminDeviceInventoryRefreshPolicyUpdateRequest,
    AdminDeviceInventoryRefreshRun,
    AdminDevicePresencePayload,
    AdminDeviceProfileItem,
    AdminInventoryBindingImportRequest,
    AdminInventoryBindingImportResult,
    AdminInventoryDashboardPayload,
)
from web_api.dto.common import SuccessResponse, json_model_response


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _actor_id(request: web.Request) -> str | None:
    auth_context = request.get("auth_context")
    return getattr(auth_context, "actor_id", None) if auth_context else None


def _inventory_history_item(row) -> AdminDeviceInventoryHistoryItem:
    return AdminDeviceInventoryHistoryItem(
        id=str(getattr(row, "id", "") or ""),
        collected_at=_iso(getattr(row, "collected_at", None)) or "",
        status=str(getattr(row, "status", "") or "ok"),
        summary=getattr(row, "summary", None),
    )


def _inventory_binding_item(device_id: str, row) -> AdminDeviceInventoryBinding:
    return AdminDeviceInventoryBinding(
        device_id=device_id,
        person_id=getattr(row, "person_id", None) if row is not None else None,
        asset_id=getattr(row, "asset_id", None) if row is not None else None,
        source_binding_id=getattr(row, "source_binding_id", None) if row is not None else None,
        registration_status=getattr(row, "registration_status", None) if row is not None else None,
        building=getattr(row, "building", None) if row is not None else None,
        floor=getattr(row, "floor", None) if row is not None else None,
        room=getattr(row, "room", None) if row is not None else None,
        department=getattr(row, "department", None) if row is not None else None,
        responsible_user=getattr(row, "responsible_user", None) if row is not None else None,
        responsible_user_login=getattr(row, "responsible_user_login", None) if row is not None else None,
        inventory_number=getattr(row, "inventory_number", None) if row is not None else None,
        status=getattr(row, "status", None) if row is not None else None,
        tags=list(getattr(row, "tags", []) or []) if row is not None else [],
        notes=getattr(row, "notes", None) if row is not None else None,
        updated_at=_iso(getattr(row, "updated_at", None)) if row is not None else None,
        updated_by=getattr(row, "updated_by", None) if row is not None else None,
    )


def _binding_history_item(row) -> AdminDeviceInventoryBindingHistoryItem:
    return AdminDeviceInventoryBindingHistoryItem(
        changed_at=_iso(getattr(row, "changed_at", None)) or "",
        changed_by=getattr(row, "changed_by", None),
        changed_fields=[str(item) for item in (getattr(row, "changed_fields", None) or [])],
        old_binding=getattr(row, "old_binding", None),
        new_binding=dict(getattr(row, "new_binding", None) or {}),
        reason=getattr(row, "reason", None),
    )


def _refresh_run_item(row) -> AdminDeviceInventoryRefreshRun:
    return AdminDeviceInventoryRefreshRun(
        id=str(getattr(row, "id", "") or ""),
        device_id=getattr(row, "device_id", None),
        policy_id=getattr(row, "policy_id", None),
        bulk_operation_id=getattr(row, "bulk_operation_id", None),
        requested_at=_iso(getattr(row, "requested_at", None)) or "",
        requested_by=getattr(row, "requested_by", None),
        status=str(getattr(row, "status", "") or "requested"),
        job_id=getattr(row, "job_id", None),
        error=getattr(row, "error", None),
        completed_at=_iso(getattr(row, "completed_at", None)),
    )


def _binding_suggestion_item(row) -> AdminBindingSuggestionItem:
    return AdminBindingSuggestionItem(
        id=str(getattr(row, "id", "") or ""),
        device_id=str(getattr(row, "device_id", "") or ""),
        source=str(getattr(row, "source", "") or "agent_profile"),
        source_ref=getattr(row, "source_ref", None),
        suggested_binding=dict(getattr(row, "suggested_binding", None) or {}),
        profile_snapshot=dict(getattr(row, "profile_snapshot", None) or {}),
        status=str(getattr(row, "status", "") or "pending"),
        confidence=getattr(row, "confidence", None),
        created_at=_iso(getattr(row, "created_at", None)) or "",
        updated_at=_iso(getattr(row, "updated_at", None)) or "",
        reviewed_by=getattr(row, "reviewed_by", None),
        reviewed_at=_iso(getattr(row, "reviewed_at", None)),
        review_note=getattr(row, "review_note", None),
    )


def _bulk_operation_summary(row) -> AdminBulkOperationSummary:
    return AdminBulkOperationSummary(
        id=str(getattr(row, "id", "") or ""),
        operation_type=str(getattr(row, "operation_type", "") or "inventory_refresh"),
        status=str(getattr(row, "status", "") or "planned"),
        requested_by=getattr(row, "requested_by", None),
        requested_at=_iso(getattr(row, "requested_at", None)) or "",
        filters=dict(getattr(row, "filters", None) or {}),
        wave=dict(getattr(row, "wave", None) or {}),
        total_count=int(getattr(row, "total_count", 0) or 0),
        dispatched_count=int(getattr(row, "dispatched_count", 0) or 0),
        skipped_count=int(getattr(row, "skipped_count", 0) or 0),
        failed_count=int(getattr(row, "failed_count", 0) or 0),
        completed_at=_iso(getattr(row, "completed_at", None)),
    )


def _presence_payload_item(payload: dict) -> AdminDevicePresencePayload:
    return AdminDevicePresencePayload.model_validate(payload)


def _inventory_refresh_policy_item(
    row,
    *,
    scope: str = "global",
    device_id: str | None = None,
) -> AdminDeviceInventoryRefreshPolicy:
    if row is None:
        return AdminDeviceInventoryRefreshPolicy(
            id=None,
            scope=scope,
            device_id=device_id if scope == "device" else None,
            enabled=False,
            interval_minutes=1440,
            jitter_minutes=30,
        )
    return AdminDeviceInventoryRefreshPolicy(
        id=str(getattr(row, "id", "") or "") or None,
        scope=str(getattr(row, "scope", "") or scope),
        device_id=getattr(row, "device_id", None),
        enabled=bool(getattr(row, "enabled", False)),
        interval_minutes=int(getattr(row, "interval_minutes", 1440) or 1440),
        jitter_minutes=int(getattr(row, "jitter_minutes", 30) or 0),
        last_requested_at=_iso(getattr(row, "last_requested_at", None)),
        next_due_at=_iso(getattr(row, "next_due_at", None)),
        updated_at=_iso(getattr(row, "updated_at", None)),
        updated_by=getattr(row, "updated_by", None),
    )


async def _inventory_latest_item(service: DeviceInventoryService, row) -> AdminDeviceInventoryLatestSnapshot:
    presentation = await service.resolve_inventory_presentation(
        tool_id=str(getattr(row, "source_tool", None) or "inventory.collect")
    )
    return AdminDeviceInventoryLatestSnapshot(
        id=str(getattr(row, "id", "") or ""),
        source_tool=str(getattr(row, "source_tool", "") or "inventory.collect"),
        collected_at=_iso(getattr(row, "collected_at", None)) or "",
        status=str(getattr(row, "status", "") or "ok"),
        summary=getattr(row, "summary", None),
        result=dict(getattr(row, "snapshot", None) or {}),
        presentation_schema=presentation["presentation_schema"],
        effective_presentation_schema=presentation["effective_presentation_schema"],
        presentation_schema_source=presentation["presentation_schema_source"],
        device_card_slots=presentation["device_card_slots"],
    )


def _csv_response(csv_text: str, filename: str) -> web.Response:
    return web.Response(
        text=csv_text,
        content_type="text/csv",
        charset="utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(payload: bytes, filename: str) -> web.Response:
    return web.Response(
        body=payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@require_auth("admin")
async def handle_web_admin_device_inventory(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            latest = await service.get_latest(device_id)
            history_rows = await service.list_history(device_id)
            binding_row = await service.get_binding(device_id)
            binding_history_rows = await service.list_binding_history(device_id)
            refresh_policy = await service.get_effective_refresh_policy(device_id)
            refresh_run_rows = await service.list_refresh_runs(device_id=device_id, limit=20)
            profiles = await service.list_device_profiles(device_id)
            suggestions = await service.list_binding_suggestions(device_id, include_reviewed=True)
            presence_payload = await DevicePresenceService(session).build_device_payload(device_id)
            latest_payload = await _inventory_latest_item(service, latest) if latest is not None else None
            refresh_runs = [_refresh_run_item(row) for row in refresh_run_rows]
            payload = AdminDeviceInventoryPayload(
                device_id=device_id,
                latest_snapshot=latest_payload,
                history=[_inventory_history_item(row) for row in history_rows],
                binding=_inventory_binding_item(device_id, binding_row),
                binding_history=[_binding_history_item(row) for row in binding_history_rows],
                refresh_policy=_inventory_refresh_policy_item(
                    refresh_policy,
                    scope=getattr(refresh_policy, "scope", "global") if refresh_policy else "global",
                    device_id=device_id if getattr(refresh_policy, "scope", None) == "device" else None,
                ),
                refresh_runs=refresh_runs,
                last_refresh_run=refresh_runs[0] if refresh_runs else None,
                profiles=[AdminDeviceProfileItem.model_validate(item) for item in profiles],
                binding_suggestions=[_binding_suggestion_item(row) for row in suggestions],
                presence=_presence_payload_item(presence_payload),
            )
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить инвентарь устройства",
                "error_code": "ADMIN_DEVICE_INVENTORY_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_inventory_binding(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.get_binding(device_id)
            payload = _inventory_binding_item(device_id, row)
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_binding] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить привязку устройства",
                "error_code": "ADMIN_DEVICE_BINDING_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryBinding](data=payload))


@require_auth("admin")
async def handle_web_admin_device_inventory_binding_update(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        raw_payload = await request.json()
        if isinstance(raw_payload, dict) and isinstance(raw_payload.get("binding"), dict):
            binding_payload = raw_payload["binding"]
            reason = raw_payload.get("reason")
        else:
            binding_payload = raw_payload
            reason = raw_payload.get("reason") if isinstance(raw_payload, dict) else None
        payload = AdminDeviceInventoryBindingUpdateRequest.model_validate(binding_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Некорректные поля привязки устройства",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.upsert_binding(
                device_id,
                payload.model_dump(),
                updated_by=_actor_id(request),
                reason=reason,
            )
            await session.commit()
            result = _inventory_binding_item(device_id, row)
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_binding_update] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сохранить привязку устройства",
                "error_code": "ADMIN_DEVICE_BINDING_SAVE_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryBinding](data=result))


@require_auth("admin")
async def handle_web_admin_device_inventory_binding_history(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            rows = await service.list_binding_history(device_id)
            payload = {"device_id": device_id, "items": [_binding_history_item(row).model_dump() for row in rows]}
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_binding_history] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить историю привязки",
                "error_code": "ADMIN_DEVICE_BINDING_HISTORY_FAILED",
            },
            status=500,
        )
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin")
async def handle_web_admin_device_profiles(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            profiles = await DeviceInventoryService(session).list_device_profiles(device_id)
            payload = {"device_id": device_id, "profiles": [AdminDeviceProfileItem.model_validate(item).model_dump() for item in profiles]}
    except Exception as exc:
        logger.warning(f"[web_admin_device_profiles] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось загрузить профили агента", "error_code": "ADMIN_DEVICE_PROFILES_FAILED"},
            status=500,
        )
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin")
async def handle_web_admin_device_binding_suggestions(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            rows = await DeviceInventoryService(session).list_binding_suggestions(device_id, include_reviewed=True)
            payload = {"device_id": device_id, "items": [_binding_suggestion_item(row).model_dump() for row in rows]}
    except Exception as exc:
        logger.warning(f"[web_admin_device_binding_suggestions] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось загрузить предложения привязки", "error_code": "ADMIN_BINDING_SUGGESTIONS_FAILED"},
            status=500,
        )
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin")
async def handle_web_admin_device_binding_suggestion_apply(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    suggestion_id = str(request.match_info.get("suggestion_id") or "").strip()
    try:
        payload = AdminBindingSuggestionApplyRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response({"status": "error", "error": "Некорректное применение предложения", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            row = await DeviceInventoryService(session).apply_binding_suggestion(
                device_id=device_id,
                suggestion_id=suggestion_id,
                fields=payload.fields,
                reviewed_by=_actor_id(request),
                reason=payload.reason,
            )
            await session.commit()
            result = _binding_suggestion_item(row)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    except Exception as exc:
        logger.warning(f"[web_admin_device_binding_suggestion_apply] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось применить предложение привязки", "error_code": "ADMIN_BINDING_SUGGESTION_APPLY_FAILED"},
            status=500,
        )
    return json_model_response(SuccessResponse[AdminBindingSuggestionItem](data=result))


@require_auth("admin")
async def handle_web_admin_device_binding_suggestion_ignore(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    suggestion_id = str(request.match_info.get("suggestion_id") or "").strip()
    try:
        payload = AdminBindingSuggestionReviewRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response({"status": "error", "error": "Некорректное отклонение предложения", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            row = await DeviceInventoryService(session).ignore_binding_suggestion(
                device_id=device_id,
                suggestion_id=suggestion_id,
                reviewed_by=_actor_id(request),
                reason=payload.reason,
            )
            await session.commit()
            result = _binding_suggestion_item(row)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    except Exception as exc:
        logger.warning(f"[web_admin_device_binding_suggestion_ignore] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось игнорировать предложение привязки", "error_code": "ADMIN_BINDING_SUGGESTION_IGNORE_FAILED"},
            status=500,
        )
    return json_model_response(SuccessResponse[AdminBindingSuggestionItem](data=result))


@require_auth("admin")
async def handle_web_admin_inventory_bindings_import(request: web.Request):
    try:
        payload = AdminInventoryBindingImportRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response(
            {"status": "error", "error": "Некорректный CSV импорт привязок", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            result = await service.import_bindings_csv(
                payload.csv_text,
                dry_run=payload.dry_run,
                updated_by=_actor_id(request),
                reason=payload.reason,
            )
            if not payload.dry_run:
                await session.commit()
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_bindings_import] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось импортировать привязки",
                "error_code": "ADMIN_INVENTORY_BINDINGS_IMPORT_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminInventoryBindingImportResult](data=AdminInventoryBindingImportResult.model_validate(result)))


@require_auth("admin")
async def handle_web_admin_inventory_bindings_export_csv(request: web.Request):
    try:
        async with get_session() as session:
            csv_text = await DeviceInventoryService(session).export_bindings_csv()
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_bindings_export_csv] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось экспортировать привязки",
                "error_code": "ADMIN_INVENTORY_BINDINGS_EXPORT_FAILED",
            },
            status=500,
        )
    return _csv_response(csv_text, "inventory-bindings.csv")


@require_auth("admin")
async def handle_web_admin_inventory_export_csv(request: web.Request):
    try:
        stale_days = int(request.query.get("stale_days") or 7)
        building = request.query.get("building")
        department = request.query.get("department")
        missing_binding = request.query.get("missing_binding")
        has_snapshot = request.query.get("has_snapshot")
        async with get_session() as session:
            csv_text = await DeviceInventoryService(session).export_inventory_csv(
                stale_days=stale_days,
                building=building or None,
                department=department or None,
                missing_binding=(missing_binding.lower() == "true") if missing_binding is not None else None,
                has_snapshot=(has_snapshot.lower() == "true") if has_snapshot is not None else None,
            )
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_export_csv] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось экспортировать инвентарь",
                "error_code": "ADMIN_INVENTORY_EXPORT_FAILED",
            },
            status=500,
        )
    return _csv_response(csv_text, "inventory.csv")


@require_auth("admin")
async def handle_web_admin_inventory_export_xlsx(request: web.Request):
    try:
        stale_days = int(request.query.get("stale_days") or 7)
        async with get_session() as session:
            payload = await DeviceInventoryService(session).export_inventory_xlsx(stale_days=stale_days)
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_export_xlsx] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось экспортировать Excel инвентаря",
                "error_code": "ADMIN_INVENTORY_XLSX_EXPORT_FAILED",
            },
            status=500,
        )
    return _xlsx_response(payload, "inventory.xlsx")


@require_auth("admin")
async def handle_web_admin_inventory_dashboard(request: web.Request):
    try:
        stale_days = int(request.query.get("stale_days") or 7)
        async with get_session() as session:
            service = DeviceInventoryService(session)
            result = await service.build_dashboard(stale_days=stale_days)
            result["attention"] = await service.list_attention_items(stale_days=stale_days)
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_dashboard] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить сводку парка",
                "error_code": "ADMIN_INVENTORY_DASHBOARD_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminInventoryDashboardPayload](data=AdminInventoryDashboardPayload.model_validate(result)))


@require_auth("admin")
async def handle_web_admin_inventory_report(request: web.Request):
    try:
        report_type = request.query.get("type") or request.match_info.get("report_type") or "attention"
        stale_days = int(request.query.get("stale_days") or 7)
        async with get_session() as session:
            result = await DeviceInventoryService(session).build_report(report_type=report_type, stale_days=stale_days)
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_report] failed: error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось загрузить отчёт инвентаря", "error_code": "ADMIN_INVENTORY_REPORT_FAILED"},
            status=500,
        )
    return web.json_response({"status": "success", "data": result})


@require_auth("admin")
async def handle_web_admin_inventory_bulk_refresh(request: web.Request):
    try:
        payload = AdminBulkRefreshRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response(
            {"status": "error", "error": "Некорректный запрос массового обновления", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            preview = await service.bulk_refresh_preview(
                device_ids=payload.device_ids,
                mode=payload.mode,
                filters=payload.filters,
                wave=payload.wave,
            )
            if payload.dry_run:
                return json_model_response(SuccessResponse[AdminBulkRefreshResult](data=AdminBulkRefreshResult.model_validate(preview)))

            operation = await service.create_bulk_refresh_operation(
                preview=preview,
                mode=payload.mode,
                filters=payload.filters,
                wave=payload.wave,
                requested_by=_actor_id(request),
            )
            operation.status = "running"
            tool_service = ToolExecutionService(request.app["state"])
            items = await service.list_bulk_operation_items(operation.id)
            now = datetime.now(timezone.utc)
            for item in items:
                if item.status == "skipped_offline":
                    await service.record_refresh_run(
                        device_id=item.device_id,
                        bulk_operation_id=operation.id,
                        requested_at=now,
                        requested_by=_actor_id(request),
                        status="skipped_offline",
                        error=item.error,
                    )
                    continue
                if item.status != "pending":
                    continue
                operation_id = str(uuid.uuid4())
                try:
                    result = await tool_service.run_tool(
                        device_id=item.device_id,
                        ticket_id="",
                        tool_name="inventory.collect",
                        params={
                            "_operation_id": operation_id,
                            "source": "inventory_bulk_refresh",
                            "bulk_operation_id": operation.id,
                            "wave_index": item.wave_index,
                        },
                        call_id=str(uuid.uuid4()),
                        auth_context=request.get("auth_context"),
                        wait_for_result=False,
                    )
                except Exception as exc:
                    item.status = "failed"
                    item.error = str(exc)
                    operation.failed_count += 1
                    await service.record_refresh_run(
                        device_id=item.device_id,
                        bulk_operation_id=operation.id,
                        requested_at=now,
                        requested_by=_actor_id(request),
                        status="failed",
                        error=str(exc),
                    )
                    continue
                status = str(result.get("status") or "")
                accepted = status in {"accepted", "queued", "sent", "waiting_consent"}
                item.requested_at = now
                if accepted:
                    item.status = "dispatched"
                    item.job_id = str(result.get("operation_id") or operation_id)
                    operation.dispatched_count += 1
                    await service.record_refresh_run(
                        device_id=item.device_id,
                        bulk_operation_id=operation.id,
                        requested_at=now,
                        requested_by=_actor_id(request),
                        status="dispatched",
                        job_id=item.job_id,
                    )
                else:
                    item.status = "failed"
                    item.error = str(result.get("error") or status or "dispatch rejected")
                    operation.failed_count += 1
                    await service.record_refresh_run(
                        device_id=item.device_id,
                        bulk_operation_id=operation.id,
                        requested_at=now,
                        requested_by=_actor_id(request),
                        status="failed",
                        error=item.error,
                    )
            operation.status = "completed" if operation.failed_count == 0 else "failed"
            operation.completed_at = datetime.now(timezone.utc)
            await session.commit()
            response = {
                **preview,
                "dry_run": False,
                "operation_id": operation.id,
                "status": operation.status,
            }
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_bulk_refresh] failed: error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось запустить массовое обновление инвентаря", "error_code": "ADMIN_INVENTORY_BULK_REFRESH_FAILED"},
            status=500,
        )
    return json_model_response(SuccessResponse[AdminBulkRefreshResult](data=AdminBulkRefreshResult.model_validate(response)))


@require_auth("admin")
async def handle_web_admin_inventory_bulk_operations(request: web.Request):
    try:
        limit = int(request.query.get("limit") or 20)
        async with get_session() as session:
            rows = await DeviceInventoryService(session).list_bulk_operations(limit=limit)
            payload = AdminBulkOperationsPayload(items=[_bulk_operation_summary(row) for row in rows])
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_bulk_operations] failed: error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось загрузить массовые операции", "error_code": "ADMIN_INVENTORY_BULK_OPERATIONS_FAILED"},
            status=500,
        )
    return json_model_response(SuccessResponse[AdminBulkOperationsPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_inventory_refresh_runs(request: web.Request):
    try:
        device_id = request.query.get("device_id")
        limit = int(request.query.get("limit") or 50)
        async with get_session() as session:
            rows = await DeviceInventoryService(session).list_refresh_runs(device_id=device_id, limit=limit)
            payload = {"items": [_refresh_run_item(row).model_dump() for row in rows]}
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_refresh_runs] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить историю обновления инвентаря",
                "error_code": "ADMIN_INVENTORY_REFRESH_RUNS_FAILED",
            },
            status=500,
        )
    return web.json_response({"status": "success", "data": payload})


@require_auth("admin")
async def handle_web_admin_inventory_refresh_policy(request: web.Request):
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.get_refresh_policy(scope="global")
            payload = _inventory_refresh_policy_item(row, scope="global")
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_refresh_policy] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить политику обновления инвентаря",
                "error_code": "ADMIN_INVENTORY_REFRESH_POLICY_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryRefreshPolicy](data=payload))


@require_auth("admin")
async def handle_web_admin_inventory_refresh_policy_update(request: web.Request):
    try:
        payload = AdminDeviceInventoryRefreshPolicyUpdateRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response(
            {"status": "error", "error": "Некорректная политика обновления инвентаря", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.upsert_refresh_policy(
                scope="global",
                enabled=payload.enabled,
                interval_minutes=payload.interval_minutes,
                jitter_minutes=payload.jitter_minutes,
                updated_by=_actor_id(request),
            )
            await session.commit()
            result = _inventory_refresh_policy_item(row, scope="global")
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_inventory_refresh_policy_update] failed: error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сохранить политику обновления инвентаря",
                "error_code": "ADMIN_INVENTORY_REFRESH_POLICY_SAVE_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryRefreshPolicy](data=result))


@require_auth("admin")
async def handle_web_admin_device_inventory_refresh_policy(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.get_effective_refresh_policy(device_id)
            payload = _inventory_refresh_policy_item(
                row,
                scope=getattr(row, "scope", "global") if row else "global",
                device_id=device_id if getattr(row, "scope", None) == "device" else None,
            )
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_refresh_policy] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить расписание инвентаря",
                "error_code": "ADMIN_DEVICE_INVENTORY_REFRESH_POLICY_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryRefreshPolicy](data=payload))


@require_auth("admin")
async def handle_web_admin_device_inventory_refresh_policy_update(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        payload = AdminDeviceInventoryRefreshPolicyUpdateRequest.model_validate(await request.json())
    except (ValidationError, Exception):
        return web.json_response(
            {"status": "error", "error": "Некорректная политика обновления инвентаря", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    try:
        async with get_session() as session:
            service = DeviceInventoryService(session)
            row = await service.upsert_refresh_policy(
                scope="device",
                device_id=device_id,
                enabled=payload.enabled,
                interval_minutes=payload.interval_minutes,
                jitter_minutes=payload.jitter_minutes,
                updated_by=_actor_id(request),
            )
            await session.commit()
            result = _inventory_refresh_policy_item(row, scope="device", device_id=device_id)
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_refresh_policy_update] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось сохранить расписание инвентаря",
                "error_code": "ADMIN_DEVICE_INVENTORY_REFRESH_POLICY_SAVE_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDeviceInventoryRefreshPolicy](data=result))


@require_auth("admin")
async def handle_web_admin_device_inventory_collect(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    auth_context = request.get("auth_context")
    operation_id = str(uuid.uuid4())
    requested_at = datetime.now(timezone.utc)
    try:
        tool_service = ToolExecutionService(request.app["state"])
        result = await tool_service.run_tool(
            device_id=device_id,
            ticket_id="",
            tool_name="inventory.collect",
            params={"_operation_id": operation_id},
            call_id=str(uuid.uuid4()),
            auth_context=auth_context,
            wait_for_result=False,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_device_inventory_collect] dispatch failed: device_id={device_id} error={exc}")
        async with get_session() as session:
            await DeviceInventoryService(session).record_refresh_run(
                device_id=device_id,
                requested_at=requested_at,
                requested_by=_actor_id(request),
                status="failed",
                error=str(exc),
            )
            await session.commit()
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось отправить команду inventory.collect",
                "error_code": "ADMIN_DEVICE_INVENTORY_COLLECT_FAILED",
            },
            status=503,
        )

    status = str(result.get("status") or "accepted")
    accepted = status in {"accepted", "queued", "sent", "waiting_consent"}
    async with get_session() as session:
        await DeviceInventoryService(session).record_refresh_run(
            device_id=device_id,
            requested_at=requested_at,
            requested_by=_actor_id(request),
            status="dispatched" if accepted else "failed",
            job_id=str(result.get("operation_id") or operation_id) if accepted else None,
            error=None if accepted else str(result.get("error") or status or "dispatch rejected"),
        )
        await session.commit()
    if not accepted:
        return web.json_response(
            {
                "status": "error",
                "error": str(result.get("error") or "Не удалось поставить inventory.collect в очередь"),
                "error_code": str(result.get("error_code") or "ADMIN_DEVICE_INVENTORY_COLLECT_FAILED"),
            },
            status=503,
        )
    payload = AdminDeviceInventoryCollectPayload(
        device_id=device_id,
        tool_name="inventory.collect",
        operation_id=str(result.get("operation_id") or operation_id),
        status=status,
        message="Команда inventory.collect отправлена",
        poll_url=f"/api/operations/{result.get('operation_id') or operation_id}",
    )
    return json_model_response(SuccessResponse[AdminDeviceInventoryCollectPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_presence(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    try:
        async with get_session() as session:
            payload = AdminDevicePresencePayload.model_validate(await DevicePresenceService(session).build_device_payload(device_id))
    except Exception as exc:
        logger.warning(f"[web_admin_device_presence] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось загрузить присутствие рабочего места", "error_code": "ADMIN_DEVICE_PRESENCE_FAILED"},
            status=500,
        )
    return json_model_response(SuccessResponse[AdminDevicePresencePayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_presence_collect(request: web.Request):
    device_id = str(request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response({"status": "error", "error": "device_id is required", "error_code": "VALIDATION_ERROR"}, status=400)
    operation_id = str(uuid.uuid4())
    try:
        result = await ToolExecutionService(request.app["state"]).run_tool(
            device_id=device_id,
            ticket_id="",
            tool_name=PRESENCE_TOOL_ID,
            params={"_operation_id": operation_id},
            call_id=str(uuid.uuid4()),
            auth_context=request.get("auth_context"),
            wait_for_result=False,
        )
    except Exception as exc:
        logger.warning(f"[web_admin_device_presence_collect] dispatch failed: device_id={device_id} error={exc}")
        return web.json_response(
            {"status": "error", "error": "Не удалось отправить presence.collect", "error_code": "ADMIN_DEVICE_PRESENCE_COLLECT_FAILED"},
            status=503,
        )
    status = str(result.get("status") or "accepted")
    if status not in {"accepted", "queued", "sent", "waiting_consent"}:
        return web.json_response(
            {
                "status": "error",
                "error": str(result.get("error") or "Не удалось поставить presence.collect в очередь"),
                "error_code": str(result.get("error_code") or "ADMIN_DEVICE_PRESENCE_COLLECT_FAILED"),
            },
            status=503,
        )
    payload = AdminDeviceInventoryCollectPayload(
        device_id=device_id,
        tool_name=PRESENCE_TOOL_ID,
        operation_id=str(result.get("operation_id") or operation_id),
        status=status,
        message="Команда presence.collect отправлена",
        poll_url=f"/api/operations/{result.get('operation_id') or operation_id}",
    )
    return json_model_response(SuccessResponse[AdminDeviceInventoryCollectPayload](data=payload))
