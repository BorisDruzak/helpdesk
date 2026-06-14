import { describe, expect, it } from "vitest";

import {
  ADMIN_HOME_PATH,
  REQUESTER_KB_ASK_PATH,
  REQUESTER_KB_HOME_PATH,
  REQUESTER_KB_SEARCH_PATH,
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
  "knowledge.metadata.manage",
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
    expect(getActiveWorkspace("/app/kb")).toBe("requester");
    expect(getActiveWorkspace("/app/kb/search?query=vpn")).toBe("requester");
    expect(getActiveWorkspace("/app/help")).toBeNull();

    expect(getActiveNavItem("/app/tickets/T-1/passport/print")?.label).toBe("Тикеты");
    expect(getActiveNavItem("/app/admin/inventory?panel=requests")?.label).toBe("Инвентарь устройств");
    expect(getActiveNavItem("/app/admin/policy-health?service=mail")?.label).toBe("Проверка политик");
    expect(getActiveNavItem("/app/kb/search?query=vpn", ["workspace.requester.view"])?.label).toBe("База знаний");
    expect(getActiveNavItem("/app/kb/ask", ["workspace.requester.view"])?.label).toBe("AI-вопрос");
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

  it("shows the Knowledge metadata editor only to knowledge managers", () => {
    const knowledgeWithoutManager = getVisibleNavigationDomains("admin", [
      "admin.forms.view",
      "workspace.admin.view",
    ]).find((domain) => domain.id === "knowledge");
    const knowledgeManager = getVisibleNavigationDomains("admin", [
      "knowledge.metadata.manage",
      "workspace.admin.view",
    ]).find((domain) => domain.id === "knowledge");

    expect(knowledgeWithoutManager?.items.map((item) => item.to)).not.toContain(
      "/app/admin/knowledge/metadata",
    );
    expect(knowledgeManager?.items.map((item) => item.to)).toEqual(["/app/admin/knowledge/metadata"]);
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

  it("exposes Knowledge metadata editor, studio, indexing, AI and search settings inside the Knowledge domain", () => {
    const knowledgeDomain = getVisibleNavigationDomains("admin", fullAdminPermissions).find(
      (domain) => domain.id === "knowledge",
    );
    const sectionsItem = getActiveNavItem("/app/admin/knowledge/sections", fullAdminPermissions);
    const metadataItem = getActiveNavItem("/app/admin/knowledge/metadata", fullAdminPermissions);
    const studioItem = getActiveNavItem("/app/admin/knowledge/studio", fullAdminPermissions);
    const graphItem = getActiveNavItem("/app/admin/knowledge/graph", fullAdminPermissions);
    const importItem = getActiveNavItem("/app/admin/knowledge/import", fullAdminPermissions);
    const indexingItem = getActiveNavItem("/app/admin/knowledge/indexing", fullAdminPermissions);
    const aiItem = getActiveNavItem("/app/admin/knowledge/ai", fullAdminPermissions);
    const searchItem = getActiveNavItem("/app/admin/knowledge/search-settings", fullAdminPermissions);

    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/sections");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/metadata");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/studio");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/graph");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/import");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/indexing");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/ai");
    expect(knowledgeDomain?.items.map((item) => item.to)).toContain("/app/admin/knowledge/search-settings");
    expect(knowledgeDomain?.items.find((item) => item.to === "/app/admin/knowledge")?.description).toBe(
      "Разделы, статьи, версии, ACL и deflection",
    );
    expect(sectionsItem?.to).toBe("/app/admin/knowledge/sections");
    expect(sectionsItem?.label).toBe("Разделы базы знаний");
    expect(metadataItem?.to).toBe("/app/admin/knowledge/metadata");
    expect(metadataItem?.label).toBe("Метаданные знаний");
    expect(studioItem?.to).toBe("/app/admin/knowledge/studio");
    expect(studioItem?.label).toBe("Студия знаний");
    expect(graphItem?.to).toBe("/app/admin/knowledge/graph");
    expect(graphItem?.label).toBe("Граф знаний");
    expect(importItem?.to).toBe("/app/admin/knowledge/import");
    expect(importItem?.label).toBe("Импорт знаний");
    expect(indexingItem?.to).toBe("/app/admin/knowledge/indexing");
    expect(indexingItem?.label).toBe("Индексация");
    expect(aiItem?.to).toBe("/app/admin/knowledge/ai");
    expect(aiItem?.label).toBe("AI настройки");
    expect(searchItem?.to).toBe("/app/admin/knowledge/search-settings");
    expect(searchItem?.label).toBe("Настройки поиска");

    const requesterDomains = getVisibleNavigationDomains("requester", ["workspace.requester.view"]);
    expect(requesterDomains.flatMap((domain) => domain.items).map((item) => item.to)).not.toContain(
      "/app/admin/knowledge/metadata",
    );
    expect(requesterDomains.flatMap((domain) => domain.items).map((item) => item.to)).not.toContain(
      "/app/admin/knowledge/sections",
    );
  });

  it("recognizes workspace-owned paths without including public requester routes", () => {
    expect(SUPPORT_HOME_PATH).toBe("/app/support");
    expect(ADMIN_HOME_PATH).toBe("/app/admin");
    expect(REQUESTER_KB_HOME_PATH).toBe("/app/kb");
    expect(REQUESTER_KB_SEARCH_PATH).toBe("/app/kb/search");
    expect(REQUESTER_KB_ASK_PATH).toBe("/app/kb/ask");
    expect(isWorkspacePath("/app/knowledge?query=printer", "support")).toBe(true);
    expect(isWorkspacePath("/app/kb", "requester")).toBe(true);
    expect(isWorkspacePath("/app/kb/articles/vpn", "requester")).toBe(true);
    expect(isWorkspacePath("/app/kb/spaces/it", "requester")).toBe(true);
    expect(isWorkspacePath("/app/kb/tags/vpn", "requester")).toBe(true);
    expect(isWorkspacePath("/app/kb/search?q=vpn", "requester")).toBe(true);
    expect(isWorkspacePath("/app/kb/ask", "requester")).toBe(true);
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
