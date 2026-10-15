"""Owner-scoped persistence around the canonical pre-ticket runtime."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

from sqlalchemy import select

from app.db.request_scenario_models import RequestStudioCategory, RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.request_scenario_runtime import RuntimeState, ScenarioConflict, ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_session import project_step, review_display_value
from tickets.request_scenario_pickers import PICKERS, picker_options, validate_picker_answers
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver
from web_api.dto.request_scenario import ScenarioDefinition


class SessionAccessError(ValueError):
    def __init__(self, code, status=404):
        self.code, self.status = code, status
        super().__init__(code)


class RequestScenarioSessionRepo:
    def __init__(self, session, actor):
        self.session, self.owner = session, actor.actor_id
        self.actor_role = actor.actor_role
        if actor.actor_role not in {"user", "admin"} or not self.owner:
            raise SessionAccessError("FORBIDDEN", 403)

    async def _visible(self, scenario):
        if scenario.archived or not scenario.enabled:
            raise SessionAccessError("SCENARIO_UNAVAILABLE")
        try:
            await ServiceCatalogRuntimeResolver(self.session).resolve_selection(
                offering_full_code=scenario.offering_full_code, actor_role="requester", require_catalog=True,
            )
        except ServiceCatalogResolutionError:
            raise SessionAccessError("SCENARIO_UNAVAILABLE") from None
        category_id, visited = scenario.category_id, set()
        while category_id:
            if category_id in visited or len(visited) >= 16:
                raise SessionAccessError("SCENARIO_UNAVAILABLE")
            visited.add(category_id)
            category = await self.session.get(RequestStudioCategory, category_id)
            if not category or category.visibility != "public" or category.lifecycle_status != "published":
                raise SessionAccessError("SCENARIO_UNAVAILABLE")
            category_id = category.parent_id

    @staticmethod
    def _state(row):
        return RuntimeState(row.current_block_id, row.revision, deepcopy(row.answers), list(row.history), deepcopy(row.results), row.state)

    @staticmethod
    def _store(row, state):
        for key in ("current_block_id", "revision", "answers", "history", "results", "state"):
            setattr(row, key, deepcopy(getattr(state, key)))

    async def _projection(self, runtime, state):
        projection = project_step(runtime.definition, state)
        fields = projection["block"].get("fields", [])
        options = await picker_options(self.session, self.owner, {item["type"] for item in fields} & PICKERS)
        for item in fields:
            if item["type"] in PICKERS:
                item["options"] = options.get(item["type"], [])
        summary = projection["block"].get("answers", [])
        summary_types = {item["type"] for item in summary} & PICKERS
        if summary_types:
            options = await picker_options(self.session, self.owner, summary_types)
            definitions = {item.key: item for block in runtime.definition.blocks for item in getattr(block, "fields", ())}
            for item in summary:
                if item["type"] in PICKERS:
                    item["display_value"] = review_display_value(definitions[item["key"]], item["value"], options.get(item["type"], []))
        return projection

    async def _view(self, row, runtime):
        return {
            "id": row.id, "version_id": row.version_id, "revision": row.revision,
            "state": row.state, "expires_at": row.expires_at.isoformat(),
            "linked_ticket_id": row.linked_ticket_id,
            "entry_point": deepcopy(row.results.get("_entry_point")),
            **await self._projection(runtime, self._state(row)),
        }

    async def start(self, offering, entry_point_key=None):
        # Serialize start with publish/disable and other starts for this offering.
        scenario = await self.session.scalar(select(RequestStudioScenario).where(
            RequestStudioScenario.offering_full_code == offering,
            RequestStudioScenario.enabled.is_(True), RequestStudioScenario.archived.is_(False),
        ).with_for_update().execution_options(populate_existing=True))
        if not scenario:
            raise SessionAccessError("SCENARIO_UNAVAILABLE")
        await self._visible(scenario)
        version = await self.session.get(RequestStudioScenarioVersion, scenario.published_version_id)
        if not version or version.state != "published" or version.scenario_id != scenario.id:
            raise SessionAccessError("SCENARIO_UNAVAILABLE")
        runtime = ScenarioRuntime(ScenarioDefinition.model_validate(version.definition))
        entry = next((item for item in runtime.definition.entry_points if item.key == entry_point_key), None)
        if entry_point_key is not None:
            if not entry or not entry.enabled or entry.visibility != "public":
                raise SessionAccessError("SCENARIO_UNAVAILABLE")
            from tickets.request_scenario_catalog import category_path_is_public
            categories = {item.id: item for item in (await self.session.scalars(select(RequestStudioCategory))).all()}
            if not category_path_is_public(entry.category_id, categories):
                raise SessionAccessError("SCENARIO_UNAVAILABLE")
        now = datetime.now(timezone.utc)
        row = await self.session.scalar(select(RequestStudioSession).where(
            RequestStudioSession.owner_actor_id == self.owner,
            RequestStudioSession.version_id == version.id,
            RequestStudioSession.state == "active", RequestStudioSession.expires_at > now,
            RequestStudioSession.results[("_entry_point", "key")].astext == entry_point_key,
        ).order_by(RequestStudioSession.created_at.desc()).limit(1))
        if row is None:
            state = runtime.initial_state(entry_point_key)
            row = RequestStudioSession(owner_actor_id=self.owner, version_id=version.id,
                                       expires_at=now + timedelta(hours=24))
            self._store(row, state)
            self.session.add(row)
            await self.session.flush()
            await self._audit(row, "start")
        return await self._view(row, runtime)

    async def _audit(self, row, action):
        await ServiceCatalogRepo(self.session).append_audit(
            object_type="scenario_session", object_code=row.id, action=action,
            actor_id=self.owner, actor_role=self.actor_role, before=None,
            after={"version_id": row.version_id, "block_id": row.current_block_id,
                   "revision": row.revision, "state": row.state},
        )

    async def load(self, identifier):
        row = await self.session.scalar(select(RequestStudioSession).where(
            RequestStudioSession.id == identifier, RequestStudioSession.owner_actor_id == self.owner,
        ).with_for_update().execution_options(populate_existing=True))
        if not row:
            raise SessionAccessError("SESSION_NOT_FOUND")
        version = await self.session.get(RequestStudioScenarioVersion, row.version_id)
        scenario = await self.session.get(RequestStudioScenario, version.scenario_id)
        await self._visible(scenario)
        entry = row.results.get("_entry_point")
        if entry:
            from tickets.request_scenario_catalog import category_path_is_public
            categories = {item.id: item for item in (await self.session.scalars(select(RequestStudioCategory))).all()}
            if not category_path_is_public(entry.get("category_id"), categories):
                raise SessionAccessError("SCENARIO_UNAVAILABLE")
        if version.state == "revoked":
            raise SessionAccessError("SESSION_REVOKED", 410)
        if row.expires_at <= datetime.now(timezone.utc):
            raise SessionAccessError("SESSION_EXPIRED", 410)
        # A retired version remains pinned; never substitute the active definition.
        return row, ScenarioRuntime(ScenarioDefinition.model_validate(version.definition))

    async def read(self, identifier):
        row, runtime = await self.load(identifier)
        return await self._view(row, runtime)

    async def preview(self, identifier, payload):
        row, runtime = await self.load(identifier)
        state = runtime.preview_answers(self._state(row), payload)
        await self._validate_pickers(runtime, state)
        return {"id": row.id, "revision": row.revision, **await self._projection(runtime, state)}

    async def prepare_submission(self, identifier, revision):
        from tickets.request_scenario_submission import build_scenario_submission
        row, runtime = await self.load(identifier)
        if row.state == "ticket_created" and row.linked_ticket_id:
            return row, runtime, None, None
        if row.revision != revision:
            raise ScenarioConflict("Scenario revision changed")
        state = self._state(row)
        source = None
        if runtime.definition.schema_version == 3:
            version = await self.session.get(RequestStudioScenarioVersion, row.version_id)
            source = version.source_snapshot
        data, snapshot = build_scenario_submission(runtime.definition, state, session_id=row.id, version_id=row.version_id,
            **({"source_snapshot": source} if runtime.definition.schema_version == 3 else {}))
        for key in state.history:
            if runtime.blocks[key].kind == "form_page":
                checked = deepcopy(state)
                checked.current_block_id = key
                checked.answers = snapshot["answers"]
                await self._validate_pickers(runtime, checked)
        snapshot["summary"] = (await self._projection(runtime, state))["block"]["answers"]
        data["description"] = ("\n".join(f"{item['label']}: {item['display_value']}" for item in snapshot["summary"]) or runtime.definition.title)[:5000]
        devices = [snapshot["answers"][item.key] for block in runtime.definition.blocks
                   for item in getattr(block, "fields", ()) if item.type == "device_picker" and snapshot["answers"].get(item.key)]
        if len(set(devices)) > 1:
            raise ScenarioInputError({"device": "Choose one diagnostic device for this request"})
        if devices:
            data["device_id"] = devices[0]
        return row, runtime, data, snapshot

    async def complete_submission(self, row, ticket_id):
        row.linked_ticket_id, row.state = ticket_id, "ticket_created"
        row.revision += 1
        await self.session.flush()
        await self._audit(row, "ticket_created")

    async def _validate_pickers(self, runtime, state):
        block = runtime.blocks[state.current_block_id]
        fields = getattr(block, "fields", ())
        types = {item.type for item in fields} & PICKERS
        if types:
            options = await picker_options(self.session, self.owner, types)
            validate_picker_answers(fields, state.answers, options)

    async def command(self, identifier, kind, payload):
        row, runtime = await self.load(identifier)
        fingerprint = hashlib.sha256(json.dumps(
            {"kind": kind, "payload": payload.model_dump(mode="json")}, sort_keys=True,
            ensure_ascii=False, separators=(",", ":"),
        ).encode()).hexdigest()
        receipt = row.results.get("_request_receipt")
        if receipt == {"hash": fingerprint, "revision": row.revision}:
            return await self._view(row, runtime)
        state = self._state(row)
        if state.revision != payload.revision or (
            hasattr(payload, "expected_block_id") and state.current_block_id != payload.expected_block_id
        ):
            raise ScenarioConflict("Scenario revision or current block changed")
        if kind == "back":
            state = runtime.back(state, payload.target_block_id, expected_revision=payload.revision)
        elif kind == "finish":
            if state.revision != payload.revision:
                raise ScenarioConflict("Scenario revision changed")
            if state.state != "completed_self_service":
                raise ScenarioInputError({"block": "Only the self-service finish can be confirmed"})
            state.revision += 1
        else:
            expected_kind = runtime.blocks[state.current_block_id].kind
            if (kind == "answer") != (expected_kind == "form_page"):
                raise ScenarioInputError({"block": "Use the command for the current step"})
            if expected_kind == "form_page":
                await self._validate_pickers(runtime, runtime.preview_answers(state, payload))
            state = runtime.advance(state, payload)
        state.results["_request_receipt"] = {"hash": fingerprint, "revision": state.revision}
        self._store(row, state)
        await self.session.flush()
        await self._audit(row, kind)
        return await self._view(row, runtime)
