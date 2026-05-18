from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRecipePrimitive,
    AgentRecipeVersion,
    DiagnosticCapability,
    DiagnosticCapabilityVersion,
)
from diagnostics.agent_recipes import (
    AGENT_RECIPE_RUNNER_PROVIDER_ID,
    DEFAULT_AGENT_RECIPE_PRIMITIVES,
    normalize_recipe_platforms,
)
from diagnostics.capability_models import CapabilityDescriptor


@dataclass(slots=True)
class ResolvedAgentRecipe:
    capability: DiagnosticCapability
    capability_version: DiagnosticCapabilityVersion
    recipe_version: AgentRecipeVersion

    def descriptor(self) -> CapabilityDescriptor:
        descriptor = dict(self.capability.descriptor_json or {})
        evidence = dict(self.capability_version.evidence_mapping_json or descriptor.get("evidence") or {})
        deployment = dict(self.capability_version.deployment_json or {})
        descriptor.update(
            {
                "id": self.capability.capability_id,
                "title": self.capability.title,
                "description": self.capability.description or descriptor.get("description") or "",
                "provider_id": self.recipe_version.runner_provider_id,
                "provider_type": "agent_recipe_runner",
                "execution_target": "agent_recipe",
                "requires_device": True,
                "requires_agent_online": True,
                "supports_auto_install": True,
                "install_required_on_agent": False,
                "platforms": list(self.recipe_version.platforms_json or []),
                "params_schema": dict(self.capability_version.params_schema_json or descriptor.get("params_schema") or {}),
                "output_schema": dict(self.capability_version.output_schema_json or descriptor.get("output_schema") or {}),
                "output_contract": dict(self.capability_version.output_contract_json or descriptor.get("output_contract") or {}),
                "presentation_schema": dict(descriptor.get("presentation_schema") or {}),
                "evidence": evidence,
                "source": "agent_recipe",
                "runner_provider_id": self.recipe_version.runner_provider_id,
                "min_runner_version": self.recipe_version.min_runner_version,
                "primitive_id": self.recipe_version.primitive_id,
                "primitive_version": self.recipe_version.primitive_version,
                "recipe_version_id": self.recipe_version.id,
                "capability_version_id": self.capability_version.id,
                "supports_auto_install_runner": bool(deployment.get("supports_auto_install_runner", True)),
            }
        )
        return CapabilityDescriptor(**descriptor)


class AgentRecipeRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    def validate_platforms(self, platforms: list[object]) -> list[str]:
        return normalize_recipe_platforms(platforms)

    async def list_primitives(self, *, runner_provider_id: str = "agent_recipe_runner") -> list[AgentRecipePrimitive]:
        result = await self.session.execute(
            select(AgentRecipePrimitive)
            .where(AgentRecipePrimitive.runner_provider_id == runner_provider_id)
            .order_by(AgentRecipePrimitive.runner_version.desc(), AgentRecipePrimitive.primitive_id.asc())
        )
        return list(result.scalars().all())

    async def list_published_capabilities(self) -> list[ResolvedAgentRecipe]:
        stmt = (
            select(DiagnosticCapability, DiagnosticCapabilityVersion, AgentRecipeVersion)
            .join(DiagnosticCapabilityVersion, DiagnosticCapabilityVersion.capability_id == DiagnosticCapability.capability_id)
            .join(AgentRecipeVersion, AgentRecipeVersion.capability_version_id == DiagnosticCapabilityVersion.id)
            .where(
                DiagnosticCapability.execution_target == "agent_recipe",
                DiagnosticCapability.status.in_(["active", "available"]),
                DiagnosticCapabilityVersion.status == "published",
                DiagnosticCapabilityVersion.is_current.is_(True),
            )
            .order_by(DiagnosticCapability.capability_id.asc())
        )
        rows = await self.session.execute(stmt)
        return [ResolvedAgentRecipe(capability, version, recipe) for capability, version, recipe in rows.all()]

    async def get_recipe_capability(self, capability_id: str, version: Optional[str] = None) -> Optional[ResolvedAgentRecipe]:
        stmt = (
            select(DiagnosticCapability, DiagnosticCapabilityVersion, AgentRecipeVersion)
            .join(DiagnosticCapabilityVersion, DiagnosticCapabilityVersion.capability_id == DiagnosticCapability.capability_id)
            .join(AgentRecipeVersion, AgentRecipeVersion.capability_version_id == DiagnosticCapabilityVersion.id)
            .where(
                DiagnosticCapability.capability_id == capability_id,
                DiagnosticCapability.execution_target == "agent_recipe",
                DiagnosticCapabilityVersion.status == "published",
            )
        )
        if version:
            stmt = stmt.where(DiagnosticCapabilityVersion.version == version)
        else:
            stmt = stmt.where(DiagnosticCapabilityVersion.is_current.is_(True))
        row = (await self.session.execute(stmt.limit(1))).first()
        if row is None:
            return None
        capability, capability_version, recipe_version = row
        return ResolvedAgentRecipe(capability, capability_version, recipe_version)

    async def primitive_supported(self, *, runner_provider_id: str, runner_version: str, primitive_id: str) -> bool:
        row = await self.session.execute(
            select(AgentRecipePrimitive.id)
            .where(
                AgentRecipePrimitive.runner_provider_id == runner_provider_id,
                AgentRecipePrimitive.runner_version == runner_version,
                AgentRecipePrimitive.primitive_id == primitive_id,
            )
            .limit(1)
        )
        if row.first() is not None:
            return True
        if runner_provider_id == AGENT_RECIPE_RUNNER_PROVIDER_ID and runner_version == "1.0.0":
            return any(str(item.get("primitive_id")) == primitive_id for item in DEFAULT_AGENT_RECIPE_PRIMITIVES)
        return False
