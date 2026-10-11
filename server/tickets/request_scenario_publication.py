"""Scenario readiness and atomic publication over canonical policy services."""
from copy import deepcopy
from dataclasses import asdict

from sqlalchemy import select, func, text
from pydantic import ValidationError

from app.db.models import FormSchema, FormField, RequestTemplate, TicketQueue, TicketSlaPolicy, TicketSlaTarget, TicketQueueOlaTarget, TicketBusinessCalendar, TicketFormPack, ServerConfig
from app.db.request_scenario_models import RequestStudioScenarioVersion, RequestStudioCategory
from app.repos import TicketFormPacksRepo
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo, POLICY_MODELS
from app.repos.request_scenario_repo import ScenarioAdminError, definition_hash, serialize
from tickets.form_catalog import resolve_ticket_form_pack
from tickets.policy_health_service import PolicyHealthService
from tickets.request_scenario_readiness import ReadinessCoverageError, submission_variants
from tickets.request_scenario_submission import build_scenario_submission
from tickets.request_scenario_validation import ScenarioValidationError
from tickets.request_studio_publication import RequestStudioPublicationService
from tickets.service_catalog_preview import simulate_service_catalog_processing
from tickets.service_catalog_publication import ServiceCatalogPublicationService
from web_api.dto.request_scenario import ScenarioDefinition

SCOPE = "request_scenario.publish"


def scenario_diff(before, after, path=""):
    """Expose nested edits; unchanged block titles cannot conceal changed fields."""
    if before == after:
        return []
    if isinstance(before, dict) or isinstance(after, dict):
        left, right = before if isinstance(before, dict) else {}, after if isinstance(after, dict) else {}
        return [change for key in sorted(set(left) | set(right))
                for change in scenario_diff(left.get(key), right.get(key), f"{path}.{key}".strip("."))]
    if isinstance(before, list) or isinstance(after, list):
        left, right = before if isinstance(before, list) else [], after if isinstance(after, list) else []
        key = next((candidate for candidate in ("id", "key") if left + right and all(isinstance(item, dict) and candidate in item for item in left + right)), None)
        if key:
            result = scenario_diff([item[key] for item in left], [item[key] for item in right], path + ".order")
            left_by, right_by = {item[key]: item for item in left}, {item[key]: item for item in right}
            result.extend(change for identifier in sorted(set(left_by) | set(right_by))
                          for change in scenario_diff(left_by.get(identifier), right_by.get(identifier), path + "." + identifier))
            return result
    return [{"path": path, "before": before, "after": after}]


def _policy_fields(value):
    """Find actual canonical policy fact references, including legacy inline rules."""
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key == "field" or key.endswith("_field") or key == "fact_key"):
                result.add(item.rsplit(".", 1)[-1])
            if key == "modifier_fields" and isinstance(item, dict):
                result.update(field.rsplit(".", 1)[-1] for field in item.values() if isinstance(field, str))
            result.update(_policy_fields(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_policy_fields(item))
    return result


class ScenarioPublicationService:
    def __init__(self, repo):
        self.repo, self.session = repo, repo.session
        self.tokens = RequestStudioPublicationService(self.session)

    async def _snapshot(self, row, draft):
        policies = HelpdeskPolicyRepo(self.session)
        effective = await policies.resolve_effective_request_template(template_code=draft.definition["process_binding"]["request_template_key"], raise_if_missing=False)
        result = {"effective_template": effective,
                  "service": await self.repo.catalog.get_service_by_code(row.service_code),
                  "offering": await self.repo.catalog.get_offering_by_full_code(row.offering_full_code),
                  "taxonomy": await self.repo.categories(),
                  "form_schemas": await policies.list_form_schemas(include_inactive=False),
                  "policies": await policies.list_policies(include_inactive=False)}
        packs = TicketFormPacksRepo(self.session)
        result["form_pack"] = await resolve_ticket_form_pack(packs)
        result["preferred_pack"] = await packs.get_preferred("request_forms")
        for key, model in (("queues", TicketQueue), ("sla_policies", TicketSlaPolicy), ("sla_targets", TicketSlaTarget), ("ola_targets", TicketQueueOlaTarget), ("business_calendars", TicketBusinessCalendar)):
            values = [serialize(item) for item in await self.session.scalars(select(model))]
            result[key] = sorted(values, key=definition_hash)
        return result

    @staticmethod
    def _binding(row, draft, source):
        return definition_hash({"scenario_id": row.id, "revision": draft.revision, "definition": draft.definition,
                                "active_version_id": row.published_version_id, "enabled": row.enabled,
                                "archived": row.archived, "source_snapshot": source})

    async def _assess(self, row, draft, source):
        issues, checked, outcomes = [], 0, []
        active_queue_ids = {queue["id"] for queue in source["queues"] if queue.get("is_active") is True}
        def add(code, message, path="process_binding"):
            issues.append({"code": code, "message": message, "path": path})
        for block in draft.definition.get("blocks", []):
            for field in block.get("fields", []):
                if field.get("type") == "file":
                    add("attachments_unsupported", "Вложения до создания обращения недоступны: безопасное временное хранение и проверка файлов не настроены.", "blocks." + block.get("id", "") + ".fields." + field.get("key", ""))
        effective = source["effective_template"]
        template = deepcopy(effective.get("request_template") or {})
        policies = deepcopy(effective.get("resolved_policies") or {})
        references = draft.definition.get("process_binding", {}).get("policy_refs", {})
        if references:
            from tickets.request_scenario_processing import apply_scenario_policy_refs
            try:
                selected = await apply_scenario_policy_refs(self.session, {"template_context": {}}, references)
                context = selected["template_context"]
                for kind, code in references.items():
                    policies[kind] = context[kind + "_policy"]
                    template[kind + "_policy_code"] = code
            except ValueError:
                add("policy_reference_unavailable", "Выбранная политика обработки недоступна или не опубликована. Выберите действующую политику.", "process_binding.policy_refs")
        health = PolicyHealthService().evaluate(templates=[template] if template else [], policies=source["policies"], queues=source["queues"])
        health = next(iter(health["templates"]), {"health_status": "unavailable"})
        if row.archived:
            add("archived", "Архивный сценарий нельзя публиковать.")
        if not template or not template.get("published_at"):
            add("template_unpublished", "Выберите действующий опубликованный шаблон обработки.")
        for kind, label in (("closure", "закрытия"), ("visibility", "видимости")):
            if not policies.get(kind):
                add(kind + "_missing", f"Не настроена действующая политика {label}.")
        for key in ("service", "offering"):
            item = source.get(key) or {}
            candidate = key == "offering" and draft.definition.get("publish_offering") is True and item.get("lifecycle_status") == "draft"
            if (item.get("lifecycle_status") != "published" and not candidate) or item.get("visibility") != "public":
                add(key + "_unavailable", "Услуга и раздел должны быть опубликованы и доступны сотруднику.")
        candidate_offering = draft.definition.get("publish_offering") is True and (source.get("offering") or {}).get("lifecycle_status") == "draft"
        if candidate_offering:
            validation = await ServiceCatalogPublicationService(self.session).validate_offering(row.offering_full_code)
            if validation["blocking"]:
                add("offering_not_ready", "Новая услуга не прошла действующую проверку Service Catalog. Исправьте шаблон, маршрут или политики.", "offering_full_code")
        if (source.get("offering") or {}).get("request_template_key") != draft.definition["process_binding"]["request_template_key"]:
            add("binding_changed", "Привязка услуги к шаблону изменилась.")
        if row.category_id:
            categories = {item["id"]: item for item in source["taxonomy"]}
            category_id = row.category_id
            while category_id:
                category = categories.get(category_id)
                if not category or category["lifecycle_status"] != "published" or category["effective_visibility"] != "public":
                    add("category_unavailable", "Категория и её родители должны быть опубликованы и доступны сотруднику.", "category_id")
                    break
                category_id = category["parent_id"]
        definition = None
        try:
            definition = ScenarioDefinition.model_validate(draft.definition)
            actual_fields = _policy_fields(effective) | _policy_fields(source["policies"])
            process_fields = {field.key for block in definition.blocks for field in getattr(block, "fields", ())
                              if (field.process_mapping.fact_key or field.key) in actual_fields}
            states = submission_variants(definition, process_fields=process_fields)
        except ValidationError:
            add("incomplete_graph", "Добавьте вопросы, начальный шаг и допустимые завершения.", "blocks")
            states = []
        except ScenarioValidationError as exc:
            issues.extend(asdict(issue) for issue in exc.issues)
            states = []
        except ReadinessCoverageError as exc:
            add("coverage_unproven", str(exc), "blocks")
            states = []
        submit_ids = {block.id for block in definition.blocks if block.kind == "submit_ticket"} if definition else set()
        if not any(state.current_block_id in submit_ids for state in states):
            add("submission_unreachable", "Нет проверяемой ветви обращения в поддержку.", "blocks")
        for state in states:
            checked += 1
            if state.state == "completed_self_service":
                outcomes.append({"terminal": state.current_block_id, "kind": "self_service"})
                continue
            try:
                payload, snapshot = build_scenario_submission(definition, state, session_id="readiness", version_id="draft")
                _, result = await simulate_service_catalog_processing(self.session, payload, scenario_snapshot=snapshot, **({"allow_draft_offering": True} if candidate_offering else {}))
                routing, sla, approval = result["routing"], result["sla"], result["approval"]
                if routing.get("queue_id") not in active_queue_ids:
                    add("routing_unavailable", "Одна из ветвей не попадает в действующую очередь.")
                if ("sla" in references or not (template.get("config") or {}).get("no_sla")) and not sla.get("resolution_min"):
                    add("sla_unavailable", "Одна из ветвей не имеет срока выполнения по действующей политике.")
                if approval.get("required") and not approval.get("approvers"):
                    add("approval_unavailable", "Согласование требуется, но действующий источник не определил согласующих.")
                outcomes.append({"terminal": state.current_block_id, "kind": "ticket", "priority": result["priority"], "routing": routing,
                                 "sla": {key: value for key, value in sla.items() if not key.endswith("preview")}, "approval_required": bool(approval.get("required"))})
            except ValueError:
                add("processing_invalid", "Ответы одной из ветвей несовместимы с опубликованной формой или обработкой.")
        unique = {definition_hash(issue): issue for issue in issues}
        return {"health": health, "readiness": {"can_publish": not unique, "issues": list(unique.values()), "variants_checked": checked}, "outcomes": outcomes}

    async def preview(self, identifier, revision, *, issue_token=True):
        row, draft = await self.repo.detail(identifier, lock=issue_token)
        if draft.revision != revision:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        source = await self._snapshot(row, draft)
        result = await self._assess(row, draft, source)
        old = await self.session.get(RequestStudioScenarioVersion, row.published_version_id) if row.published_version_id else None
        before = old.definition if old else {}
        result["diff"] = scenario_diff(before, draft.definition)
        if draft.definition.get("publish_offering") is True and (source.get("offering") or {}).get("lifecycle_status") == "draft":
            result["diff"].append({"path": "offering.lifecycle_status", "before": "draft", "after": "published"})
        result.update(confirmation_token=None, expires_at=None, source_hash=definition_hash(source), revision=draft.revision)
        if issue_token and result["readiness"]["can_publish"]:
            token, expiry = await self.tokens.issue_bound_confirmation_token(self._binding(row, draft, source), scope=SCOPE, auth_context=self.repo.auth, summary={"scenario_id": row.id, "revision": draft.revision})
            result.update(confirmation_token=token, expires_at=expiry.isoformat())
        return result

    async def _freeze_sources(self, *, write_offering=False):
        # Prevent canonical source DML between revalidation and commit. Names are
        # static SQLAlchemy metadata, never request input. Only publish takes this
        # short transaction lock; preview/simulation never locks source tables.
        models = [FormSchema, FormField, RequestTemplate, TicketQueue, TicketSlaPolicy, TicketSlaTarget,
                  TicketQueueOlaTarget, TicketBusinessCalendar, TicketFormPack, ServerConfig, RequestStudioCategory, *POLICY_MODELS.values()]
        names = sorted({model.__tablename__ for model in models} | {"helpdesk_services", "helpdesk_service_offerings"})
        # Acquire a write-compatible source lock up front for catalog promotion;
        # two concurrent SHARE holders must not deadlock while upgrading later.
        mode = "SHARE ROW EXCLUSIVE" if write_offering else "SHARE"
        await self.session.execute(text("LOCK TABLE " + ", ".join(names) + " IN " + mode + " MODE"))

    async def publish(self, identifier, payload):
        current, _ = await self.repo.detail(identifier)
        await self.repo._service_lock(current.service_code)
        row, draft = await self.repo.detail(identifier, lock=True)
        if row.archived or draft.revision != payload.revision:
            raise ScenarioAdminError("REVISION_CONFLICT", 409)
        await self._freeze_sources(write_offering=draft.definition.get("publish_offering") is True)
        source = await self._snapshot(row, draft)
        token = await self.tokens.validate_bound_confirmation_token(payload.confirmation_token, self._binding(row, draft, source), scope=SCOPE, auth_context=self.repo.auth)
        assessment = await self._assess(row, draft, source)
        if not assessment["readiness"]["can_publish"]:
            raise ScenarioAdminError("SCENARIO_NOT_READY", 409)
        before = self.repo._draft_audit(row, draft)
        if draft.definition.get("publish_offering") is True and (source.get("offering") or {}).get("lifecycle_status") == "draft":
            source["offering"] = await self.repo.catalog.publish_offering(row.offering_full_code, actor_id=self.repo.auth.actor_id, actor_role=self.repo.auth.actor_role)
        previous = await self.session.get(RequestStudioScenarioVersion, row.published_version_id) if row.published_version_id else None
        if previous:
            previous.state = "retired"
            await self.session.flush()
        number = await self.session.scalar(select(func.max(RequestStudioScenarioVersion.version)).where(RequestStudioScenarioVersion.scenario_id == row.id))
        version = RequestStudioScenarioVersion(scenario_id=row.id, offering_full_code=row.offering_full_code, version=(number or 0) + 1,
            schema_version=1, definition=deepcopy(draft.definition), content_hash=definition_hash(draft.definition), source_snapshot=source, published_by=self.repo.auth.actor_id)
        self.session.add(version)
        await self.session.flush()
        row.published_version_id, row.enabled, row.updated_by = version.id, True, self.repo.auth.actor_id
        draft.base_version_id = version.id
        await self.session.flush()
        await self.session.refresh(row, attribute_names=["updated_at"])
        await self.session.refresh(draft, attribute_names=["updated_at"])
        await self.tokens._mark_confirmation_used(token, auth_context=self.repo.auth)
        await self.repo._audit("scenario", row.id, "publish", before, self.repo._draft_audit(row, draft))
        return {"scenario": serialize(row), "draft": serialize(draft), "version": serialize(version)}

    async def rollback_draft(self, identifier, payload):
        current, _ = await self.repo.detail(identifier)
        await self.repo._service_lock(current.service_code)
        row, draft = await self.repo.detail(identifier, lock=True)
        version = await self.session.get(RequestStudioScenarioVersion, payload.version_id)
        if not version or version.scenario_id != row.id:
            raise ScenarioAdminError("NOT_FOUND", 404)
        from web_api.dto.request_scenario_admin import ScenarioSave
        return await self.repo.save(identifier, ScenarioSave(revision=payload.revision, definition=deepcopy(version.definition)))
