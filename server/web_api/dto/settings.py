from pydantic import BaseModel, ConfigDict, Field


class WebSettingsCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_write: bool
    actor_role: str


class WebSettingsOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queues_count: int
    active_queues_count: int
    routing_rules_count: int
    active_routing_rules_count: int
    sla_policies_count: int
    calendars_count: int
    resolution_codes_count: int
    audit_records_count: int


class WebSettingsQueueMemberItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    role_in_queue: str | None = None


class WebSettingsOlaTargetItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str
    ack_min: int
    processing_min: int


class WebSettingsQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    is_triage: bool
    is_active: bool
    auto_assign_enabled: bool
    open_tickets_count: int
    enabled_routing_rules_count: int
    members: list[WebSettingsQueueMemberItem] = Field(default_factory=list)
    ola_targets: list[WebSettingsOlaTargetItem] = Field(default_factory=list)


class WebSettingsRoutingRuleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    enabled: bool
    priority_order: int
    condition_json: dict | None = None
    target_queue_id: int
    target_queue_name: str | None = None


class WebSettingsRoutingBuilderOperatorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class WebSettingsRoutingBuilderFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    source: str
    form_key: str | None = None
    form_title: str | None = None
    field_type: str | None = None


class WebSettingsRoutingBuilderFormFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    field: str
    type: str


class WebSettingsRoutingBuilderFormItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    request_kind: str
    title: str
    fields: list[WebSettingsRoutingBuilderFormFieldItem] = Field(default_factory=list)


class WebSettingsRoutingBuilderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operators: list[WebSettingsRoutingBuilderOperatorItem] = Field(default_factory=list)
    fields: list[WebSettingsRoutingBuilderFieldItem] = Field(default_factory=list)
    forms: list[WebSettingsRoutingBuilderFormItem] = Field(default_factory=list)


class WebSettingsSlaTargetItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str
    first_response_min: int
    resolution_min: int


class WebSettingsPriorityMatrixItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact: int
    urgency: int
    priority: str


class WebSettingsSlaPolicyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    timezone: str
    business_hours_json: dict | None = None
    calendar_id: int | None = None
    calendar_name: str | None = None
    is_default: bool
    is_active: bool
    open_tickets_count: int
    targets: list[WebSettingsSlaTargetItem] = Field(default_factory=list)
    priority_matrix: list[WebSettingsPriorityMatrixItem] = Field(default_factory=list)


class WebSettingsCalendarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    timezone: str
    weekly_hours_json: dict | None = None
    holidays_json: dict | None = None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class WebSettingsResolutionCodeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    is_active: bool
    sort_order: int
    usage_count: int


class WebSettingsAuditItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    actor_role: str
    trace_id: str | None = None
    created_at: str | None = None


class WebSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: WebSettingsCapabilities
    overview: WebSettingsOverview
    routing_builder: WebSettingsRoutingBuilderPayload
    queues: list[WebSettingsQueueItem] = Field(default_factory=list)
    routing_rules: list[WebSettingsRoutingRuleItem] = Field(default_factory=list)
    sla_policies: list[WebSettingsSlaPolicyItem] = Field(default_factory=list)
    calendars: list[WebSettingsCalendarItem] = Field(default_factory=list)
    resolution_codes: list[WebSettingsResolutionCodeItem] = Field(default_factory=list)
    audit: list[WebSettingsAuditItem] = Field(default_factory=list)
