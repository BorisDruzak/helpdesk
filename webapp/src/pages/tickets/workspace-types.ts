export type WorkspaceMode = "ticket" | "queue" | "tools" | "sla" | "passport";
export type WorkspaceRightTab = "context" | "sla" | "tools" | "knowledge" | "passport";

export type SupportWorkspaceLayoutState = {
  mode: WorkspaceMode;
  selectedTicketId?: string;
  selectedQueueId?: string;
  selectedViewId?: string;
  activeRightTab: WorkspaceRightTab;
  leftPanelWidth: number;
  rightPanelWidth: number;
  isContextCollapsed: boolean;
};

export const SUPPORT_WORKSPACE_LAST_MODE_STORAGE_KEY = "support-workspace-last-mode";
export const SUPPORT_WORKSPACE_ACTIVE_RIGHT_TAB_STORAGE_KEY = "support-workspace-active-right-tab";
export const SUPPORT_WORKSPACE_SELECTED_VIEW_STORAGE_KEY = "support-workspace-selected-view";
export const SUPPORT_WORKSPACE_SELECTED_QUEUE_STORAGE_KEY = "support-workspace-selected-queue";

export const workspaceModes: WorkspaceMode[] = ["ticket", "queue", "tools", "sla", "passport"];
export const workspaceRightTabs: WorkspaceRightTab[] = ["context", "sla", "tools", "knowledge", "passport"];

export function isWorkspaceMode(value: unknown): value is WorkspaceMode {
  return typeof value === "string" && workspaceModes.includes(value as WorkspaceMode);
}

export function isWorkspaceRightTab(value: unknown): value is WorkspaceRightTab {
  return typeof value === "string" && workspaceRightTabs.includes(value as WorkspaceRightTab);
}

export function getInitialWorkspaceMode(): WorkspaceMode {
  if (typeof window === "undefined") {
    return "ticket";
  }
  const stored = window.localStorage.getItem(SUPPORT_WORKSPACE_LAST_MODE_STORAGE_KEY);
  return isWorkspaceMode(stored) ? stored : "ticket";
}

export function getInitialWorkspaceRightTab(): WorkspaceRightTab {
  if (typeof window === "undefined") {
    return "context";
  }
  const stored = window.localStorage.getItem(SUPPORT_WORKSPACE_ACTIVE_RIGHT_TAB_STORAGE_KEY);
  return isWorkspaceRightTab(stored) ? stored : "context";
}

export function getInitialWorkspaceSelectedView(defaultViewId = "my_action"): string {
  if (typeof window === "undefined") {
    return defaultViewId;
  }
  return window.localStorage.getItem(SUPPORT_WORKSPACE_SELECTED_VIEW_STORAGE_KEY) || defaultViewId;
}

export function getInitialWorkspaceSelectedQueue(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(SUPPORT_WORKSPACE_SELECTED_QUEUE_STORAGE_KEY);
}

export function persistWorkspaceMode(mode: WorkspaceMode) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SUPPORT_WORKSPACE_LAST_MODE_STORAGE_KEY, mode);
}

export function persistWorkspaceRightTab(tab: WorkspaceRightTab) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SUPPORT_WORKSPACE_ACTIVE_RIGHT_TAB_STORAGE_KEY, tab);
}

export function persistWorkspaceSelectedView(viewId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SUPPORT_WORKSPACE_SELECTED_VIEW_STORAGE_KEY, viewId);
}

export function persistWorkspaceSelectedQueue(queueId: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (queueId) {
    window.localStorage.setItem(SUPPORT_WORKSPACE_SELECTED_QUEUE_STORAGE_KEY, queueId);
    return;
  }
  window.localStorage.removeItem(SUPPORT_WORKSPACE_SELECTED_QUEUE_STORAGE_KEY);
}
