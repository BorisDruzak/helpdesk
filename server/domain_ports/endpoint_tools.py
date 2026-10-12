"""Immutable local intent; never a provider wire request supplied by the browser."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from .endpoint_module_contracts_generated import EndpointRecipeModuleSpecV1


class ToolRunRequestV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["module", "context_collection", "diagnostic"]
    module_key: str | None = None
    version: str | None = None
    inputs: dict[str, StrictStr | StrictInt] = Field(default_factory=dict, max_length=8)
    recipe: EndpointRecipeModuleSpecV1 | None = None
    profile: Literal["inventory_v1", "health_v1", "network_v1", "baseline_v1", "session_v1"] | None = None

    @model_validator(mode="after")
    def validate_kind(self):
        if self.kind == "module":
            if not self.module_key or not self.version or not self.recipe or self.recipe.module_key != self.module_key or self.profile:
                raise ValueError("module identity and recipe required")
        elif self.module_key or self.version or self.recipe or self.inputs:
            raise ValueError("module fields are not context parameters")
        if (self.kind == "context_collection") != (self.profile is not None):
            raise ValueError("context profile required only for collection")
        return self
