"""Fragment library commands; all writes use the existing Studio authorization."""
from typing import Annotated
from pydantic import Field, StrictInt, field_validator
from web_api.dto.request_scenario import Key, CatalogCode, StrictModel, ScenarioEditorLayout
from web_api.dto.request_scenario_admin import Identifier


class FragmentCreate(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=300)]
    source_scenario_id: Identifier
    block_ids: Annotated[list[Key], Field(min_length=1, max_length=256)]
    source_revision: Annotated[StrictInt, Field(ge=1)]


class FragmentMappings(StrictModel):
    blocks: dict[Key, Key] = Field(default_factory=dict, max_length=256)
    facts: dict[Key, Key] = Field(default_factory=dict, max_length=256)
    fields: dict[Key, Key] = Field(default_factory=dict, max_length=256)
    routes: dict[Key, Key] = Field(default_factory=dict, max_length=64)
    sla_profiles: dict[Key, Key] = Field(default_factory=dict, max_length=64)
    sla_policy_refs: dict[CatalogCode, CatalogCode] = Field(default_factory=dict, max_length=64)
    ola_policy_refs: dict[CatalogCode, CatalogCode] = Field(default_factory=dict, max_length=64)
    routing_policy_refs: dict[CatalogCode, CatalogCode] = Field(default_factory=dict, max_length=64)
    # Legacy SLA mappings remain accepted for saved fragments and older clients.
    policy_refs: dict[CatalogCode, CatalogCode] = Field(default_factory=dict, max_length=64)
    calendars: dict[Key, Annotated[StrictInt, Field(ge=1)]] = Field(default_factory=dict, max_length=64)


class FragmentInsert(StrictModel):
    revision: Annotated[StrictInt, Field(ge=1)]
    fragment_revision: Annotated[StrictInt, Field(ge=1)]
    position: dict
    mappings: FragmentMappings = Field(default_factory=FragmentMappings)

    @field_validator('position')
    @classmethod
    def validate_position(cls, value):
        return ScenarioEditorLayout.model_validate({'positions': {'fragment': value}}).model_dump()['positions']['fragment']
