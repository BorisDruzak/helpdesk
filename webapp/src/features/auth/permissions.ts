import type { WebSession } from "./api";

type PermissionSource = Pick<WebSession, "permissions"> | null | undefined;

export type PermissionDecision =
  | { allowed: true; reason: null }
  | { allowed: false; reason: string };

export function getPermissions(source: PermissionSource): string[] {
  return Array.isArray(source?.permissions) ? source.permissions : [];
}

export function hasPermission(source: PermissionSource, permission: string): boolean {
  return getPermissions(source).includes(permission);
}

export function hasAnyPermission(source: PermissionSource, permissions: string[]): boolean {
  return permissions.some((permission) => hasPermission(source, permission));
}

export function getMissingPermissionReason(permission: string): string {
  return `Недостаточно прав: ${permission}`;
}

export function requirePermission(source: PermissionSource, permission: string): PermissionDecision {
  if (hasPermission(source, permission)) {
    return { allowed: true, reason: null };
  }

  return { allowed: false, reason: getMissingPermissionReason(permission) };
}

export function requireAllPermissions(source: PermissionSource, permissions: string[]): PermissionDecision {
  const missing = permissions.find((permission) => !hasPermission(source, permission));
  if (!missing) {
    return { allowed: true, reason: null };
  }

  return { allowed: false, reason: getMissingPermissionReason(missing) };
}

export function getToolRiskPermission(riskLevel: string | null | undefined): string {
  return riskLevel === "high" || riskLevel === "dangerous"
    ? "module.tool.run.high_risk"
    : "module.tool.run.low_risk";
}

export function requireToolRunPermission(
  source: PermissionSource,
  riskLevel: string | null | undefined,
): PermissionDecision {
  return requireAllPermissions(source, ["ticket.tool.run", getToolRiskPermission(riskLevel)]);
}
