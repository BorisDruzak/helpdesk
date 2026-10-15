"""Scenario admin persistence over the existing catalog and its audit transaction."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select, text, exists, or_, func

from app.db.models import RequestTemplate, HelpdeskServiceOffering
from app.db.request_scenario_models import RequestStudioCategory, RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.request_studio_catalog_projection import offering_cards
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

    async def create_service(self, raw):
        """Create the internal catalog binding with the map, in one transaction."""
        from web_api.dto.request_scenario import ScenarioDraftDefinition, CatalogCode, _bounded_input
        from pydantic import TypeAdapter
        _bounded_input(raw)
        version = raw.get("schema_version", 2)
        if type(version) is not int or version not in {1, 2, 3}:
            raise ScenarioAdminError("VALIDATION_ERROR")
        code = TypeAdapter(CatalogCode).validate_python(raw.get("service_code"))
        service = await self._service_lock(code)
        prior = await self.session.scalar(select(RequestStudioScenario).where(RequestStudioScenario.scenario_key == raw.get("scenario_key")))
        if prior:
            row, draft = await self.detail(prior.id)
            comparable = deepcopy(draft.definition)
            comparable.update(offering_full_code="", publish_offering=False)
            comparable["process_binding"]["request_template_key"] = ""
            incoming = deepcopy(raw)
            incoming.setdefault("publish_offering", False)
            incoming = ScenarioDraftDefinition.model_validate({**incoming, "offering_full_code": row.offering_full_code,
                "process_binding": {**incoming.get("process_binding", {}), "request_template_key": draft.definition["process_binding"]["request_template_key"]}}).model_dump(mode="json")
            incoming.update(offering_full_code="", publish_offering=False)
            incoming["process_binding"]["request_template_key"] = ""
            if comparable != incoming:
                raise ScenarioAdminError("REVISION_CONFLICT", 409)
            return {"scenario": serialize(row), "draft": serialize(draft)}
        if raw.get("offering_full_code") or (raw.get("process_binding") or {}).get("request_template_key"):
            raise ScenarioAdminError("CATALOG_BINDING_INVALID")
        configured = (service.get("metadata") or {}).get("studio_default_template")
        offerings = await self.catalog.list_offerings(service_code=code)
        candidates = sorted({item["request_template_key"] for item in offerings
            if item.get("request_template_key") and item.get("lifecycle_status") == "published"})
        template_key = configured or (code if code in candidates else candidates[0] if len(candidates) == 1 else None)
        if not template_key:
            # Compare processing, not question schemas. Equivalent bridges are
            # interchangeable for v2 and section policy overrides remain canonical.
            from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
            fingerprints = {}
            for candidate in candidates:
                effective = await HelpdeskPolicyRepo(self.session).resolve_effective_request_template(template_code=candidate, raise_if_missing=False)
                template = effective.get("request_template") or {}
                if template.get("published_at") and template.get("ticket_type") == (service.get("default_ticket_type_code") or "incident"):
                    fingerprints[candidate] = definition_hash({"type": template.get("ticket_type"), "policies": effective.get("resolved_policies"), "workflow": template.get("workflow_profile_id"), "config": template.get("config")})
            if fingerprints and len(set(fingerprints.values())) == 1:
                template_key = sorted(fingerprints)[0]
        if not template_key:
            raise ScenarioAdminError("SERVICE_PROCESSING_DEFAULT_REQUIRED", 409)
        from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
        effective = await HelpdeskPolicyRepo(self.session).resolve_effective_request_template(template_code=template_key, raise_if_missing=False)
        template = effective.get("request_template") or {}
        if not template.get("published_at") or not template.get("is_active"):
            raise ScenarioAdminError("SERVICE_PROCESSING_DEFAULT_REQUIRED", 409)
        offering_code = "map_" + hashlib.sha256(str(raw.get("scenario_key")).encode()).hexdigest()[:32]
        bound = {**raw, "schema_version": max(2, version), "offering_full_code": code + "." + offering_code,
                 "process_binding": {**(raw.get("process_binding") or {}), "request_template_key": template_key}, "publish_offering": True}
        definition = ScenarioDraftDefinition.model_validate(bound)
        await self._category(definition.category_id, code)
        await self.catalog.upsert_offering_draft({"service_code": code, "code": offering_code,
            "public_title": definition.title, "short_description": definition.description, "lifecycle_status": "draft",
            "visibility": "public", "request_template_key": template_key, "ticket_type_code": template["ticket_type"],
            "request_type": "request", "metadata": {"studio_catalog": {"category_id": definition.category_id}, "studio_map_source": definition.scenario_key}},
            actor_id=self.auth.actor_id, actor_role=self.auth.actor_role)
        return await self.create(definition)

    async def convert_offering(self, code, *, apply=False):
        from tickets.request_scenario_conversion import convert_form, ConversionBlocked
        from tickets.form_catalog import resolve_ticket_form_pack
        from app.repos import TicketFormPacksRepo
        offering = await self.catalog.get_offering_by_full_code(code)
        if not offering:
            raise ScenarioAdminError("OFFERING_NOT_FOUND", 404)
        await self._service_lock(offering["service_code"])
        current = await self.session.scalar(select(RequestStudioScenario).where(
            RequestStudioScenario.offering_full_code == code).order_by(RequestStudioScenario.archived, RequestStudioScenario.created_at))
        if current:
            row, draft = await self.detail(current.id)
            return {"offering_full_code": code, "title": offering.get("public_title") or offering.get("name") or code,
                    "status": "existing", "archived": bool(current.archived),
                    "issues": [{"code": "archived_map", "message": "Карта находится в архиве. Повторное преобразование не выполняется."}] if current.archived else [],
                    "detail": {"scenario": serialize(row), "draft": serialize(draft)}}
        form = None
        pack = await resolve_ticket_form_pack(TicketFormPacksRepo(self.session))
        key = offering.get("request_template_key")
        form = next((item for item in pack["forms"] if item["key"] == key or item.get("request_template_key") == key), None)
        if form is None:
            from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
            from tickets.request_template_submission import _find_registry_form_schema, _registry_pack_from_template
            policies = HelpdeskPolicyRepo(self.session)
            effective = await policies.resolve_effective_request_template(template_code=key, raise_if_missing=False)
            schema = _find_registry_form_schema(await policies.list_form_schemas(include_inactive=False),
                template_code=key, requested_form_key=key, preferred_schema_id=(effective.get("request_template") or {}).get("form_schema_id"))
            if schema:
                form = _registry_pack_from_template(effective_template=effective, form_schema=schema, form_key=key)["forms"][0]
        if form is None:
            return {"offering_full_code": code, "title": offering.get("public_title") or offering.get("name") or code, "status": "blocked", "issues": [{"code": "form_unavailable", "message": "Исходная форма недоступна."}]}
        try:
            definition = convert_form(offering, form)
        except ConversionBlocked as exc:
            return {"offering_full_code": code, "title": offering.get("public_title") or offering.get("name") or code, "status": "blocked", "issues": exc.issues}
        result = {"offering_full_code": code, "title": offering.get("public_title") or offering.get("name") or code, "status": "ready", "definition": definition.model_dump(mode="json"), "issues": []}
        if apply:
            result.update(status="converted", detail=await self.create(definition))
        return result

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
        offering = await self.session.scalar(select(HelpdeskServiceOffering.offering_id).where(
            HelpdeskServiceOffering.metadata_json["studio_catalog"]["category_id"].astext == row.id,
            HelpdeskServiceOffering.lifecycle_status != "retired").limit(1))
        if offering:
            raise ScenarioAdminError("CATEGORY_NOT_EMPTY", 409)
        entry_category = {"entry_points": [{"category_id": row.id}]}
        draft_entry = await self.session.scalar(select(RequestStudioDraft.scenario_id).join(
            RequestStudioScenario, RequestStudioDraft.scenario_id == RequestStudioScenario.id,
        ).where(RequestStudioScenario.archived.is_(False), RequestStudioDraft.definition.contains(entry_category)).limit(1))
        if draft_entry:
            raise ScenarioAdminError("CATEGORY_NOT_EMPTY", 409)
        pinned = exists(select(RequestStudioSession.id).where(
            RequestStudioSession.version_id == RequestStudioScenarioVersion.id,
            RequestStudioSession.state == "active", RequestStudioSession.expires_at > datetime.now(timezone.utc),
        ))
        published_entry = await self.session.scalar(select(RequestStudioScenarioVersion.id).join(
            RequestStudioScenario, RequestStudioScenarioVersion.scenario_id == RequestStudioScenario.id,
        ).where(RequestStudioScenario.archived.is_(False), RequestStudioScenarioVersion.definition.contains(entry_category),
                or_(RequestStudioScenario.published_version_id == RequestStudioScenarioVersion.id, pinned)).limit(1))
        if published_entry:
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
        from tickets.request_scenario_processing import apply_scenario_policy_refs
        references = {kind: code for kind, code in definition.process_binding.policy_refs.items()
                      if definition.schema_version != 3 or kind not in {"routing", "sla"}}
        await apply_scenario_policy_refs(self.session, {"template_context": {}}, references)
        await self._category(definition.category_id, definition.service_code)
        for entry in definition.entry_points:
            await self._category(entry.category_id, definition.service_code)

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
        from tickets.request_scenario_simulation import simulation_definition
        definition, scope = simulation_definition(draft.definition, payload.entry_point_key)
        available_diagnostics = {block.get("id") for block in draft.definition.get("blocks", []) if block.get("kind") == "diagnostic"}
        if payload.diagnostic_outcomes.keys() - available_diagnostics:
            raise ScenarioAdminError("DIAGNOSTIC_OUTCOME_INVALID")
        selected_ids = {block.id for block in definition.blocks}
        engine = ScenarioRuntime(definition, diagnostic_outcomes={key: value for key, value in payload.diagnostic_outcomes.items() if key in selected_ids})
        state = engine.initial_state(payload.entry_point_key)
        for step in payload.steps:
            state = engine.advance(state, step)
        from tickets.request_scenario_session import project_step
        projected = engine.preview_answers(state, payload.preview) if payload.preview else state
        processing = None
        processing_error = None
        if engine.blocks[state.current_block_id].kind == "submit_ticket":
            from tickets.request_scenario_submission import build_scenario_submission
            from tickets.service_catalog_preview import ServiceCatalogPreviewError, simulate_service_catalog_processing
            data, snapshot = build_scenario_submission(engine.definition, state, session_id="simulation", version_id="draft")
            try:
                _, processing = await simulate_service_catalog_processing(self.session, data, scenario_snapshot=snapshot,
                    **({"allow_draft_offering": True} if draft.definition.get("publish_offering") is True else {}))
            except ServiceCatalogPreviewError:
                # The graph reached its result. Canonical form/policy validation is
                # still blocked; disclose it separately without echoing raw inputs.
                processing_error = {"code": "PROCESSING_INPUT_INVALID"}
        terminal_trace = {}
        if engine.definition.schema_version == 3 and state.state == "completed_self_service":
            from tickets.request_scenario_submission import map_processing
            terminal_trace = {"map_processing": map_processing(engine.definition, state)}
        return {"state": asdict(state), "current_block": engine.blocks[state.current_block_id].model_dump(mode="json"),
                "current_step": project_step(engine.definition, projected)["block"], "processing": processing, "revision": draft.revision,
                "simulation_scope": scope, "processing_error": processing_error, **terminal_trace}

    async def catalog_view(self, *, query="", status="all", offset=0, limit=100, category_id=None, service_code=None, offering_code=None):
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
        offerings = await self.catalog.list_offerings()
        services = await self.catalog.list_services()
        rows = (await self.session.execute(select(RequestStudioScenario, RequestStudioDraft, RequestStudioScenarioVersion.version,
            func.coalesce(func.jsonb_array_length(RequestStudioScenarioVersion.definition["entry_points"]), 0), RequestStudioScenarioVersion.definition).join(RequestStudioDraft, RequestStudioDraft.scenario_id == RequestStudioScenario.id).outerjoin(RequestStudioScenarioVersion, (RequestStudioScenarioVersion.id == RequestStudioScenario.published_version_id) & (RequestStudioScenarioVersion.state == "published")).order_by(RequestStudioScenario.title, RequestStudioScenario.id))).all()
        scenarios = []
        for record in rows:
            row, draft, published_version, published_entry_count = record[:4]
            published_definition = record[4] if len(record) > 4 else None
            item = serialize(row)
            item["updated_at"] = max(row.updated_at, draft.updated_at).isoformat()
            issues = []
            try:
                definition = ScenarioDefinition.model_validate(draft.definition)
                issues = [asdict(issue) for issue in validate_scenario(definition)]
            except ValueError:
                issues = [{"code": "incomplete_draft", "path": "blocks", "message": "Добавьте вопросы и переходы"}]
            item["status"] = "archived" if row.archived else "published" if row.published_version_id else "errors" if issues else "draft"
            item.update(revision=draft.revision, published_version=published_version,
                published_entry_count=published_entry_count,
                entry_point_count=len(draft.definition.get("entry_points", [])),
                issues=issues, category_title=category_names.get(row.category_id, ""))
            item["entry_points"] = deepcopy(draft.definition.get("entry_points", []))
            item["schema_version"] = draft.definition.get("schema_version", 1)
            item["published_entry_points"] = deepcopy((published_definition or {}).get("entry_points", []))
            if len(record) > 4:
                from tickets.request_scenario_catalog import project_catalog_entries
                try:
                    published = ScenarioDefinition.model_validate(published_definition)
                    public_entries = project_catalog_entries(published, {c["id"]: c for c in categories}, row.published_version_id)
                    item["published_public_entry_keys"] = [entry["key"] for entry in public_entries]
                    item["published_route_available"] = bool(public_entries) or not published.entry_points
                except ValueError:
                    item["published_public_entry_keys"] = []
                    item["published_route_available"] = False
            scenarios.append(item)
        entries = offering_cards(offerings, scenarios, categories, services, query=query, status=status,
            service_code=service_code, offering_code=offering_code, selected=selected)
        page = entries[offset:offset + limit]
        return {"categories": categories, "entries": page,
            "scenarios": [scenario for item in page for scenario in item["scenarios"]],
            "legacy_offerings": [item["offering"] for item in page if not any(not scenario["archived"] for scenario in item["scenarios"])], "total": len(entries),
            "offset": offset, "limit": limit, "services": services, "offerings": offerings}
