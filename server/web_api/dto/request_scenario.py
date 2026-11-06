"""Additive, bounded Guided Request Studio v1 definitions and session inputs.

Only answers and the current block result are condition sources. The server owns
identity, policy selection, graph validation and execution; this module does not
dispatch operations or compute ticket policies.
"""
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator, model_serializer

Key = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_]*$")]
CatalogCode = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")]
Scalar = str | bool | int | float | None
Answer = Scalar | list[str]
Role = Literal["display_only", "priority_impact", "priority_urgency", "priority_importance", "routing_field", "diagnostic_input", "approval_subject", "closure_evidence", "reporting_dimension", "passport_fact", "visibility_public"]
FieldType = Literal["text", "textarea", "select", "multi_select", "radio", "checkbox", "number", "date", "datetime", "phone", "email", "url", "user_picker", "department_picker", "location_picker", "device_picker", "service_picker"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def _bounded_input(raw):
    if not isinstance(raw, dict):
        return raw
    stack = [(raw, 0)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if depth > 32 or nodes > 20000:
            raise ValueError("definition exceeds nesting or item limit")
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    if len(json.dumps(raw, ensure_ascii=False).encode("utf-8")) > 1048576:
        raise ValueError("definition exceeds byte limit")
    return raw


class ConditionSource(StrictModel):
    source: Literal["answer", "current_result"]
    field: Key | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if (self.source == "answer") != (self.field is not None):
            raise ValueError("answer requires field; current_result permits only null or omitted field")
        return self


class Comparison(ConditionSource):
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte"]
    value: Scalar


class Membership(ConditionSource):
    op: Literal["in"]
    value: Annotated[list[Scalar], Field(min_length=1, max_length=100)]


class Exists(ConditionSource):
    op: Literal["exists"]


class AllAny(StrictModel):
    op: Literal["and", "or"]
    conditions: Annotated[list[Condition], Field(min_length=1, max_length=20)]


class Negation(StrictModel):
    op: Literal["not"]
    condition: Condition


Condition = Annotated[Comparison | Membership | Exists | AllAny | Negation, Field(discriminator="op")]
AllAny.model_rebuild()
Negation.model_rebuild()


class ProcessingFacts(StrictModel):
    impact: Literal["single_user", "multiple_users", "department"] | None = None
    urgency: Literal["can_work", "degraded", "blocked"] | None = None
    importance: Literal["normal", "important", "critical"] | None = None


class AnswerEffect(StrictModel):
    value: Scalar
    facts: ProcessingFacts


class ScenarioBranchProcessing(StrictModel):
    route: Key | None = None
    sla_profile: Key | None = None
    approval_required: StrictBool | None = None


class ScenarioSlaProfile(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    first_response_minutes: int = Field(ge=0, le=525600)
    resolution_minutes: int = Field(ge=0, le=525600)
    time_basis: Literal["calendar", "business"] = "calendar"
    calendar_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_calendar(self):
        if self.time_basis == "calendar" and self.calendar_id is not None:
            raise ValueError("calendar time must not select a business calendar")
        return self


class ScenarioRoute(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    queue_code: Annotated[str, Field(max_length=100)]


class ScenarioProcessingDefaults(StrictModel):
    route: Key | Literal[""]
    sla_profile: Key | Literal[""]


class ScenarioProcessing(StrictModel):
    sla_profiles: Annotated[dict[Key, ScenarioSlaProfile], Field(max_length=64)] = Field(default_factory=dict)
    routes: Annotated[dict[Key, ScenarioRoute], Field(max_length=64)] = Field(default_factory=dict)
    defaults: ScenarioProcessingDefaults
    assignment_mode: Literal["last_matching_branch"] = "last_matching_branch"


class TransitionButton(StrictModel):
    key: Key
    label: Annotated[str, Field(min_length=1, max_length=300)]


class Transition(StrictModel):
    button: TransitionButton | None = None
    to: Key
    when: Condition | None = None
    priority: int | None = Field(default=None, ge=1, le=10000)
    processing_facts: ProcessingFacts | None = None
    processing: ScenarioBranchProcessing | None = None


class FieldOption(StrictModel):
    value: Annotated[str, Field(min_length=1, max_length=100)]
    label: Annotated[str, Field(min_length=1, max_length=300)]


class ProcessMapping(StrictModel):
    roles: Annotated[list[Role], Field(max_length=11)] = Field(default_factory=list)
    fact_key: Key | None = None
    effects: Annotated[list[AnswerEffect], Field(max_length=100)] = Field(default_factory=list)


class FieldValidation(StrictModel):
    optional_when_legacy_missing: bool = False
    min_length: int | None = Field(default=None, ge=0, le=10000)
    max_length: int | None = Field(default=None, ge=1, le=10000)
    min_value: float | int | None = None
    max_value: float | int | None = None

    @model_validator(mode="after")
    def ordered_bounds(self):
        for lower, upper in ((self.min_length, self.max_length), (self.min_value, self.max_value)):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("lower validation bound exceeds upper")
        return self


class ScenarioAttachment(StrictModel):
    asset_id: Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
    name: Annotated[str, Field(min_length=1, max_length=255)]
    mime_type: Annotated[str, Field(min_length=1, max_length=100)]
    size_bytes: int = Field(ge=0, le=209715200)
    url: Annotated[str, Field(max_length=200)]

    @model_validator(mode="after")
    def canonical_url(self):
        if self.url != f"/api/web/request-scenario-assets/{self.asset_id}/download":
            raise ValueError("attachment URL must identify its canonical asset")
        return self


class RichDocument(StrictModel):
    type: Literal["doc"]
    content: list[dict] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_tree(self):
        from urllib.parse import urlsplit
        allowed = {"paragraph", "heading", "text", "bulletList", "orderedList", "listItem", "blockquote", "hardBreak", "image"}
        stack = [(node, 1) for node in self.content]
        count = 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if not isinstance(node, dict) or depth > 16 or count > 1000 or set(node) - {"type", "text", "attrs", "content", "marks"}:
                raise ValueError("invalid rich document structure")
            kind = node.get("type")
            if kind not in allowed:
                raise ValueError("unsupported rich document node")
            attrs = node.get("attrs") or {}
            if not isinstance(attrs, dict):
                raise ValueError("invalid node attributes")
            permitted = {"heading": {"level"}, "orderedList": {"start"}, "image": {"asset_id", "alt"}}.get(kind, set())
            if set(attrs) - permitted:
                raise ValueError("unsupported node attributes")
            if kind == "heading" and attrs.get("level") not in (1, 2, 3):
                raise ValueError("invalid heading")
            if kind == "image":
                import re
                if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", str(attrs.get("asset_id", ""))) or not isinstance(attrs.get("alt", ""), str) or len(attrs.get("alt", "")) > 500:
                    raise ValueError("invalid image asset")
            if kind == "text" and (not isinstance(node.get("text"), str) or len(node["text"]) > 10000):
                raise ValueError("invalid text")
            marks = node.get("marks", [])
            if not isinstance(marks, list) or len(marks) > 5:
                raise ValueError("invalid marks")
            for mark in marks:
                if not isinstance(mark, dict) or set(mark) - {"type", "attrs"} or mark.get("type") not in {"bold", "italic", "strike", "code", "link"}:
                    raise ValueError("unsupported mark")
                ma = mark.get("attrs") or {}
                if not isinstance(ma, dict) or (mark["type"] != "link" and ma) or (mark["type"] == "link" and (set(ma) != {"href"} or not isinstance(ma["href"], str) or len(ma["href"]) > 2048 or urlsplit(ma["href"]).scheme not in {"https", "http", "mailto"})):
                    raise ValueError("unsafe link")
            children = node.get("content", [])
            if not isinstance(children, list) or kind in {"text", "image", "hardBreak"} and children:
                raise ValueError("invalid child nodes")
            stack.extend((child, depth + 1) for child in children)
        return self


class ScenarioField(StrictModel):
    help_document: RichDocument | None = None
    key: Key
    type: FieldType
    label: Annotated[str, Field(min_length=1, max_length=300)]
    required: bool = False
    placeholder: str = Field(default="", max_length=500)
    help_text: str = Field(default="", max_length=2000)
    help_attachments: Annotated[list[ScenarioAttachment], Field(max_length=10)] = Field(default_factory=list)
    options: Annotated[list[FieldOption], Field(max_length=100)] = Field(default_factory=list)
    visible_when: Condition | None = None
    required_when: Condition | None = None
    validation: FieldValidation = Field(default_factory=FieldValidation)
    process_mapping: ProcessMapping = Field(default_factory=ProcessMapping)
    allow_unknown: bool = False
    group: Key | None = None
    group_title: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    aliases: Annotated[list[Key], Field(max_length=8)] = Field(default_factory=list)

    @model_validator(mode="after")
    def choice_options(self):
        if self.type in {"select", "radio", "multi_select"} and not self.options:
            raise ValueError("choice field requires options")
        if len({item.value for item in self.options}) != len(self.options):
            raise ValueError("option values must be unique")
        if len(set(self.process_mapping.roles)) != len(self.process_mapping.roles):
            raise ValueError("process roles must be unique")
        return self


class BlockBase(StrictModel):
    transition_mode: Literal["automatic", "buttons"] | None = None
    id: Key
    title: Annotated[str, Field(min_length=1, max_length=300)]
    transitions: Annotated[list[Transition], Field(max_length=30)] = Field(default_factory=list)


class FormPage(BlockBase):
    kind: Literal["form_page"]
    layout: Literal["single", "group", "section"] = "group"
    fields: Annotated[list[ScenarioField], Field(min_length=1, max_length=100)]


class InstructionContent(StrictModel):
    rich_document: RichDocument | None = None
    format: Literal["markdown", "plain"] = "markdown"
    body: Annotated[str, Field(min_length=1, max_length=10000)]
    attachments: Annotated[list[ScenarioAttachment], Field(max_length=10)] = Field(default_factory=list)


class Instruction(BlockBase):
    kind: Literal["instruction"]
    content: InstructionContent
    acknowledgment_required: bool = True


class Navigation(BlockBase):
    kind: Literal["navigation"]


class Sla(BlockBase):
    kind: Literal["sla"]
    processing_facts: ProcessingFacts = Field(default_factory=ProcessingFacts)
    sla_profile: Key | None = None
    policy_ref: CatalogCode | None = None


class PolicyAttachmentBase(StrictModel):
    """A setting link, never an executable employee step or flow edge."""
    id: Key
    title: Annotated[str, Field(min_length=1, max_length=300)]
    attached_to: Key | None = None

    @property
    def transitions(self):
        return ()

    @property
    def transition_mode(self):
        return None


class SlaAttachment(PolicyAttachmentBase):
    kind: Literal["sla_attachment"]
    processing_facts: ProcessingFacts = Field(default_factory=ProcessingFacts)
    sla_profile: Key | None = None
    policy_ref: CatalogCode | None = None


class RoutingAttachment(PolicyAttachmentBase):
    kind: Literal["routing_attachment"]
    route: Key | None = None
    policy_ref: CatalogCode | None = None


class Decision(BlockBase):
    kind: Literal["decision"]


class ResolutionCheck(BlockBase):
    kind: Literal["resolution_check"]


class Diagnostic(BlockBase):
    kind: Literal["diagnostic"]
    capability: str = Field(default="endpoint.context.diagnostic.collect", max_length=100)
    require_consent: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    execution_mode: Literal["unavailable"] = "unavailable"


class Review(BlockBase):
    kind: Literal["review"]


class SubmitTicket(BlockBase):
    kind: Literal["submit_ticket"]
    route: Key | None = None
    routing_policy_ref: CatalogCode | None = None
    sla_profile: Key | None = None
    policy_ref: CatalogCode | None = None

    @model_serializer(mode="wrap")
    def omit_inherited_sla(self, handler):
        raw = handler(self)
        for key in ("sla_profile", "policy_ref", "route", "routing_policy_ref"):
            if raw.get(key) is None:
                raw.pop(key, None)
        return raw


class Finish(BlockBase):
    kind: Literal["finish"]
    message: str = Field(default="Проблема решена без обращения", max_length=2000)


Block = Annotated[FormPage | Instruction | Navigation | Sla | SlaAttachment | RoutingAttachment | Decision | ResolutionCheck | Diagnostic | Review | SubmitTicket | Finish, Field(discriminator="kind")]


class ProcessBinding(StrictModel):
    request_template_key: CatalogCode
    priority_source: Literal["existing_server_policy_runtime"] = "existing_server_policy_runtime"
    policy_refs: Annotated[dict[Literal["priority", "routing", "sla", "ola", "approval", "notification", "closure", "visibility"], CatalogCode], Field(max_length=8)] = Field(default_factory=dict)


class ScenarioEntryPoint(StrictModel):
    key: Key
    title: Annotated[str, Field(min_length=1, max_length=300)]
    description: str = Field(default="", max_length=2000)
    category_id: Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")] | None = None
    synonyms: Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=20)] = Field(default_factory=list)
    visibility: Literal["public", "internal", "restricted"] = "public"
    enabled: StrictBool = True
    target_block_id: Key
    reported_symptom: str = Field(default="", max_length=2000)


class EditorPosition(StrictModel):
    x: float | int = Field(ge=-100000, le=100000)
    y: float | int = Field(ge=-100000, le=100000)


class PendingCatalogEntrance(StrictModel):
    key: Key
    title: Annotated[str, Field(min_length=1, max_length=300)]
    position: EditorPosition


class ScenarioEditorLayout(StrictModel):
    positions: Annotated[dict[Key, EditorPosition], Field(max_length=257)] = Field(default_factory=dict)
    pending_entrances: Annotated[list[PendingCatalogEntrance], Field(max_length=64)] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def omit_empty_pending(self, handler):
        raw = handler(self)
        if not self.pending_entrances:
            raw.pop("pending_entrances", None)
        return raw


class ScenarioDraftDefinition(StrictModel):
    schema_version: Literal[1, 2, 3, 4] = 1
    execution_semantics: Literal[1, 2, 3] | None = None
    scenario_key: Key
    service_code: CatalogCode
    offering_full_code: Annotated[str, Field(max_length=220, pattern=r"^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")]
    category_id: Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")] | None = None
    title: Annotated[str, Field(min_length=1, max_length=300)]
    description: str = Field(default="", max_length=2000)
    entry_block_id: Key | None = None
    entry_points: Annotated[list[ScenarioEntryPoint], Field(max_length=64)] = Field(default_factory=list)
    editor_layout: ScenarioEditorLayout = Field(default_factory=ScenarioEditorLayout)
    blocks: Annotated[list[Block], Field(max_length=256)] = Field(default_factory=list)
    process_binding: ProcessBinding
    processing: ScenarioProcessing | None = None
    publish_offering: StrictBool = False

    @model_serializer(mode="wrap")
    def preserve_legacy_wire_format(self, handler):
        raw = handler(self)
        if self.schema_version < 4:
            raw.pop("execution_semantics", None)
            for block in raw.get("blocks", []):
                block.pop("transition_mode", None)
                for edge in block.get("transitions", []):
                    edge.pop("button", None)
                if block.get("content"):
                    block["content"].pop("rich_document", None)
                for field in block.get("fields", []):
                    field.pop("help_document", None)
        return raw

    @model_validator(mode="before")
    @classmethod
    def check_input_limits(cls, raw):
        return _bounded_input(raw)

    @model_validator(mode="after")
    def validate_binding(self):
        if self.offering_full_code.partition(".")[0] != self.service_code:
            raise ValueError("offering must belong to the selected service")
        if type(self.schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if self.schema_version == 4 and self.execution_semantics is None:
            self.execution_semantics = 3
        if self.schema_version < 4 and (self.execution_semantics is not None or any(
            b.kind in {"navigation", "sla", "sla_attachment", "routing_attachment"} or b.kind == "submit_ticket" and (b.sla_profile is not None or b.policy_ref is not None or b.route is not None or b.routing_policy_ref is not None)
            or b.transition_mode is not None or any(e.button is not None for e in b.transitions)
            or (b.kind == "instruction" and b.content.rich_document is not None)
            or any(f.help_document is not None for f in getattr(b, "fields", ())) for b in self.blocks)):
            raise ValueError("v4 features require schema_version 4")
        if self.schema_version < 3 and (self.processing is not None or any(
            edge.processing is not None for block in self.blocks for edge in block.transitions
        )):
            raise ValueError("map-owned processing requires schema_version 3")
        if self.schema_version == 1 and any(
            edge.processing_facts is not None or any(field.process_mapping.effects for field in getattr(block, "fields", ()))
            for block in self.blocks for edge in (block.transitions or [Transition(to=block.id)])
        ):
            raise ValueError("processing effects require schema_version 2")
        return self


class ScenarioDefinition(ScenarioDraftDefinition):
    entry_block_id: Key
    blocks: Annotated[list[Block], Field(min_length=1, max_length=256)]


class ScenarioAnswerRequest(StrictModel):
    action_key: Key | None = None
    expected_block_id: Key
    revision: int = Field(ge=1)
    answers: dict[Key, Answer] = Field(default_factory=dict)
    current_result: Literal["yes", "no", "unknown", "acknowledged", "request_ticket"] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_input_limits(cls, raw):
        _bounded_input(raw)
        if isinstance(raw, dict) and len(json.dumps(raw, ensure_ascii=False).encode("utf-8")) > 65536:
            raise ValueError("answers exceed byte limit")
        return raw
