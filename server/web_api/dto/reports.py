from pydantic import BaseModel, ConfigDict, Field


class WebReportsFilterOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class WebReportsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_options: list[WebReportsFilterOption] = Field(default_factory=list)


class WebReportsPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int
    start_at: str
    end_at: str
    queue_id: int | None = None


class WebReportsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_backlog_count: int
    closed_in_period_count: int
    avg_resolution_minutes: float | None = None
    first_response_compliance_percent: float | None = None
    resolution_compliance_percent: float | None = None
    reopen_rate_percent: float | None = None


class WebReportsTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: str
    created_count: int
    closed_count: int


class WebReportsBacklogPriorityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str
    priority_label: str
    count: int


class WebReportsAgingBucketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str
    count: int


class WebReportsStatusAgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    status_label: str
    count: int
    avg_age_seconds: int


class WebReportsTopQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: int | None = None
    queue_label: str
    open_count: int


class WebReportsTopRequesterItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_id: str
    count: int


class WebReportsRequestKindItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    count: int


class WebReportsRecentTicketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    ticket_code: str
    title: str
    status: str
    status_label: str
    queue_label: str
    requester_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WebReportsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: WebReportsPeriod
    filters: WebReportsFilters
    summary: WebReportsSummary
    daily_trend: list[WebReportsTrendPoint] = Field(default_factory=list)
    backlog_by_priority: list[WebReportsBacklogPriorityItem] = Field(default_factory=list)
    aging_buckets: list[WebReportsAgingBucketItem] = Field(default_factory=list)
    status_age: list[WebReportsStatusAgeItem] = Field(default_factory=list)
    top_queues: list[WebReportsTopQueueItem] = Field(default_factory=list)
    top_requesters: list[WebReportsTopRequesterItem] = Field(default_factory=list)
    request_kinds: list[WebReportsRequestKindItem] = Field(default_factory=list)
    recent_tickets: list[WebReportsRecentTicketItem] = Field(default_factory=list)
