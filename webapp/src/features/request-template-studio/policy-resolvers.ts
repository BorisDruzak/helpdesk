import type { AdminHelpdeskModelPayload } from "../forms-builder/api";

export function resolveVisibilityPolicyCode(registry: AdminHelpdeskModelPayload | null | undefined) {
  const policies = (registry?.policies?.visibility ?? []).filter((policy) => policy.is_active);
  return policies.find((policy) => policy.code === "visibility_default")?.code ?? policies[0]?.code ?? null;
}
