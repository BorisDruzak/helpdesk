"""Strict admin editing inputs; publication and enablement are separate actions."""
from typing import Annotated, Literal

from pydantic import Field, StrictInt

from web_api.dto.request_scenario import CatalogCode, ScenarioAnswerRequest, ScenarioDraftDefinition, StrictModel

Identifier = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class CategoryInput(StrictModel):
    service_code: CatalogCode
    parent_id: Identifier | None = None
    slug: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")]
    title: Annotated[str, Field(min_length=1, max_length=300)]
    description: str = Field(default="", max_length=2000)
    sort_order: int = Field(default=0, ge=-100000, le=100000)
    visibility: Literal["public", "internal", "restricted"] = "internal"
    lifecycle_status: Literal["draft", "published", "archived"] = "draft"
    revision: Annotated[StrictInt, Field(ge=1)] | None = None


class ScenarioCreate(StrictModel):
    definition: ScenarioDraftDefinition


class ScenarioSave(ScenarioCreate):
    revision: Annotated[StrictInt, Field(ge=1)]


class RevisionInput(StrictModel):
    revision: Annotated[StrictInt, Field(ge=1)]


class SimulationInput(RevisionInput):
    steps: Annotated[list[ScenarioAnswerRequest], Field(max_length=256)] = Field(default_factory=list)
