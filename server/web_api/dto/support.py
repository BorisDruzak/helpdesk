from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupportObserverCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_summary_endpoint: str
    drawer_tab: str


class SupportBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: str
    features: list[str]
    observer: SupportObserverCapabilities


class SupportFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class SupportQueueFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_options: list[SupportFilterOption]
    status_options: list[SupportFilterOption]


class SupportQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int
    selected_ticket_id: str | None


class SupportQueueTicketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str | None
    title: str
    status: str
    status_label: str
    queue_code: str | None
    assignee_id: str | None
    requester_display_name: str | None
    device_id: str | None
    updated_at: str | None
    created_at: str | None
    requires_operator_action: bool
    unread_user_messages: int


class SupportQueuePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    query: str
    status_filter: str
    summary: SupportQueueSummary
    filters: SupportQueueFilters
    tickets: list[SupportQueueTicketItem]


class SupportTicketQueueInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None
    code: str | None
    name: str | None


class SupportTicketQueueMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    role_in_queue: str | None


class SupportTicketDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str | None
    title: str
    description: str | None
    status: str
    status_label: str
    requester_display_name: str | None
    device_id: str | None
    queue: SupportTicketQueueInfo
    assignee_id: str | None
    updated_at: str | None
    created_at: str | None
    queue_members: list[SupportTicketQueueMember]


class SupportTicketObserverSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    root_trace_id: str | None = None
    trace_count: int
    active_trace_count: int
    error_trace_count: int
    signature_count: int
    latest_trace_at: str | None = None


class SupportTicketObserverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_summary_endpoint: str
    summary: SupportTicketObserverSummary


class SupportTicketReplyTo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_message_id: str | None = None
    preview: str | None = None
    sender_role: str | None = None
    sender_display_name: str | None = None
    ts: str | None = None


class SupportTicketMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str | None
    event_id: int | None
    event_type: str = "chat_message"
    from_role: str
    sender_display_name: str | None = None
    text: str
    ts: str | None
    visibility: str
    direction: str
    attachments: list[dict] = Field(default_factory=list)
    reply_to: SupportTicketReplyTo | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    result_summary: str | None = None
    result_preview: str | None = None


class SupportTicketPresence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_online: bool = False
    requester_last_seen_at: str | None = None
    requester_actor_ids: list[str] = Field(default_factory=list)
    support_online: bool = False
    support_last_seen_at: str | None = None
    support_actor_ids: list[str] = Field(default_factory=list)
    agent_online: bool = False


class SupportTicketDeviceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str | None = None
    hostname: str | None = None
    os: str | None = None
    agent_version: str | None = None
    last_seen_at: str | None = None
    online: bool = False


class SupportTicketOperationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    kind: str
    status: str
    tool_name: str | None = None
    command_name: str | None = None
    queued_at: str | None = None
    finished_at: str | None = None
    result_summary: str | None = None
    error_message: str | None = None


class SupportTicketSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_event_id: int
    notification_unread: int
    presence: SupportTicketPresence
    device: SupportTicketDeviceSnapshot
    latest_operations: list[SupportTicketOperationSnapshot] = Field(default_factory=list)


class SupportStatusAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class SupportTicketActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_options: list[SupportStatusAction] = Field(default_factory=list)
    can_send_internal_note: bool = False


class SupportMessageActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    message: SupportTicketMessage


class SupportStatusActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    status: str
    status_label: str


class SupportToolParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    description: str | None = None
    type: str = "string"
    required: bool = False
    default: Any | None = None


class SupportToolPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    label: str


class SupportToolItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    module_name: str | None = None
    description: str | None = None
    risk_level: str = "safe_read"
    requires_consent: bool = False
    install_required: bool = False
    source: str
    params_schema: list[SupportToolParameter] = Field(default_factory=list)
    presets: list[SupportToolPreset] = Field(default_factory=list)


class SupportTicketToolsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str | None = None
    tools: list[SupportToolItem] = Field(default_factory=list)


class SupportToolActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    device_id: str
    tool_name: str
    dispatch_status: str
    operation_id: str
    poll_url: str
    trace_id: str | None = None
    message: str


class SupportTicketDetailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: SupportTicketDetail
    observer: SupportTicketObserverPayload
    timeline: list[SupportTicketMessage]
    snapshot: SupportTicketSnapshot
    actions: SupportTicketActions
