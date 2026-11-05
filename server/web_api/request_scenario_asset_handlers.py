"""Bounded multipart uploads with explicit draft/session ownership."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from aiohttp import web
from loguru import logger
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select, func, or_

from app.db import get_session
from app.db.request_scenario_models import RequestStudioAsset, RequestStudioCategory, RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession
from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError
from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo, SessionAccessError
from auth.middleware import require_auth
from config import UPLOAD_DIR, ARTIFACT_MAX_BYTES
from tickets.request_scenario_assets import asset_metadata, material_references, safe_asset_name, session_assets
from tickets.request_scenario_conditions import evaluate_condition
from tickets.request_scenario_runtime import ScenarioConflict, ScenarioInputError
from uploads.handlers import _content_disposition_attachment
from web_api.dto.request_scenario import ScenarioAnswerRequest
from web_api.dto.request_scenario_admin import Identifier
from web_api.request_scenario_admin_handlers import _payload

RASTER_MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}


def _reply(data, status=200):
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store"})


async def _multipart(request, file_path):
    reader = await request.multipart()
    fields, info, parts = {}, None, 0
    async for part in reader:
        parts += 1
        if parts > 8 or not hasattr(part, "filename"):
            raise ScenarioAdminError("MULTIPART_INVALID")
        if part.filename is not None:
            if part.name != "file" or info is not None:
                raise ScenarioAdminError("ONE_FILE_REQUIRED")
            name, size, digest = safe_asset_name(part.filename), 0, hashlib.sha256()
            with file_path.open("xb") as output:
                while chunk := await part.read_chunk(65536):
                    size += len(chunk)
                    if size > ARTIFACT_MAX_BYTES:
                        raise ScenarioAdminError("FILE_TOO_LARGE", 413)
                    digest.update(chunk)
                    output.write(chunk)
            suffix = Path(name).suffix.lower()
            # Never trust user-supplied Content-Type for executable inline data.
            mime = RASTER_MIMES.get(suffix, {".pdf": "application/pdf", ".txt": "text/plain"}.get(suffix, "application/octet-stream"))
            info = {"name": name, "mime_type": mime, "size_bytes": size, "sha256": digest.hexdigest()}
        else:
            if part.name in fields or part.name not in {"field_key", "expected_block_id", "revision", "answers", "block_id"}:
                raise ScenarioAdminError("MULTIPART_INVALID")
            data = bytearray()
            while chunk := await part.read_chunk(65536):
                data.extend(chunk)
                if len(data) > 65536:
                    raise ScenarioAdminError("PAYLOAD_TOO_LARGE", 413)
            fields[part.name] = data.decode("utf-8")
    if info is None:
        raise ScenarioAdminError("FILE_REQUIRED")
    return fields, info


async def _upload(request, author=False):
    path, uncertain = None, False
    try:
        identifier = TypeAdapter(Identifier).validate_python(request.match_info["identifier"])
        async with get_session() as session:
            auth = request["auth_context"]
            if author:
                repo = RequestScenarioRepo(session, auth)
                scenario, draft = await repo.detail(identifier, lock=True)
                if scenario.archived:
                    raise ScenarioAdminError("SCENARIO_UNAVAILABLE", 409)
                count = await session.scalar(select(func.count()).select_from(RequestStudioAsset).where(RequestStudioAsset.scenario_id == identifier))
                if count >= 1000:
                    raise ScenarioAdminError("ATTACHMENT_LIMIT", 409)
            else:
                repo = RequestScenarioSessionRepo(session, auth)
                row, runtime = await repo.load(identifier)
                if row.state != "active":
                    raise ScenarioConflict("Session is not active")
            asset_id = str(uuid.uuid4())
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            path = UPLOAD_DIR / ("studio_" + asset_id + ".bin")
            fields, info = await _multipart(request, path)
            scope = {"scenario_id": identifier} if author else {"session_id": identifier}
            if not author:
                payload = ScenarioAnswerRequest.model_validate({"expected_block_id": fields.get("expected_block_id"),
                    "revision": int(fields.get("revision", "0")), "answers": json.loads(fields.get("answers", "{}"))})
                state = runtime.preview_answers(repo._state(row), payload)
                field = next((item for item in getattr(runtime.blocks[state.current_block_id], "fields", ())
                    if item.key == fields.get("field_key") and item.type in {"text", "textarea"}
                    and evaluate_condition(item.visible_when, state.answers)), None)
                if field is None:
                    raise ScenarioInputError({"field_key": "Choose a visible text field in the current page"})
                assets = await session_assets(session, identifier)
                if sum(item.block_id == state.current_block_id and item.field_key == field.key for item in assets) >= 10:
                    raise ScenarioAdminError("ATTACHMENT_LIMIT", 409)
                scope.update(block_id=state.current_block_id, field_key=field.key)
            asset = RequestStudioAsset(id=asset_id, owner_actor_id=auth.actor_id,
                storage_path=path.name, **scope, **info)
            session.add(asset)
            await session.flush()
            if author:
                await repo._audit("scenario_asset", asset.id, "upload", None, {"scenario_id": identifier})
            else:
                await repo._audit(row, "attachment_upload")
            uncertain = True
            await session.commit()
            return _reply({"status": "success", "data": asset_metadata(asset)})
    except (SessionAccessError, ScenarioAdminError) as exc:
        return _reply({"status": "error", "error_code": exc.code}, exc.status)
    except ScenarioConflict:
        return _reply({"status": "error", "error_code": "REVISION_CONFLICT"}, 409)
    except ScenarioInputError as exc:
        return _reply({"status": "error", "error_code": "INVALID_ANSWERS", "errors": exc.errors}, 400)
    except (ValidationError, ValueError, TypeError):
        return _reply({"status": "error", "error_code": "VALIDATION_ERROR"}, 400)
    except Exception as exc:
        logger.error("[studio_asset] upload failed: {}", type(exc).__name__)
        return _reply({"status": "error", "error_code": "UPLOAD_FAILED"}, 500)
    finally:
        if path is not None and not uncertain:
            path.unlink(missing_ok=True)


@require_auth("admin")
async def handle_scenario_material_upload(request):
    return await _upload(request, author=True)


@require_auth("user", "admin")
async def handle_scenario_answer_upload(request):
    return await _upload(request)


@require_auth("user", "admin")
async def handle_scenario_answer_remove(request):
    try:
        async with get_session() as session:
            repo = RequestScenarioSessionRepo(session, request["auth_context"])
            row, runtime = await repo.load(request.match_info["identifier"])
            payload = await _payload(request, ScenarioAnswerRequest)
            if row.state != "active" or row.revision != payload.revision or row.current_block_id != payload.expected_block_id:
                raise ScenarioConflict("Session revision or lifecycle changed")
            if payload.answers or payload.current_result is not None:
                raise ScenarioInputError({"answers": "Removal does not accept answers"})
            asset = await session.get(RequestStudioAsset, request.match_info["asset_id"])
            if not asset or asset.session_id != row.id or asset.owner_actor_id != repo.owner or asset.artifact_id:
                raise SessionAccessError("ATTACHMENT_NOT_FOUND")
            if asset.removed_at is None:
                asset.removed_at = datetime.now(timezone.utc)
                await repo._audit(row, "attachment_remove")
            await session.commit()
        return _reply({"status": "success", "data": {"removed": True}})
    except (SessionAccessError, ScenarioAdminError) as exc:
        return _reply({"status": "error", "error_code": exc.code}, exc.status)
    except ScenarioConflict:
        return _reply({"status": "error", "error_code": "REVISION_CONFLICT"}, 409)
    except (ValidationError, ValueError, TypeError, ScenarioInputError):
        return _reply({"status": "error", "error_code": "VALIDATION_ERROR"}, 400)


@require_auth("user", "admin")
async def handle_scenario_asset_download(request):
    try:
        async with get_session() as session:
            auth = request["auth_context"]
            asset = await session.get(RequestStudioAsset, request.match_info["asset_id"])
            if not asset or asset.removed_at:
                raise SessionAccessError("ATTACHMENT_NOT_FOUND")
            if asset.session_id:
                repo = RequestScenarioSessionRepo(session, auth)
                row, runtime = await repo.load(asset.session_id)
                if asset.owner_actor_id != auth.actor_id or row.state != "active":
                    raise SessionAccessError("ATTACHMENT_NOT_FOUND")
            elif auth.actor_role != "admin":
                repo = RequestScenarioSessionRepo(session, auth)
                scenario = await session.get(RequestStudioScenario, asset.scenario_id)
                await repo._visible(scenario)
                pinned = select(RequestStudioSession.version_id).where(
                    RequestStudioSession.owner_actor_id == auth.actor_id, RequestStudioSession.state == "active",
                    RequestStudioSession.expires_at > datetime.now(timezone.utc))
                versions = list((await session.scalars(select(RequestStudioScenarioVersion).where(
                    RequestStudioScenarioVersion.scenario_id == scenario.id,
                    or_(RequestStudioScenarioVersion.id == scenario.published_version_id, RequestStudioScenarioVersion.id.in_(pinned)),
                    RequestStudioScenarioVersion.state != "revoked"))).all())
                allowed = False
                for version in versions:
                    if not any(ref["asset_id"] == asset.id for ref in material_references(version.definition)):
                        continue
                    if version.id == scenario.published_version_id and version.state == "published":
                        entries = version.definition.get("entry_points", [])
                        from tickets.request_scenario_catalog import category_path_is_public
                        categories = {item.id: item for item in (await session.scalars(select(RequestStudioCategory))).all()} if entries else {}
                        if not entries or any(item.get("enabled", True) and item.get("visibility", "public") == "public"
                            and category_path_is_public(item.get("category_id"), categories) for item in entries):
                            allowed = True
                            break
                    identifiers = (await session.scalars(select(RequestStudioSession.id).where(
                        RequestStudioSession.owner_actor_id == auth.actor_id, RequestStudioSession.version_id == version.id,
                        RequestStudioSession.state == "active", RequestStudioSession.expires_at > datetime.now(timezone.utc)))).all()
                    for identifier in identifiers:
                        try:
                            await repo.load(identifier)
                            allowed = True
                            break
                        except SessionAccessError:
                            continue
                if not allowed:
                    raise SessionAccessError("ATTACHMENT_NOT_FOUND")
            path = UPLOAD_DIR / asset.storage_path
            if not path.is_file():
                raise SessionAccessError("ATTACHMENT_NOT_FOUND")
            disposition = _content_disposition_attachment(asset.name)
            if asset.mime_type in RASTER_MIMES.values():
                disposition = disposition.replace("attachment;", "inline;", 1)
            return web.FileResponse(path, headers={"Content-Type": asset.mime_type,
                "Content-Disposition": disposition, "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox", "Cache-Control": "private, no-store"})
    except SessionAccessError as exc:
        return _reply({"status": "error", "error_code": exc.code}, exc.status)
