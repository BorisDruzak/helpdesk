import { describe, expect, it } from "vitest";

import {
  ADMIN_HOME_PATH,
  SUPPORT_HOME_PATH,
  findFirstVisibleDomainItem,
  getActiveNavItem,
  getActiveWorkspace,
  getVisibleNavigationDomains,
  isWorkspacePath,
} from "./navigation";
import {
  readWorkspaceHistoryPath,
  resolveNextWorkspacePath,
  resolveWorkspaceSwitchPath,
  writeWorkspaceHistoryPath,
} from "../features/auth/workspace-access";

const fullAdminPermissions = [
  "admin.access.view",
  "admin.forms.view",
  "admin.inventory.view",
  "admin.modules.view",
  "admin.observer.view",
  "admin.playbooks.view",
  "admin.registry.view",
  "settings.view",
];

const fullSession = {
  user_login: "admin1",
  actor_role: "admin",
  auth_type: "ui_token",
  default_workspace: "admin",
  available_workspaces: ["admin", "support"],
  permissions: ["ticket.queue.view", "workspace.support.view", ...fullAdminPermissions],
};

describe("navigation helpers", () => {
  it("detects workspace and active nav item for nested routes without query/hash noise", () => {
    expect(getActiveWorkspace("/app/tickets/T-1/passport/print?mode=full#top")).toBe("support");
    expect(getActiveWorkspace("/app/admin/inventory?panel=requests")).toBe("admin");
    expect(getActiveWorkspace("/app/help")).toBeNull();

    expect(getActiveNavItem("/app/tickets/T-1/passport/print")?.label).toBe("Тикеты");
    expect(getActiveNavItem("/app/admin/inventory?panel=requests")?.label).toBe("Инвентарь устройств");
    expect(getActiveNavItem("/app/admin/policy-health?service=mail")?.label).toBe("Проверка политик");
  });

  it("filters admin domain groups by permissions and hides empty groups", () => {
    const domains = getVisibleNavigationDomains("admin", ["admin.access.view"]);

    expect(domains.map((domain) => domain.label)).toEqual(["Система"]);
    expect(domains[0]?.items.map((item) => item.label)).toEqual(["Доступ"]);
  });

  it("returns the first available item inside a domain with permission filtering", () => {
    expect(findFirstVisibleDomainItem("catalog-intake", fullAdminPermissions)?.to).toBe(
      "/app/admin/request-template-studio",
    );
    expect(findFirstVisibleDomainItem("knowledge", fullAdminPermissions)?.to).toBe("/app/admin/knowledge");
    expect(findFirstVisibleDomainItem("catalog-intake", [])).toBeNull();
  });

  it("keeps device operations last in the devices domain", () => {
    const devicesDomain = getVisibleNavigationDomains("admin", fullAdminPermissions).find(
      (domain) => domain.id === "devices-agents",
    );

    expect(devicesDomain?.items.map((item) => item.to)).toContain("/app/admin/tech");
    expect(devicesDomain?.items.at(-1)?.label).toBe("Операции устройства");
  });

  it("recognizes the migrated tech panel as an admin navigation item", () => {
    const activeItem = getActiveNavItem("/app/admin/tech?panel=logs", fullAdminPermissions);

    expect(activeItem?.to).toBe("/app/admin/tech");
    expect(activeItem?.label).toBe("Техпанель");
    expect(activeItem?.domainId).toBe("devices-agents");
  });

  it("exposes AI integration as a dedicated admin navigation domain", () => {
    const domains = getVisibleNavigationDomains("admin", fullAdminPermissions);
    const aiDomain = domains.find((domain) => domain.id === "ai-integration");
    const activeItem = getActiveNavItem("/app/admin/ai-integration?tab=mcp", fullAdminPermissions);

    expect(aiDomain?.label).toBe("Интеграция ИИ");
    expect(aiDomain?.items.map((item) => item.to)).toEqual(["/app/admin/ai-integration"]);
    expect(activeItem?.label).toBe("MCP сервер");
  });

  it("exposes Knowledge AI settings inside the Knowledge domain", () => {
    const knowledgeDomain = getVisibleNavigationDomains("admin", fullAdminPermissions).find(
      (domain) => domain.id === "knowledge",
    );
    const activeItem = getActiveNavItem("/app/admin/knowledge/ai", fullAdminPermissions);

    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/ai");
    expect(activeItem?.to).toBe("/app/admin/knowledge/ai");
    expect(activeItem?.label).toBe("AI настройки");
  });

  it("recognizes workspace-owned paths without including public requester routes", () => {
    expect(SUPPORT_HOME_PATH).toBe("/app/support");
    expect(ADMIN_HOME_PATH).toBe("/app/admin");
    expect(isWorkspacePath("/app/knowledge?query=printer", "support")).toBe(true);
    expect(isWorkspacePath("/app/admin/forms#policy", "admin")).toBe(true);
    expect(isWorkspacePath("/app/help", "support")).toBe(false);
    expect(isWorkspacePath("/app/ticket/T-1", "support")).toBe(false);
  });

  it("stores and resolves workspace switch targets with safe fallbacks", () => {
    const storage = new Map<string, string>();
    const localStorageLike = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
    };

    expect(readWorkspaceHistoryPath("support", null)).toBeNull();
    writeWorkspaceHistoryPath("support", "/app/help", localStorageLike);
    expect(readWorkspaceHistoryPath("support", localStorageLike)).toBeNull();

    writeWorkspaceHistoryPath("support", "/app/knowledge?query=printer", localStorageLike);
    writeWorkspaceHistoryPath("admin", "/app/admin/forms#routing", localStorageLike);

    expect(resolveWorkspaceSwitchPath("support", fullSession, localStorageLike)).toBe(
      "/app/knowledge?query=printer",
    );
    expect(resolveWorkspaceSwitchPath("admin", fullSession, localStorageLike)).toBe(
      "/app/admin/forms#routing",
    );

    writeWorkspaceHistoryPath("admin", "/app/admin/observer", localStorageLike);
    expect(resolveWorkspaceSwitchPath("admin", { ...fullSession, permissions: [] }, localStorageLike)).toBe(
      ADMIN_HOME_PATH,
    );
  });

  it("keeps protected device pairing next paths after login", () => {
    expect(
      resolveNextWorkspacePath("/app/device/pair", {
        ...fullSession,
        default_workspace: "requester",
        available_workspaces: ["requester"],
        permissions: ["workspace.requester.view"],
      }),
    ).toBe("/app/device/pair");
    expect(
      resolveNextWorkspacePath("/app/device/register?pairing_id=pair-1", {
        ...fullSession,
        default_workspace: "requester",
        available_workspaces: ["requester"],
        permissions: ["workspace.requester.view"],
      }),
    ).toBe("/app/device/register?pairing_id=pair-1");
    expect(
      resolveNextWorkspacePath("https://example.test/app/device/register?pairing_id=pair-1", fullSession),
    ).toBe(ADMIN_HOME_PATH);
  });
});
