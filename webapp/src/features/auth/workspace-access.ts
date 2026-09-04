import {
  ADMIN_HOME_PATH,
  REQUESTER_HOME_PATH,
  SUPPORT_HOME_PATH,
  canAccessNavigationPath,
  isWorkspacePath,
} from "../../app/navigation";
import type { WebSession } from "./api";

export type AppWorkspace = "support" | "admin" | "requester";

type WorkspaceStorage = Pick<Storage, "getItem" | "setItem">;

const WORKSPACE_PATHS: Record<AppWorkspace, string> = {
  support: SUPPORT_HOME_PATH,
  admin: ADMIN_HOME_PATH,
  requester: REQUESTER_HOME_PATH
};

const WORKSPACE_HISTORY_KEYS: Record<AppWorkspace, string> = {
  support: "pc-client:last-support-path",
  admin: "pc-client:last-admin-path",
  requester: "pc-client:last-requester-path"
};

function isWorkspace(value: string | null | undefined): value is AppWorkspace {
  return value === "support" || value === "admin" || value === "requester";
}

function getBrowserStorage(): WorkspaceStorage | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

function normalizePath(path: string) {
  const withoutHash = path.split("#", 1)[0] ?? path;
  const withoutQuery = withoutHash.split("?", 1)[0] ?? withoutHash;
  if (withoutQuery.length > 1) {
    return withoutQuery.replace(/\/+$/, "");
  }
  return withoutQuery || "/";
}

function isRequesterProfileSetupPath(path: string) {
  return normalizePath(path) === "/app/requester/profile/setup";
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
  if (nextPath && isRequesterProfileSetupPath(nextPath) && hasWorkspaceAccess(session, "requester")) {
    return nextPath;
  }

  if (nextPath && isWorkspacePath(nextPath, "support") && hasWorkspaceAccess(session, "support")) {
    return canAccessNavigationPath(nextPath, session?.permissions ?? []) ? nextPath : SUPPORT_HOME_PATH;
  }

  if (nextPath && isWorkspacePath(nextPath, "admin") && hasWorkspaceAccess(session, "admin")) {
    return canAccessNavigationPath(nextPath, session?.permissions ?? []) ? nextPath : ADMIN_HOME_PATH;
  }

  if (nextPath && isWorkspacePath(nextPath, "requester") && hasWorkspaceAccess(session, "requester")) {
    return canAccessNavigationPath(nextPath, session?.permissions ?? []) ? nextPath : REQUESTER_HOME_PATH;
  }

  return resolveDefaultWorkspacePath(session);
}

export function readWorkspaceHistoryPath(
  workspace: AppWorkspace,
  storage: WorkspaceStorage | null | undefined = getBrowserStorage()
): string | null {
  const value = storage?.getItem(WORKSPACE_HISTORY_KEYS[workspace]) ?? null;
  if (!value || !isWorkspacePath(value, workspace)) {
    return null;
  }

  return value;
}

export function writeWorkspaceHistoryPath(
  workspace: AppWorkspace,
  path: string,
  storage: WorkspaceStorage | null | undefined = getBrowserStorage()
): void {
  if (!storage || !isWorkspacePath(path, workspace)) {
    return;
  }

  storage.setItem(WORKSPACE_HISTORY_KEYS[workspace], path);
}

export function rememberWorkspacePath(
  path: string,
  session: WebSession | null,
  storage: WorkspaceStorage | null | undefined = getBrowserStorage()
): void {
  const workspace = isWorkspacePath(path, "admin")
    ? "admin"
    : isWorkspacePath(path, "support")
      ? "support"
      : isWorkspacePath(path, "requester")
        ? "requester"
        : null;
  if (!workspace || !hasWorkspaceAccess(session, workspace)) {
    return;
  }

  writeWorkspaceHistoryPath(workspace, path, storage);
}

export function resolveWorkspaceSwitchPath(
  workspace: AppWorkspace,
  session: WebSession | null,
  storage: WorkspaceStorage | null | undefined = getBrowserStorage()
): string | null {
  if (!hasWorkspaceAccess(session, workspace)) {
    return resolveDefaultWorkspacePath(session);
  }

  const storedPath = readWorkspaceHistoryPath(workspace, storage);
  if (storedPath && canAccessNavigationPath(storedPath, session?.permissions ?? [])) {
    return storedPath;
  }

  return getWorkspacePath(workspace);
}
