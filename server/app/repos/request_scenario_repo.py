"""Scenario admin persistence over the existing catalog and its audit transaction."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from sqlalchemy import select, text

from app.db.models import RequestTemplate
from app.db.request_scenario_models import RequestStudioCategory, RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.request_scenario_runtime import ScenarioRuntime
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition


class ScenarioAdminError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def serialize(row):
    result = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        result[column.name] = value.isoformat() if hasattr(value, "isoformat") else deepcopy(value)
    return result


def definition_hash(definition):
    return hashlib.sha256(json.dumps(definition, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


class RequestScenarioRepo:
    def __init__(self, session, auth):
        self.session, self.auth = session, auth
        self.catalog = ServiceCatalogRepo(session)

    async def _service_lock(self, code):
        # Same lock as the SQL tree guard; serialize moves/archives with children.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:code, 0))"), {"code": code})
        service = await self.catalog.get_service_by_code(code)
        if not service:
            raise ScenarioAdminError("SERVICE_NOT_FOUND", 404)
        return service

    async def _audit(self, kind, key, action, before, after):
        await self.catalog.append_audit(object_type=kind, object_code=key, action=action,
            actor_id=self.auth.actor_id, actor_role=self.auth.actor_role, before=before, after=after)

    async def _category(self, identifier, service_code, *, allow_archived=False):
        if identifier is None:
            return None
        row = await self.session.get(RequestStudioCategory, identifier)
        if row is None or row.service_code != service_code or row.lifecycle_status == "archived" and not allow_archived:
            raise ScenarioAdminError("CATEGORY_BINDING_INVALID")
        return row

    async def categories(self):
        rows = (await self.session.scalars(select(RequestStudioCategory).order_by(RequestStudioCategory.sort_order, RequestStudioCategory.title, RequestStudioCategory.id))).all()
        services = {item["code"]: item for item in await self.catalog.list_services()}
        by_id = {row.id: row for row in rows}
        rank = {"public": 0, "internal": 1, "restricted": 2}
        result = []
        for row in rows:
            visibility = [services[row.service_code]["visibility"], row.visibility]
            parent = row.parent_id
            seen = {row.id}
            while parent is not None:
                if parent in seen or parent not in by_id:
                    raise ScenarioAdminError("CATEGORY_TREE_INVALID", 409)
                seen.add(parent)
                visibility.append(by_id[parent].visibility)
                parent = by_id[parent].parent_id
            item = serialize(row)
            item["effective_visibility"] = max(visibility, key=lambda value: rank[value])
            result.append(item)
        return result

    async def _archive_category_check(self, row):
        child = await self.session.scalar(select(RequestStudioCategory.id).where(RequestStudioCategory.parent_id == row.id, RequestStudioCategory.lifecycle_status != "archived").limit(1))
        scenario = await self.session.scalar(select(RequestStudioScenario.id).where(RequestStudioScenario.category_id == row.id, RequestStudioScenario.archived.is_(False)).limit(1))
        if child or scenario:
            raise ScenarioAdminError("CATEGORY_NOT_EMPTY", 409)

    async def save_category(self, payload, identifier=None):
        await self._service_lock(payload.service_code)
        before = None
        if identifier:
            row = await self.session.scalar(select(RequestStudioCategory).where(RequestStudioCategory.id == identifier).with_for_update())
            if not row:
                raise ScenarioAdminError("NOT_FOUND", 404)
            if row.service_code != payload.service_code:
                raise ScenarioAdminError("SERVICE_BINDING_IMMUTABLE")
            if row.revision != payload.revision:
                raise ScenarioAdminError("REVISION_CONFLICT", 409)
            before = serialize(row)
        else:
            if payload.revision is not None:
                raise ScenarioAdminError("CREATE_REVISION_INVALID")
            row = RequestStudioCategory(service_code=payload.service_code, created_by=self.auth.actor_id, revision=1)
            self.session.add(row)
        await self._category(payload.parent_id, payload.service_code)
        if payload.lifecycle_status == "archived" and identifier:
            await self._archive_category_check(row)
        for key, value in payload.model_dump(exclude={"revision"}).items():
            setattr(row, key, value)
        row.updated_by = self.auth.actor_id
        if identifier:
            row.revision += 1
        await self.session.flush()
        if identifier:
            await self.session.refresh(row, attribute_names=["updated_at"])
        after = serialize(row)
        await self._audit("scenario_category", row.id, "update" if identifier else "create", before, after)
        return next(item for item in await self.categories() if item["id"] == row.id)

    async def archive_category(self, identifier, revision):
        row = await self.session.get(RequestStudioCategory, identifier)
        if not row:
            raise ScenarioAdminError("NOT_FOUND", 404)
        await self._service_lock(row.service_code)
        await self.session.refresh(row, with_for_update=True)
        if row.revision != revision:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        await self._archive_category_check(row)
        before = serialize(row)
        row.lifecycle_status, row.updated_by = "archived", self.auth.actor_id
        row.revision += 1
        await self.session.flush()
        await self.session.refresh(row, attribute_names=["updated_at"])
        after = serialize(row)
        await self._audit("scenario_category", row.id, "archive", before, after)
        return after

    async def _binding(self, definition):
        offering = await self.catalog.get_offering_by_full_code(definition.offering_full_code)
        if not offering:
            raise ScenarioAdminError("OFFERING_NOT_FOUND", 404)
        if offering["service_code"] != definition.service_code or offering["request_template_key"] != definition.process_binding.request_template_key:
            raise ScenarioAdminError("CATALOG_BINDING_INVALID")
        template = await self.session.scalar(select(RequestTemplate.template_code).where(RequestTemplate.template_code == definition.process_binding.request_template_key).limit(1))
        if not template:
            raise ScenarioAdminError("TEMPLATE_NOT_FOUND", 404)
        await self._category(definition.category_id, definition.service_code)

    async def detail(self, identifier, *, lock=False):
        stmt = select(RequestStudioScenario).where(RequestStudioScenario.id == identifier)
        row = await self.session.scalar(stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt)
        if not row:
            raise ScenarioAdminError("NOT_FOUND", 404)
        draft_stmt = select(RequestStudioDraft).where(RequestStudioDraft.scenario_id == identifier)
        draft = await self.session.scalar(draft_stmt.with_for_update().execution_options(populate_existing=True) if lock else draft_stmt)
        if not draft:
            raise ScenarioAdminError("DRAFT_NOT_FOUND", 409)
        return row, draft

    @staticmethod
    def _draft_audit(row, draft):
        return {"scenario": serialize(row), "revision": draft.revision, "definition_hash": definition_hash(draft.definition)}

    async def create(self, definition):
        await self._service_lock(definition.service_code)
        await self._binding(definition)
        row = RequestStudioScenario(scenario_key=definition.scenario_key, service_code=definition.service_code,
            offering_full_code=definition.offering_full_code, category_id=definition.category_id, title=definition.title,
            description=definition.description, created_by=self.auth.actor_id, updated_by=self.auth.actor_id)
        self.session.add(row)
        await self.session.flush()
        draft = RequestStudioDraft(scenario_id=row.id, definition=definition.model_dump(mode="json"), revision=1, updated_by=self.auth.actor_id)
        self.session.add(draft)
        await self.session.flush()
        await self._audit("scenario", row.id, "create", None, self._draft_audit(row, draft))
        return {"scenario": serialize(row), "draft": serialize(draft)}

    async def save(self, identifier, payload):
        current, _ = await self.detail(identifier)
        await self._service_lock(current.service_code)
        row, draft = await self.detail(identifier, lock=True)
        if row.archived or draft.revision != payload.revision:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        definition = payload.definition
        if (definition.scenario_key, definition.service_code, definition.offering_full_code) != (row.scenario_key, row.service_code, row.offering_full_code):
            raise ScenarioAdminError("CATALOG_BINDING_IMMUTABLE")
        await self._binding(definition)
        before = self._draft_audit(row, draft)
        row.title, row.description, row.category_id = definition.title, definition.description, definition.category_id
        row.updated_by = draft.updated_by = self.auth.actor_id
        draft.definition = definition.model_dump(mode="json")
        draft.revision += 1
        await self.session.flush()
        # SQL onupdate timestamps expire on UPDATE with eager_defaults='auto'.
        # Resolve them explicitly before synchronous JSON/audit projection.
        await self.session.refresh(row, attribute_names=["updated_at"])
        await self.session.refresh(draft, attribute_names=["updated_at"])
        await self._audit("scenario", row.id, "save_draft", before, self._draft_audit(row, draft))
        return {"scenario": serialize(row), "draft": serialize(draft)}

    async def archive(self, identifier, revision):
        current, _ = await self.detail(identifier)
        await self._service_lock(current.service_code)
        row, draft = await self.detail(identifier, lock=True)
        if draft.revision != revision or row.archived:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        before = self._draft_audit(row, draft)
        row.archived, row.enabled, row.updated_by = True, False, self.auth.actor_id
        draft.revision += 1
        draft.updated_by = self.auth.actor_id
        await self.session.flush()
        await self.session.refresh(row, attribute_names=["updated_at"])
        await self.session.refresh(draft, attribute_names=["updated_at"])
        await self._audit("scenario", row.id, "archive", before, self._draft_audit(row, draft))
        return {"scenario": serialize(row), "draft": serialize(draft)}

    async def versions(self, identifier):
        await self.detail(identifier)
        rows = await self.session.scalars(select(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.scenario_id == identifier).order_by(RequestStudioScenarioVersion.version.desc()))
        return [serialize(row) for row in rows]

    async def simulate(self, identifier, payload):
        row, draft = await self.detail(identifier)
        if row.archived or draft.revision != payload.revision:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        engine = ScenarioRuntime(ScenarioDefinition.model_validate(draft.definition))
        state = engine.initial_state()
        for step in payload.steps:
            state = engine.advance(state, step)
        return {"state": asdict(state), "current_block": engine.blocks[state.current_block_id].model_dump(mode="json"), "revision": draft.revision}

    async def catalog_view(self, *, query="", status="all", offset=0, limit=100, category_id=None):
        categories = await self.categories()
        selected = {category_id} if category_id else None
        if selected is not None:
            # Include all descendants before slicing the result page.
            for _ in range(len(categories)):
                additions = {item["id"] for item in categories if item["parent_id"] in selected}
                if additions <= selected:
                    break
                selected.update(additions)
        category_names = {item["id"]: item["title"] for item in categories}
        rows = (await self.session.execute(select(RequestStudioScenario, RequestStudioDraft).join(RequestStudioDraft, RequestStudioDraft.scenario_id == RequestStudioScenario.id).order_by(RequestStudioScenario.title, RequestStudioScenario.id))).all()
        scenarios = []
        for row, draft in rows:
            item = serialize(row)
            issues = []
            try:
                definition = ScenarioDefinition.model_validate(draft.definition)
                issues = [asdict(issue) for issue in validate_scenario(definition)]
            except ValueError:
                issues = [{"code": "incomplete_draft", "path": "blocks", "message": "Добавьте вопросы и переходы"}]
            item["status"] = "archived" if row.archived else "published" if row.published_version_id else "errors" if issues else "draft"
            item.update(revision=draft.revision, issues=issues, category_title=category_names.get(row.category_id, ""))
            text_value = " ".join(str(item.get(key) or "") for key in ("title", "description", "category_title", "offering_full_code")).casefold()
            matches_status = (status == "all" or item["status"] == status
                or status == "errors" and bool(issues) and not row.archived
                or status == "draft" and not row.archived and not row.published_version_id)
            if (not query or query.casefold() in text_value) and matches_status and (selected is None or row.category_id in selected):
                scenarios.append(item)
        offerings = await self.catalog.list_offerings()
        bound = {row.offering_full_code for row, _ in rows if not row.archived}
        legacy = [item for item in offerings if item["full_code"] not in bound
            and status in {"all", "form_only"} and selected is None
            and (not query or query.casefold() in " ".join(str(item.get(key) or "") for key in ("public_title", "short_description", "full_code", "service_code")).casefold())]
        entries = [("scenario", item) for item in scenarios] + [("legacy", item) for item in legacy]
        entries.sort(key=lambda entry: (str(entry[1].get("title") or entry[1].get("public_title") or "").casefold(), entry[0], entry[1].get("id") or entry[1]["full_code"]))
        page = entries[offset:offset + limit]
        return {"categories": categories, "scenarios": [item for kind, item in page if kind == "scenario"],
            "legacy_offerings": [item for kind, item in page if kind == "legacy"], "total": len(entries),
            "offset": offset, "limit": limit, "services": await self.catalog.list_services(), "offerings": offerings}
