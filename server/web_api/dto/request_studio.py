from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from web_api.dto.admin import (
    AdminFormsSaveFormRequest,
    AdminHelpdeskFormSchemaItem,
    AdminHelpdeskRequestTemplateItem,
)


class RequestStudioOfferingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: str
    code: str
    public_title: str
    short_description: str | None = None
    description: str | None = None
    lifecycle_status: Literal["draft", "published", "retired"] = "draft"
    visibility: Literal["public", "internal", "restricted"] = "internal"
    request_type: str | None = None
    ticket_type_code: str | None = None
    request_template_key: str
    form_schema_id: str | None = None
    routing_policy_code: str | None = None
    sla_policy_code: str | None = None
    approval_policy_code: str | None = None
    closure_policy_code: str | None = None
    visibility_policy_code: str | None = None
    notification_policy_code: str | None = None
    default_queue_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RequestStudioDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: AdminFormsSaveFormRequest
    offering: RequestStudioOfferingDraft
    publish_service: bool = True
    publish_offering: bool = True
    confirmation_token: str | None = None


class RequestStudioIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    path: str | None = None
    suggested_fix: str | None = None


class RequestStudioValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "warning", "error"]
    can_publish: bool
    issues: list[RequestStudioIssue] = Field(default_factory=list)
    confirmation_token: str | None = None


class RequestStudioPublishStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    status: Literal["ready", "blocked", "will_update", "will_publish"]
    details: str | None = None


class RequestStudioDiffChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    label: str
    from_value: Any = None
    to_value: Any = None
    change_type: Literal["added", "removed", "changed", "unchanged"]
    severity: Literal["info", "warning", "danger"] = "info"


class RequestStudioObjectDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: Literal["form_schema", "request_template", "offering", "service"]
    object_code: str
    action: Literal["create", "update", "noop", "blocked"]
    title: str
    changes: list[RequestStudioDiffChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RequestStudioPublishPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation: RequestStudioValidationResult
    steps: list[RequestStudioPublishStep] = Field(default_factory=list)
    confirmation_token: str | None = None
    expires_at: str | None = None
    diffs: list[RequestStudioObjectDiff] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    message: str


class RequestStudioPublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation: RequestStudioValidationResult
    request_template: AdminHelpdeskRequestTemplateItem
    form_schema: AdminHelpdeskFormSchemaItem
    service: dict[str, Any] | None = None
    offering: dict[str, Any]
    message: str


class RequestStudioCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validate_endpoint: str = "/api/web/admin/request-studio/validate-draft"
    preview_endpoint: str = "/api/web/admin/request-studio/publish-preview"
    publish_endpoint: str = "/api/web/admin/request-studio/publish"
    safe_publish_available: bool = True
    requires_confirmation_token: bool = True
