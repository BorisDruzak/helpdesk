import { ADMIN_HOME_PATH, SUPPORT_HOME_PATH } from "../../app/navigation";
import type { WebSession } from "./api";

export type AppWorkspace = "support" | "admin";

const WORKSPACE_PATHS: Record<AppWorkspace, string> = {
  support: SUPPORT_HOME_PATH,
  admin: ADMIN_HOME_PATH
};

function isWorkspace(value: string | null | undefined): value is AppWorkspace {
  return value === "support" || value === "admin";
}

export function getWorkspacePath(workspace: AppWorkspace): string {
  return WORKSPACE_PATHS[workspace];
}

export function resolveDefaultWorkspace(session: WebSession | null): AppWorkspace | null {
  if (isWorkspace(session?.default_workspace)) {
    return session.default_workspace;
  }

  const availableWorkspaces = Array.isArray(session?.available_workspaces)
    ? session.available_workspaces
    : [];
  const fallbackWorkspace = availableWorkspaces.find((workspace) => isWorkspace(workspace));
  return fallbackWorkspace ?? null;
}

export function resolveDefaultWorkspacePath(session: WebSession | null): string | null {
  const workspace = resolveDefaultWorkspace(session);
  return workspace ? getWorkspacePath(workspace) : null;
}

export function hasWorkspaceAccess(
  session: WebSession | null,
  workspace: AppWorkspace
): boolean {
  const availableWorkspaces = Array.isArray(session?.available_workspaces)
    ? session.available_workspaces
    : [];
  return availableWorkspaces.includes(workspace);
}

export function resolveNextWorkspacePath(
  nextPath: string | null,
  session: WebSession | null
): string | null {
  if (
    nextPath &&
    ["/app/support", "/app/tickets", "/app/reports", "/app/knowledge", "/app/settings"].some((prefix) =>
      nextPath.startsWith(prefix)
    ) &&
    hasWorkspaceAccess(session, "support")
  ) {
    return nextPath === "/app/support" ? SUPPORT_HOME_PATH : nextPath;
  }

  if (nextPath && nextPath.startsWith("/app/admin") && hasWorkspaceAccess(session, "admin")) {
    return nextPath === "/app/admin" ? ADMIN_HOME_PATH : nextPath;
  }

  return resolveDefaultWorkspacePath(session);
}
