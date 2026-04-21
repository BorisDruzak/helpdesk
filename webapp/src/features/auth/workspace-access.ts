import type { WebSession } from "./api";


export type AppWorkspace = "support" | "admin";

const WORKSPACE_PATHS: Record<AppWorkspace, string> = {
  support: "/app/support",
  admin: "/app/admin"
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

  const fallbackWorkspace = session?.available_workspaces.find((workspace) => isWorkspace(workspace));
  return fallbackWorkspace ?? null;
}


export function resolveDefaultWorkspacePath(session: WebSession | null): string | null {
  const workspace = resolveDefaultWorkspace(session);
  return workspace ? getWorkspacePath(workspace) : null;
}


export function hasWorkspaceAccess(
  session: WebSession | null,
  workspace: AppWorkspace,
): boolean {
  return session?.available_workspaces.includes(workspace) ?? false;
}


export function resolveNextWorkspacePath(
  nextPath: string | null,
  session: WebSession | null,
): string | null {
  if (nextPath === "/app/support" && hasWorkspaceAccess(session, "support")) {
    return nextPath;
  }

  if (nextPath === "/app/admin" && hasWorkspaceAccess(session, "admin")) {
    return nextPath;
  }

  return resolveDefaultWorkspacePath(session);
}
