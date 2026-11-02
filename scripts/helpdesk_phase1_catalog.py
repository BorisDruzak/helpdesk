"""Bounded phase-one Studio publication; imported by the reviewed staging wrapper.

No CLI, credentials, deployment, account action or backup implementation lives
here. The caller supplies a trusted admin AuthContext and a fresh sessionmaker,
and owns private backup/release/host guards. Planning performs SELECTs only.
"""
from copy import deepcopy
import hashlib
import json

from sqlalchemy import select, text

from app.db.models import (
    FormSchema, FormField, RequestTemplate, TicketBusinessCalendar,
    TicketFormPack, TicketQueue, TicketSlaPolicy, TicketSlaTarget, TicketQueueOlaTarget,
    ServerConfig, HelpdeskService, HelpdeskServiceOffering,
)
from app.db.request_scenario_models import RequestStudioScenario, RequestStudioDraft, RequestStudioScenarioVersion, RequestStudioCategory
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo, POLICY_MODELS
from app.repos.request_scenario_repo import RequestScenarioRepo, serialize
from tickets.request_scenario_publication import ScenarioPublicationService
from web_api.dto.request_scenario_admin import ScenarioPublish

CLOSURE_CODE = "guided_studio_20261011_closure"
CLOSURE_VERSION = "1.0.2"
OTHER_KEY = "scenario_import_608bb9a16cbd45ed9c921c4ba92df310"
STAGING_DATABASE = "helpdesk_staging_db"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def require_target(database, *, isolated_test=False):
    """Database name is checked on the live connection; host is wrapper-owned."""
    if isolated_test:
        if not database.startswith("pc_support_test_") or database in {"pc_support_test_", "pc_support_test_template"} or database.startswith("pc_support_test_template"):
            raise ValueError("An isolated per-run test database is required")
    elif database != STAGING_DATABASE:
        raise ValueError("Only the approved Helpdesk staging database is allowed")


def build_definitions(base):
    """Copy authoritative Other questions/SLA; create four separate new maps."""
    if base.get("schema_version") != 3 or base.get("process_binding", {}).get("policy_refs", {}).get("closure") != CLOSURE_CODE:
        raise ValueError("The authoritative v3 Other definition is required")
    source = {block["id"]: block for block in base["blocks"]}
    for key in ("q_scope", "q_urgency", "d_sla", "submit"):
        if key not in source:
            raise ValueError("Authoritative Other questions/SLA are incomplete")
    specs = (
        ("password_recovery", "access", "Восстановление пароля или входа", "Корпоративная учётная запись",
         "В какой системе не удаётся войти?", "Название другой системы",
         "Опишите ошибку входа и когда она появилась. Не сообщайте текущий или новый пароль, PIN и коды подтверждения."),
        ("new_account", "access", "Создание учётной записи", "Корпоративная учётная запись",
         "Для какой системы нужна учётная запись?", "Название другой системы",
         "Укажите ФИО сотрудника, подразделение, дату начала работы и необходимый доступ. Создание учётной записи и права проверяет специалист; пароли не указывайте."),
        ("equipment_replacement", "workplace", "Замена оборудования", "Рабочий компьютер",
         "Какое оборудование нужно заменить?", "Другое оборудование: тип и модель",
         "Укажите причину замены, инвентарный номер (если известен) и кабинет. Замена и её согласование выполняются специалистом."),
        ("business_system", "other", "Не работает сайт или информационная система", "Веб-сайт",
         "Где возникла проблема?", "Название информационной системы",
         "Укажите адрес сайта без секретных параметров или название системы, текст ошибки, время начала и что уже пробовали. Не указывайте пароли, коды и ссылки для входа."),
    )
    result = []
    for key, service, title, known, question, other_label, help_text in specs:
        condition = {"source": "answer", "field": "subject_kind", "op": "eq", "value": "other"}
        intro = {"id": "request", "kind": "form_page", "title": title, "layout": "group", "fields": [
            {"key": "subject_kind", "type": "radio", "label": question, "required": True,
             "options": [{"value": "known", "label": known}, {"value": "other", "label": "Другая система" if service != "workplace" else "Другое оборудование"}]},
            {"key": "subject_other", "type": "text", "label": other_label,
             "visible_when": condition, "required_when": condition, "validation": {"max_length": 300}},
            {"key": "request_details", "type": "textarea", "label": "Что требуется или что произошло?",
             "required": True, "help_text": help_text, "validation": {"max_length": 5000}},
        ], "transitions": [{"to": "q_scope"}]}
        blocks = [intro, *[deepcopy(source[name]) for name in ("q_scope", "q_urgency", "d_sla", "submit")]]
        blocks[2]["transitions"] = [{"to": "d_sla"}]
        processing = deepcopy(base["processing"])
        processing["routes"] = {"first_line": deepcopy(processing["routes"]["first_line"])}
        processing["defaults"]["route"] = "first_line"
        binding = deepcopy(base["process_binding"])
        binding["request_template_key"] = ""
        result.append({"schema_version": 3, "scenario_key": "phase1_" + key,
            "service_code": service, "offering_full_code": "", "category_id": None,
            "title": title, "description": help_text, "entry_block_id": "request",
            "entry_points": [{"key": key, "title": title, "description": help_text,
                "target_block_id": "request", "enabled": True, "visibility": "public"}],
            "process_binding": binding, "processing": processing, "blocks": blocks})
    return result


def build_closure_request(current):
    if current.get("code") != CLOSURE_CODE or current.get("version") != "1.0.1":
        raise ValueError("Expected the approved ordinary closure policy version 1.0.1")
    config = deepcopy(current.get("config") or {})
    if config.get("require_public_summary") is not True:
        raise ValueError("Ordinary policy must already require a public result")
    # Only this reviewed ordinary policy is eligible; never edit special codes.
    config["require_resolution_code"] = False
    config["requester_confirmation"] = {**config.get("requester_confirmation", {}), "required": False}
    return {"kind": "closure", "code": CLOSURE_CODE, "requested_version": CLOSURE_VERSION,
        "title": current["title"], "description": current.get("description"),
        "scope_level": current.get("scope_level") or "system", "scope_ref": current.get("scope_ref"), "config": config}


async def read_catalog(session):
    """Stable complete publication-input snapshot, excluding tokens and tickets."""
    models = [RequestStudioScenario, RequestStudioDraft, RequestStudioScenarioVersion, RequestStudioCategory,
        HelpdeskService, HelpdeskServiceOffering, RequestTemplate, FormSchema, FormField,
        TicketBusinessCalendar, TicketFormPack, TicketQueue, TicketSlaPolicy,
        TicketSlaTarget, TicketQueueOlaTarget, ServerConfig, *POLICY_MODELS.values()]
    result = {}
    for model in dict.fromkeys(models):
        values = [serialize(row) for row in await session.scalars(select(model))]
        result[model.__tablename__] = sorted(values, key=fingerprint)
    return result


async def publish_phase1(session_factory, auth, *, expected_fingerprint=None, apply=False, isolated_test=False):
    """Plan by default; apply atomically through canonical audited services.

    Supply the fingerprint from a fresh reviewed plan. A repeated apply uses a
    fresh plan fingerprint and produces no additional version if content matches.
    All mutations including confirmation tokens roll back on any failure.
    """
    if not auth.is_admin() or not auth.actor_id:
        raise ValueError("A trusted authenticated admin context is required")
    async with session_factory() as session:
        async with session.begin():
            database = await session.scalar(text("SELECT current_database()"))
            require_target(database, isolated_test=isolated_test)
            if apply:
                # Stable, bounded advisory lock serializes this helper; source
                # table locks close races with normal Studio/policy writers.
                await session.execute(text("SELECT pg_advisory_xact_lock(20261102, 5)"))
                lock_repo = RequestScenarioRepo(session, auth)
                # Match canonical publication's service-before-source order.
                for code in ("access", "other", "workplace"):
                    await lock_repo._service_lock(code)
                await ScenarioPublicationService(lock_repo)._freeze_sources(write_offering=True)
                await session.execute(text("LOCK TABLE request_studio_scenarios, request_studio_drafts, request_studio_scenario_versions IN SHARE ROW EXCLUSIVE MODE"))
            snapshot = await read_catalog(session)
            before_hash = fingerprint(snapshot)
            other = next((item for item in snapshot[RequestStudioScenario.__tablename__] if item["scenario_key"] == OTHER_KEY), None)
            if not other or not other["enabled"] or other["archived"]:
                raise ValueError("Authoritative published Other scenario is unavailable")
            version = next((item for item in snapshot[RequestStudioScenarioVersion.__tablename__] if item["id"] == other["published_version_id"]), None)
            if not version:
                raise ValueError("Authoritative published Other version is unavailable")
            definitions = build_definitions(version["definition"])
            policies = await HelpdeskPolicyRepo(session).list_policies("closure")
            rows = [item for item in policies["closure"] if item["code"] == CLOSURE_CODE]
            old = next((item for item in rows if item["version"] == "1.0.1"), None)
            if not old:
                raise ValueError("Approved ordinary policy baseline is unavailable")
            policy_request = build_closure_request(old)
            exact = next((item for item in rows if item["version"] == CLOSURE_VERSION), None)
            active = [item for item in rows if item["is_active"]]
            if exact:
                if any(exact[key] != policy_request[key] for key in ("config", "title", "description", "scope_level", "scope_ref")) or not exact["is_active"] or len(active) != 1:
                    raise ValueError("Ordinary policy version conflicts with approved content")
            elif len(active) != 1 or active[0]["version"] != "1.0.1" or any(item["version"] != "1.0.1" for item in rows):
                raise ValueError("Ordinary closure policy changed since approval")
            plan = {"fingerprint": before_hash, "scenario_keys": [item["scenario_key"] for item in definitions],
                "definitions": definitions, "closure_request": policy_request, "applied": False}
            if not apply:
                return plan
            if not expected_fingerprint or before_hash != expected_fingerprint:
                raise ValueError("Publication baseline changed; obtain and review a fresh plan")
            if exact is None:
                await HelpdeskPolicyRepo(session).publish_policy(**policy_request, actor_id=auth.actor_id, actor_role=auth.actor_role)
            repo = RequestScenarioRepo(session, auth)
            publisher = ScenarioPublicationService(repo)
            published = []
            for raw in definitions:
                created = await repo.create_service(raw)
                scenario, draft = created["scenario"], created["draft"]
                if scenario["archived"]:
                    raise ValueError("Phase-one map is archived; explicit review is required")
                current = await session.get(RequestStudioScenarioVersion, scenario["published_version_id"]) if scenario["published_version_id"] else None
                if current:
                    if not scenario["enabled"] or current.definition != draft["definition"]:
                        raise ValueError("Published phase-one map differs from the approved content")
                    published.append({"scenario_key": raw["scenario_key"], "version_id": current.id, "changed": False})
                    continue
                preview = await publisher.preview(scenario["id"], draft["revision"])
                if not preview["readiness"]["can_publish"]:
                    raise ValueError("Phase-one scenario failed canonical publication readiness: " + raw["scenario_key"])
                payload = ScenarioPublish(revision=draft["revision"], confirm=True, confirmation_token=preview["confirmation_token"])
                result = await publisher.publish(scenario["id"], payload)
                published.append({"scenario_key": raw["scenario_key"], "version_id": result["version"]["id"], "changed": True})
            return {"applied": True, "before_fingerprint": before_hash,
                "after_fingerprint": fingerprint(await read_catalog(session)), "scenarios": published,
                "closure_version": CLOSURE_VERSION, "closure_changed": exact is None}
