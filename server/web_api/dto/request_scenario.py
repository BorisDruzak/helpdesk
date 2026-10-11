"""Additive, bounded Guided Request Studio v1 definitions and session inputs.

Only answers and the current block result are condition sources. The server owns
identity, policy selection, graph validation and execution; this module does not
dispatch operations or compute ticket policies.
"""
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Transition(StrictModel):
    to: Key
    when: Condition | None = None
    priority: int | None = Field(default=None, ge=1, le=10000)


class FieldOption(StrictModel):
    value: Annotated[str, Field(min_length=1, max_length=100)]
    label: Annotated[str, Field(min_length=1, max_length=300)]


class ProcessMapping(StrictModel):
    roles: Annotated[list[Role], Field(max_length=11)] = Field(default_factory=list)
    fact_key: Key | None = None


class FieldValidation(StrictModel):
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


class ScenarioField(StrictModel):
    key: Key
    type: FieldType
    label: Annotated[str, Field(min_length=1, max_length=300)]
    required: bool = False
    placeholder: str = Field(default="", max_length=500)
    help_text: str = Field(default="", max_length=2000)
    options: Annotated[list[FieldOption], Field(max_length=100)] = Field(default_factory=list)
    visible_when: Condition | None = None
    required_when: Condition | None = None
    validation: FieldValidation = Field(default_factory=FieldValidation)
    process_mapping: ProcessMapping = Field(default_factory=ProcessMapping)
    allow_unknown: bool = False
    group: Key | None = None
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
    id: Key
    title: Annotated[str, Field(min_length=1, max_length=300)]
    transitions: Annotated[list[Transition], Field(max_length=30)] = Field(default_factory=list)


class FormPage(BlockBase):
    kind: Literal["form_page"]
    layout: Literal["single", "group", "section"] = "group"
    fields: Annotated[list[ScenarioField], Field(min_length=1, max_length=100)]


class InstructionContent(StrictModel):
    format: Literal["markdown", "plain"] = "markdown"
    body: Annotated[str, Field(min_length=1, max_length=10000)]


class Instruction(BlockBase):
    kind: Literal["instruction"]
    content: InstructionContent
    acknowledgment_required: bool = True


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


class Finish(BlockBase):
    kind: Literal["finish"]
    message: str = Field(default="Проблема решена без обращения", max_length=2000)


Block = Annotated[FormPage | Instruction | Decision | ResolutionCheck | Diagnostic | Review | SubmitTicket | Finish, Field(discriminator="kind")]


class ProcessBinding(StrictModel):
    request_template_key: CatalogCode
    priority_source: Literal["existing_server_policy_runtime"] = "existing_server_policy_runtime"
    policy_refs: Annotated[dict[Literal["priority", "routing", "sla", "ola", "approval", "notification", "closure", "visibility"], CatalogCode], Field(max_length=8)] = Field(default_factory=dict)


class ScenarioDraftDefinition(StrictModel):
    schema_version: Literal[1] = 1
    scenario_key: Key
    service_code: CatalogCode
    offering_full_code: Annotated[str, Field(max_length=220, pattern=r"^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")]
    category_id: Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")] | None = None
    title: Annotated[str, Field(min_length=1, max_length=300)]
    description: str = Field(default="", max_length=2000)
    entry_block_id: Key | None = None
    blocks: Annotated[list[Block], Field(max_length=256)] = Field(default_factory=list)
    process_binding: ProcessBinding

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
        return self


class ScenarioDefinition(ScenarioDraftDefinition):
    entry_block_id: Key
    blocks: Annotated[list[Block], Field(min_length=1, max_length=256)]


class ScenarioAnswerRequest(StrictModel):
    expected_block_id: Key
    revision: int = Field(ge=1)
    answers: dict[Key, Answer] = Field(default_factory=dict)
    current_result: Literal["yes", "no", "unknown", "acknowledged"] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_input_limits(cls, raw):
        _bounded_input(raw)
        if isinstance(raw, dict) and len(json.dumps(raw, ensure_ascii=False).encode("utf-8")) > 65536:
            raise ValueError("answers exceed byte limit")
        return raw
