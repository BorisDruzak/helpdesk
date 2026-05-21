import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  BookOpen,
  Building2,
  ClipboardCheck,
  FileSearch,
  FolderKanban,
  Gauge,
  GitBranch,
  KeyRound,
  Layers3,
  MonitorCog,
  Radar,
  Route,
  Server,
  Settings2,
  ShieldCheck,
  Ticket,
  Workflow,
} from "lucide-react";

import { hasPermission } from "../features/auth/permissions";

export const SUPPORT_HOME_PATH = "/app/support";
export const ADMIN_HOME_PATH = "/app/admin";

export type AppWorkspaceId = "support" | "admin";
export type AppDomainId =
  | "support-primary"
  | "devices-agents"
  | "catalog-intake"
  | "knowledge"
  | "automation"
  | "service-management"
  | "system";

export type AppNavItem = {
  activePatterns?: string[];
  description: string;
  domainId: AppDomainId;
  icon: LucideIcon;
  isPrimary?: boolean;
  isWorkspaceHome?: boolean;
  label: string;
  order: number;
  permission?: string;
  requiresDeviceContext?: boolean;
  section: AppWorkspaceId;
  shortLabel?: string;
  to: string;
  workspace: AppWorkspaceId;
};

export type AppNavigationDomain = {
  description: string;
  icon: LucideIcon;
  id: AppDomainId;
  label: string;
  order: number;
  workspace: AppWorkspaceId;
};

export type VisibleNavigationDomain = AppNavigationDomain & {
  items: AppNavItem[];
};

export const appNavigationDomains: AppNavigationDomain[] = [
  {
    id: "support-primary",
    workspace: "support",
    label: "Support",
    description: "Рабочая зона оператора",
    icon: Ticket,
    order: 10,
  },
  {
    id: "devices-agents",
    workspace: "admin",
    label: "Устройства и агенты",
    description: "Инвентарь, карточки устройств, обновления и трассы",
    icon: MonitorCog,
    order: 10,
  },
  {
    id: "catalog-intake",
    workspace: "admin",
    label: "Каталог и заявки",
    description: "Услуги, формы, шаблоны и проверка политик",
    icon: FolderKanban,
    order: 20,
  },
  {
    id: "knowledge",
    workspace: "admin",
    label: "База знаний",
    description: "Статьи, версии, ACL и deflection",
    icon: BookOpen,
    order: 30,
  },
  {
    id: "automation",
    workspace: "admin",
    label: "Автоматизация",
    description: "Модули, возможности и сценарии",
    icon: Layers3,
    order: 40,
  },
  {
    id: "service-management",
    workspace: "admin",
    label: "Управление сервисом",
    description: "Качество, проблемы и изменения",
    icon: Gauge,
    order: 50,
  },
  {
    id: "system",
    workspace: "admin",
    label: "Система",
    description: "Реестры, доступ и настройки",
    icon: Settings2,
    order: 60,
  },
];

export const appNavigation: AppNavItem[] = [
  {
    label: "Рабочий центр",
    description: "Что требует внимания сейчас",
    icon: ClipboardCheck,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: SUPPORT_HOME_PATH,
    permission: "ticket.queue.view",
    order: 10,
    isPrimary: true,
    isWorkspaceHome: true,
  },
  {
    label: "Тикеты",
    description: "Очередь и карточка тикета",
    icon: Ticket,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: "/app/tickets",
    permission: "ticket.queue.view",
    activePatterns: ["/app/tickets/*"],
    order: 20,
  },
  {
    label: "Согласования",
    description: "Согласования, запросы согласия, рискованные действия, закрытие и переопределения политик",
    icon: KeyRound,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: "/app/support/approvals",
    permission: "ticket.queue.view",
    activePatterns: ["/app/support/approvals/*"],
    order: 30,
  },
  {
    label: "База знаний",
    description: "Статьи и категории",
    icon: BookOpen,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: "/app/knowledge",
    permission: "workspace.support.view",
    order: 30,
  },
  {
    label: "Отчёты",
    description: "KPI, сроки ответа и динамика",
    icon: BarChart3,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: "/app/reports",
    permission: "workspace.support.view",
    order: 40,
  },
  {
    label: "Настройки",
    description: "Политики и интеграции",
    icon: Settings2,
    section: "support",
    workspace: "support",
    domainId: "support-primary",
    to: "/app/settings",
    permission: "settings.view",
    order: 50,
  },
  {
    label: "Центр администрирования",
    description: "Карта доменов администрирования",
    icon: Gauge,
    section: "admin",
    workspace: "admin",
    domainId: "system",
    to: ADMIN_HOME_PATH,
    permission: "workspace.admin.view",
    order: 0,
    isPrimary: true,
    isWorkspaceHome: true,
  },
  {
    label: "Инвентарь устройств",
    shortLabel: "Инвентарь",
    description: "Список устройств и статус",
    icon: MonitorCog,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/inventory",
    permission: "admin.inventory.view",
    order: 10,
  },
  {
    label: "Карточка устройства",
    description: "Единая device card",
    icon: ShieldCheck,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/device",
    permission: "admin.inventory.view",
    order: 20,
  },
  {
    label: "Операции устройства",
    description: "Инвентаризация, агент, модули, outbox и трассы",
    icon: GitBranch,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/device-operations",
    permission: "admin.inventory.view",
    activePatterns: ["/app/admin/device-operations/*"],
    order: 90,
    requiresDeviceContext: true,
  },
  {
    label: "Обновления агента",
    description: "Build registry и rollout policy",
    icon: MonitorCog,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/agent-updates",
    permission: "admin.inventory.view",
    order: 40,
  },
  {
    label: "Observer",
    description: "Трассы и деградации",
    icon: Radar,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/observer",
    permission: "admin.observer.view",
    order: 50,
  },
  {
    label: "Техпанель",
    description: "Готовность стенда, безопасность, runtime, PostgreSQL, агенты, операции и smoke",
    icon: Server,
    section: "admin",
    workspace: "admin",
    domainId: "devices-agents",
    to: "/app/admin/tech",
    permission: "admin.observer.view",
    order: 55,
  },
  {
    label: "Каталог услуг",
    description: "Настройка услуг, вариантов и overrides",
    icon: FolderKanban,
    section: "admin",
    workspace: "admin",
    domainId: "catalog-intake",
    to: "/app/admin/service-catalog",
    permission: "admin.forms.view",
    order: 10,
  },
  {
    label: "Конструктор форм",
    description: "Формы и политики заявок",
    icon: Workflow,
    section: "admin",
    workspace: "admin",
    domainId: "catalog-intake",
    to: "/app/admin/forms",
    permission: "admin.forms.view",
    order: 20,
  },
  {
    label: "Проверка политик",
    description: "Policy Health и dry-run",
    icon: ClipboardCheck,
    section: "admin",
    workspace: "admin",
    domainId: "catalog-intake",
    to: "/app/admin/policy-health",
    permission: "admin.forms.view",
    order: 30,
  },
  {
    label: "Студия шаблонов",
    description: "Услуга, вариант, форма, политики и публикация",
    icon: ClipboardCheck,
    section: "admin",
    workspace: "admin",
    domainId: "catalog-intake",
    to: "/app/admin/request-template-studio",
    permission: "admin.forms.view",
    order: 40,
  },
  {
    label: "База знаний",
    description: "Пространства, статьи, версии, ACL и deflection",
    icon: BookOpen,
    section: "admin",
    workspace: "admin",
    domainId: "knowledge",
    to: "/app/admin/knowledge",
    permission: "admin.forms.view",
    order: 10,
  },
  {
    label: "Модули",
    description: "ZIP/SDK-модули агента",
    icon: Layers3,
    section: "admin",
    workspace: "admin",
    domainId: "automation",
    to: "/app/admin/modules",
    permission: "admin.modules.view",
    order: 10,
  },
  {
    label: "Возможности",
    description: "Диагностика, провайдеры, evidence",
    icon: Layers3,
    section: "admin",
    workspace: "admin",
    domainId: "automation",
    to: "/app/admin/capabilities",
    permission: "admin.modules.view",
    order: 20,
  },
  {
    label: "Сценарии",
    description: "Диагностика и guided actions поддержки",
    icon: Route,
    section: "admin",
    workspace: "admin",
    domainId: "automation",
    to: "/app/admin/playbooks",
    permission: "admin.playbooks.view",
    order: 30,
  },
  {
    label: "Качество",
    description: "CSAT, повторные открытия, QA и улучшения",
    icon: BarChart3,
    section: "admin",
    workspace: "admin",
    domainId: "service-management",
    to: "/app/admin/quality",
    permission: "admin.forms.view",
    order: 10,
  },
  {
    label: "Проблемы",
    description: "Кандидаты, RCA, известные ошибки и обходы",
    icon: FileSearch,
    section: "admin",
    workspace: "admin",
    domainId: "service-management",
    to: "/app/admin/problems",
    permission: "admin.forms.view",
    order: 20,
  },
  {
    label: "Изменения",
    description: "Риски, согласования, окна, задачи и PIR",
    icon: Workflow,
    section: "admin",
    workspace: "admin",
    domainId: "service-management",
    to: "/app/admin/changes",
    permission: "admin.forms.view",
    order: 30,
  },
  {
    label: "Реестры",
    description: "Люди, здания, кабинеты и сервисы",
    icon: Building2,
    section: "admin",
    workspace: "admin",
    domainId: "system",
    to: "/app/admin/registry",
    permission: "admin.registry.view",
    order: 10,
  },
  {
    label: "Доступ",
    description: "Роли, permissions и видимость",
    icon: KeyRound,
    section: "admin",
    workspace: "admin",
    domainId: "system",
    to: "/app/admin/access",
    permission: "admin.access.view",
    order: 20,
  },
  {
    label: "Настройки",
    description: "Уведомления и политики",
    icon: Settings2,
    section: "admin",
    workspace: "admin",
    domainId: "system",
    to: "/app/admin/settings",
    permission: "settings.view",
    order: 30,
  },
];

function normalizePath(path: string) {
  const withoutHash = path.split("#", 1)[0] ?? path;
  const withoutQuery = withoutHash.split("?", 1)[0] ?? withoutHash;
  if (withoutQuery.length > 1) {
    return withoutQuery.replace(/\/+$/, "");
  }
  return withoutQuery || "/";
}

export function getDeviceOperationsContext(path: string): string | null {
  const pathname = normalizePath(path);
  const basePath = "/app/admin/device-operations";
  if (pathname !== basePath && !pathname.startsWith(`${basePath}/`)) {
    return null;
  }

  const pathDeviceId = pathname.slice(basePath.length).replace(/^\/+/, "").split("/", 1)[0] ?? "";
  if (pathDeviceId) {
    return decodeURIComponent(pathDeviceId);
  }

  const query = path.split("#", 1)[0]?.split("?", 2)[1];
  if (!query) {
    return null;
  }

  const params = new URLSearchParams(query);
  return params.get("device_id") || params.get("device");
}

export function canUseNavigationItemInContext(item: AppNavItem, path: string): boolean {
  return !item.requiresDeviceContext || Boolean(getDeviceOperationsContext(path));
}

export function resolveNavigationItemTarget(item: AppNavItem, path: string): string | null {
  if (!item.requiresDeviceContext) {
    return item.to;
  }

  const deviceId = getDeviceOperationsContext(path);
  if (!deviceId) {
    return null;
  }

  return `/app/admin/device-operations/${encodeURIComponent(deviceId)}`;
}

function canShowItem(item: AppNavItem, permissions: string[]) {
  return !item.permission || hasPermission({ permissions }, item.permission);
}

function sortByOrder<T extends { order: number }>(items: T[]) {
  return [...items].sort((left, right) => left.order - right.order);
}

function pathMatchesPattern(pathname: string, pattern: string) {
  if (pattern.endsWith("/*")) {
    const base = pattern.slice(0, -2);
    return pathname === base || pathname.startsWith(`${base}/`);
  }

  return pathname === pattern;
}

export function getActiveWorkspace(path: string): AppWorkspaceId | null {
  const pathname = normalizePath(path);

  if (pathname === SUPPORT_HOME_PATH || pathname.startsWith("/app/tickets") || pathname === "/app/reports" || pathname === "/app/knowledge" || pathname === "/app/settings") {
    return "support";
  }

  if (pathname === ADMIN_HOME_PATH || pathname.startsWith("/app/admin/")) {
    return "admin";
  }

  return null;
}

export function isAdminRoute(pathname: string) {
  return getActiveWorkspace(pathname) === "admin";
}

export function isWorkspacePath(path: string, workspace: AppWorkspaceId): boolean {
  return getActiveWorkspace(path) === workspace;
}

export function isNavItemActive(item: AppNavItem, path: string) {
  const pathname = normalizePath(path);
  const itemPath = normalizePath(item.to);

  if (item.activePatterns?.some((pattern) => pathMatchesPattern(pathname, pattern))) {
    return true;
  }

  if (item.isWorkspaceHome) {
    return pathname === itemPath;
  }

  return pathname === itemPath || pathname.startsWith(`${itemPath}/`);
}

export function getVisibleNavigationItems(
  workspace: AppWorkspaceId,
  permissions: string[] = [],
  options: { includeWorkspaceHome?: boolean } = {},
): AppNavItem[] {
  const includeWorkspaceHome = options.includeWorkspaceHome ?? workspace === "support";
  return sortByOrder(
    appNavigation.filter(
      (item) =>
        item.workspace === workspace &&
        canShowItem(item, permissions) &&
        (includeWorkspaceHome || !item.isWorkspaceHome),
    ),
  );
}

export function getVisibleNavigationDomains(
  workspace: AppWorkspaceId,
  permissions: string[] = [],
): VisibleNavigationDomain[] {
  const visibleItems = getVisibleNavigationItems(workspace, permissions, { includeWorkspaceHome: false });
  return sortByOrder(appNavigationDomains.filter((domain) => domain.workspace === workspace))
    .map((domain) => ({
      ...domain,
      items: sortByOrder(visibleItems.filter((item) => item.domainId === domain.id)),
    }))
    .filter((domain) => domain.items.length > 0);
}

export function getActiveNavItem(path: string, permissions?: string[]): AppNavItem | null {
  const workspace = getActiveWorkspace(path);
  if (!workspace) {
    return null;
  }

  const items =
    permissions === undefined
      ? sortByOrder(appNavigation.filter((item) => item.workspace === workspace))
      : getVisibleNavigationItems(workspace, permissions, { includeWorkspaceHome: true });

  return [...items].reverse().find((item) => isNavItemActive(item, path)) ?? null;
}

export function getActiveNavigationDomain(
  path: string,
  permissions: string[] = [],
): VisibleNavigationDomain | null {
  const activeItem = getActiveNavItem(path, permissions);
  if (!activeItem || activeItem.isWorkspaceHome) {
    return null;
  }

  return getVisibleNavigationDomains(activeItem.workspace, permissions).find((domain) => domain.id === activeItem.domainId) ?? null;
}

export function findFirstVisibleDomainItem(domainId: AppDomainId, permissions: string[] = []): AppNavItem | null {
  const domain = appNavigationDomains.find((item) => item.id === domainId);
  if (!domain) {
    return null;
  }

  return (
    getVisibleNavigationItems(domain.workspace, permissions, { includeWorkspaceHome: false }).find(
      (item) => item.domainId === domainId,
    ) ?? null
  );
}

export function canAccessNavigationPath(path: string, permissions: string[] = []): boolean {
  const workspace = getActiveWorkspace(path);
  if (!workspace) {
    return false;
  }

  if (normalizePath(path) === ADMIN_HOME_PATH || normalizePath(path) === SUPPORT_HOME_PATH) {
    return true;
  }

  return getVisibleNavigationItems(workspace, permissions, { includeWorkspaceHome: true }).some((item) =>
    isNavItemActive(item, path),
  );
}

export function getWorkspaceLabel(pathname: string) {
  return isAdminRoute(pathname) ? "Администрирование" : "Поддержка";
}

export function getSearchPlaceholder(pathname: string) {
  const activeItem = getActiveNavItem(pathname);

  if (activeItem?.domainId === "devices-agents") {
    return "Поиск по устройствам, агентам и трассам";
  }

  if (activeItem?.domainId === "catalog-intake") {
    return "Поиск по услугам, формам и политикам";
  }

  if (activeItem?.domainId === "knowledge" || normalizePath(pathname) === "/app/knowledge") {
    return "Поиск по статьям и категориям";
  }

  if (isAdminRoute(pathname)) {
    return "Поиск по разделам администрирования";
  }

  return "Поиск по тикетам, клиентам и тегам";
}
