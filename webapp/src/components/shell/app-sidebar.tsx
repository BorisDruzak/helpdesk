import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";

import {
  ADMIN_HOME_PATH,
  REQUESTER_HOME_PATH,
  type AppNavItem,
  type AppWorkspaceId,
  canUseNavigationItemInContext,
  getActiveNavigationDomain,
  getActiveWorkspace,
  getVisibleNavigationDomains,
  getVisibleNavigationItems,
  isNavItemActive,
  resolveNavigationItemTarget,
} from "../../app/navigation";
import { cn } from "../../shared/ui/cn";

type AppSidebarProps = {
  collapsed?: boolean;
  hasAdminAccess: boolean;
  hasRequesterAccess?: boolean;
  hasSupportAccess: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  permissions?: string[];
  showCollapseToggle?: boolean;
};

const ADMIN_GROUP_STORAGE_KEY = "pc-client:admin-sidebar-open-groups";

function readOpenGroups() {
  if (typeof window === "undefined") {
    return [] as string[];
  }

  try {
    return JSON.parse(window.localStorage.getItem(ADMIN_GROUP_STORAGE_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function writeOpenGroups(groupIds: string[]) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ADMIN_GROUP_STORAGE_KEY, JSON.stringify(groupIds));
}

function resolveSidebarWorkspace({
  hasAdminAccess,
  hasRequesterAccess = false,
  hasSupportAccess,
  pathname,
}: {
  hasAdminAccess: boolean;
  hasRequesterAccess: boolean;
  hasSupportAccess: boolean;
  pathname: string;
}): AppWorkspaceId | null {
  const activeWorkspace = getActiveWorkspace(pathname);
  if (activeWorkspace === "requester" && hasRequesterAccess) {
    return "requester";
  }
  if (activeWorkspace === "admin" && hasAdminAccess) {
    return "admin";
  }
  if (activeWorkspace === "support" && hasSupportAccess) {
    return "support";
  }
  if (hasSupportAccess) {
    return "support";
  }
  if (hasAdminAccess) {
    return "admin";
  }
  if (hasRequesterAccess) {
    return "requester";
  }
  return null;
}

function SidebarNavLink({
  collapsed = false,
  item,
  currentPath,
}: {
  collapsed?: boolean;
  item: AppNavItem;
  currentPath: string;
}) {
  const Icon = item.icon;
  const isAvailable = canUseNavigationItemInContext(item, currentPath);
  const target = resolveNavigationItemTarget(item, currentPath);
  const isActive = isAvailable && isNavItemActive(item, currentPath);
  const title = `${item.label}: ${item.description}`;
  const content = (
    <>
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-panel bg-white/14 text-current transition-colors">
        <Icon className="h-4 w-4" />
      </span>
      <span className={cn("min-w-0 space-y-1", collapsed ? "sr-only" : "")}>
        <span className="block font-semibold leading-none">{item.label}</span>
        <span className="block text-xs leading-4 text-current/70">{item.description}</span>
      </span>
    </>
  );

  if (!isAvailable || !target) {
    return (
      <span
        aria-disabled="true"
        aria-label={item.label}
        className={cn(
          "flex cursor-not-allowed items-start gap-3 rounded-panel px-3 py-2.5 text-sm text-brand-50/45",
          collapsed ? "justify-center px-2" : "",
        )}
        title={collapsed ? `${title}. Откройте операции из инвентаря или карточки устройства` : undefined}
      >
        {content}
      </span>
    );
  }

  return (
    <Link
      aria-current={isActive ? "page" : undefined}
      aria-label={item.label}
      className={cn(
        "flex items-start gap-3 rounded-panel px-3 py-2.5 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-700",
        collapsed ? "justify-center px-2" : "",
        isActive ? "bg-white text-brand-900 shadow-soft" : "text-brand-50/90 hover:bg-white/10 hover:text-white",
      )}
      title={collapsed ? title : undefined}
      to={target}
    >
      {content}
    </Link>
  );
}

function SupportSidebar({
  collapsed,
  items,
  currentPath,
}: {
  collapsed: boolean;
  items: AppNavItem[];
  currentPath: string;
}) {
  return (
    <nav aria-label="Навигация поддержки" className="space-y-1">
      {items.map((item) => (
        <SidebarNavLink collapsed={collapsed} currentPath={currentPath} item={item} key={item.to} />
      ))}
    </nav>
  );
}

function AdminSidebar({
  collapsed,
  currentPath,
  permissions,
}: {
  collapsed: boolean;
  currentPath: string;
  permissions: string[];
}) {
  const activeDomain = getActiveNavigationDomain(currentPath, permissions);
  const domains = getVisibleNavigationDomains("admin", permissions);
  const primaryItems = getVisibleNavigationItems("admin", permissions, { includeWorkspaceHome: true }).filter(
    (item) => item.isWorkspaceHome,
  );
  const activeDomainId = activeDomain?.id;
  const [userOpenGroups, setUserOpenGroups] = useState<string[]>(() => {
    const storedGroups = readOpenGroups();
    return activeDomainId && !storedGroups.includes(activeDomainId) ? [...storedGroups, activeDomainId] : storedGroups;
  });

  useEffect(() => {
    if (!activeDomainId) {
      return;
    }

    setUserOpenGroups((current) => {
      if (current.includes(activeDomainId)) {
        return current;
      }
      const next = [...current, activeDomainId];
      writeOpenGroups(next);
      return next;
    });
  }, [activeDomainId]);

  function toggleGroup(groupId: string) {
    setUserOpenGroups((current) => {
      const next = current.includes(groupId) ? current.filter((id) => id !== groupId) : [...current, groupId];
      writeOpenGroups(next);
      return next;
    });
  }

  return (
    <nav aria-label="Навигация администрирования" className="space-y-4">
      {primaryItems.map((item) => (
        <SidebarNavLink collapsed={collapsed} currentPath={currentPath} item={item} key={item.to} />
      ))}

      <div className="space-y-2">
        {domains.map((domain) => {
          const isActiveGroup = activeDomain?.id === domain.id;
          const isOpen = userOpenGroups.includes(domain.id);
          const panelId = `admin-sidebar-${domain.id}`;
          const Icon = domain.icon;

          return (
            <section
              className={cn(
                "rounded-panel border border-white/10",
                isActiveGroup ? "bg-white/12" : "bg-white/5",
              )}
              key={domain.id}
            >
              <button
                aria-controls={panelId}
                aria-expanded={isOpen}
                className={cn(
                  "flex w-full items-center gap-2 rounded-panel px-3 py-2.5 text-left text-sm font-semibold text-white transition-colors hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-700",
                  collapsed ? "justify-center px-2" : "",
                )}
                onClick={() => toggleGroup(domain.id)}
                title={collapsed ? domain.label : undefined}
                type="button"
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className={collapsed ? "sr-only" : ""}>{domain.label}</span>
                <ChevronDown
                  className={cn(
                    "ml-auto h-4 w-4 shrink-0 transition-transform",
                    isOpen ? "rotate-180" : "",
                    collapsed ? "sr-only" : "",
                  )}
                />
              </button>

              {isOpen ? (
                <div className="space-y-1 px-1 pb-2" id={panelId}>
                  {domain.items.map((item) => (
                    <SidebarNavLink collapsed={collapsed} currentPath={currentPath} item={item} key={item.to} />
                  ))}
                </div>
              ) : null}
            </section>
          );
        })}
      </div>
    </nav>
  );
}

export function AppSidebar({
  collapsed = false,
  hasAdminAccess,
  hasRequesterAccess = false,
  hasSupportAccess,
  onCollapsedChange,
  permissions = [],
  showCollapseToggle = false,
}: AppSidebarProps) {
  const location = useLocation();
  const currentPath = `${location.pathname}${location.search}${location.hash}`;
  const workspace = resolveSidebarWorkspace({
    hasAdminAccess,
    hasRequesterAccess,
    hasSupportAccess,
    pathname: location.pathname,
  });
  const ToggleIcon = collapsed ? ChevronRight : ChevronLeft;
  const supportItems = useMemo(
    () => getVisibleNavigationItems("support", permissions, { includeWorkspaceHome: true }),
    [permissions],
  );
  const requesterItems = useMemo(
    () => getVisibleNavigationItems("requester", permissions, { includeWorkspaceHome: true }),
    [permissions],
  );

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r border-white/10 bg-brand-700 px-3 py-4 text-white transition-[width] duration-200 lg:flex lg:flex-col",
        collapsed ? "w-16" : "w-[260px]",
      )}
    >
      <Link
        aria-label="pc_client HelpDesk workspace"
        className={cn(
          "mb-5 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-3 py-3 transition-colors hover:bg-white/12 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-700",
          collapsed ? "justify-center px-2" : "",
        )}
        title={collapsed ? "pc_client HelpDesk workspace" : undefined}
        to={workspace === "admin" ? ADMIN_HOME_PATH : workspace === "requester" ? REQUESTER_HOME_PATH : "/app/support"}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-panel bg-white text-brand-700 shadow-soft">
          <span className={cn("text-base font-black", collapsed ? "tracking-normal" : "tracking-[0.18em]")}>PC</span>
        </div>
        <div className={cn("min-w-0", collapsed ? "sr-only" : "")}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-100/70">pc_client</p>
          <p className="text-sm font-semibold leading-tight">
            {workspace === "admin" ? "Admin workspace" : workspace === "requester" ? "Requester workspace" : "Support workspace"}
          </p>
        </div>
      </Link>

      <div className="flex-1 overflow-y-auto pr-1">
        {workspace === "support" ? (
          <SupportSidebar collapsed={collapsed} currentPath={currentPath} items={supportItems} />
        ) : null}
        {workspace === "requester" ? (
          <SupportSidebar collapsed={collapsed} currentPath={currentPath} items={requesterItems} />
        ) : null}
        {workspace === "admin" ? (
          <AdminSidebar collapsed={collapsed} currentPath={currentPath} permissions={permissions} />
        ) : null}
      </div>

      {showCollapseToggle ? (
        <button
          aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          className={cn(
            "mt-4 flex items-center gap-3 rounded-panel border border-white/10 bg-white/8 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/14 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-700",
            collapsed ? "justify-center px-2" : "",
          )}
          onClick={() => onCollapsedChange?.(!collapsed)}
          title={collapsed ? "Развернуть меню" : "Свернуть меню"}
          type="button"
        >
          <ToggleIcon className="h-4 w-4" />
          <span className={collapsed ? "sr-only" : ""}>{collapsed ? "Развернуть меню" : "Свернуть меню"}</span>
        </button>
      ) : null}
    </aside>
  );
}
