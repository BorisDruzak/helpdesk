import { startTransition, useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import {
  canUseNavigationItemInContext,
  getActiveWorkspace,
  getSearchPlaceholder,
  getVisibleNavigationItems,
  isNavItemActive,
  resolveNavigationItemTarget,
} from "../navigation";
import { AppSidebar } from "../../components/shell/app-sidebar";
import { AppTopbar } from "../../components/shell/app-topbar";
import { DomainTabs } from "../../components/shell/domain-tabs";
import { useSession } from "../../features/auth/session-provider";
import {loadPanelPreferences,savePanelPreferences} from "../../shared/ui/workspace-panel-preferences";
import {
  hasWorkspaceAccess,
  rememberWorkspacePath,
  resolveWorkspaceSwitchPath,
  type AppWorkspace,
} from "../../features/auth/workspace-access";

type AppShellProps = {
  children: ReactNode;
};


function deriveRoleLabel(value: string | null | undefined) {
  const role = String(value ?? "").trim().toLowerCase();
  if (role === "admin") {
    return "Администратор";
  }

  if (role === "support") {
    return "Поддержка";
  }

  if (role === "user" || role === "requester") {
    return "Пользователь";
  }

  return value ?? "Оператор";
}


function RequesterMobileNavigation({
  currentPath,
  permissions,
}: {
  currentPath: string;
  permissions: string[];
}) {
  const items = getVisibleNavigationItems("requester", permissions, { includeWorkspaceHome: true });
  if (!items.length) {
    return null;
  }

  return (
    <nav aria-label="Навигация заявителя" className="border-b border-border/80 bg-white lg:hidden">
      <div className="flex min-w-0 gap-1 overflow-x-auto px-3 py-2">
        {items.map((item) => {
          const isAvailable = canUseNavigationItemInContext(item, currentPath);
          const target = resolveNavigationItemTarget(item, currentPath);
          const isActive = isAvailable && isNavItemActive(item, currentPath);
          if (!isAvailable || !target) {
            return null;
          }
          const Icon = item.icon;
          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={[
                "inline-flex h-10 shrink-0 items-center gap-2 rounded-panel px-3 text-sm font-semibold transition-colors",
                item.isPrimary
                  ? "bg-brand-700 text-white hover:bg-brand-800"
                  : isActive
                    ? "bg-brand-50 text-brand-800"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
              ].join(" ")}
              key={item.to}
              to={target}
            >
              <Icon className="h-4 w-4" />
              {item.shortLabel ?? item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useSession();
  const hasSupport = hasWorkspaceAccess(session, "support");
  const hasAdmin = hasWorkspaceAccess(session, "admin");
  const hasRequester = hasWorkspaceAccess(session, "requester");
  const isTicketWorkspaceRoute = /^\/app\/tickets(?:\/[^/]+)?\/?$/.test(location.pathname);
  const isRequesterChatRoute = /^\/app\/requester\/tickets\/[^/]+\/?$/.test(location.pathname);
  const isFullHeightWorkspace = isTicketWorkspaceRoute || isRequesterChatRoute;
  const isFormsBuilderRoute = /^\/app\/admin\/forms\/?$/.test(location.pathname);
  const currentWorkspace = getActiveWorkspace(location.pathname) ?? "support";
  const account=session?.user_login??"";
  const [adminSidebarCollapsed, setAdminSidebarCollapsed] = useState(() => loadPanelPreferences(account,currentWorkspace,{navigationCollapsed:isFormsBuilderRoute,ticketListCollapsed:false}).navigationCollapsed);
  const shouldManageSidebar = currentWorkspace === "admin" || currentWorkspace === "support";

  useEffect(() => {
    setAdminSidebarCollapsed(loadPanelPreferences(account,currentWorkspace,{navigationCollapsed:isFormsBuilderRoute,ticketListCollapsed:false}).navigationCollapsed);
  }, [account,currentWorkspace,isFormsBuilderRoute]);

  useEffect(() => {
    const currentPath = `${location.pathname}${location.search}${location.hash}`;
    rememberWorkspacePath(currentPath, session);
  }, [location.hash, location.pathname, location.search, session]);

  const workspaceOptions = [
    hasRequester ? { label: "Кабинет пользователя", value: "requester" } : null,
    hasSupport ? { label: "Поддержка", value: "support" } : null,
    hasAdmin ? { label: "Администрирование", value: "admin" } : null
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  const workspaceValue = currentWorkspace;

  async function handleLogout() {
    await logout();
    startTransition(() => {
      navigate("/app/login", { replace: true });
    });
  }

  function handleWorkspaceChange(event: ChangeEvent<HTMLSelectElement>) {
    const workspace = event.target.value as AppWorkspace;
    const nextPath = resolveWorkspaceSwitchPath(workspace, session);
    if (!nextPath || nextPath === `${location.pathname}${location.search}${location.hash}`) {
      return;
    }

    startTransition(() => {
      navigate(nextPath);
    });
  }

  function handleAdminSidebarCollapsedChange(collapsed: boolean) {
    setAdminSidebarCollapsed(collapsed);
    savePanelPreferences(account,currentWorkspace,{...loadPanelPreferences(account,currentWorkspace),navigationCollapsed:collapsed});
  }

  return (
    <div className={`${isFullHeightWorkspace ? "h-dvh overflow-hidden" : "min-h-screen"} bg-app text-slate-950`}>
      <div className={`flex ${isFullHeightWorkspace ? "h-full min-h-0" : "min-h-screen"}`}>
        <AppSidebar
          collapsed={shouldManageSidebar ? adminSidebarCollapsed : false}
          hasAdminAccess={hasAdmin}
          hasRequesterAccess={hasRequester}
          hasSupportAccess={hasSupport}
          onCollapsedChange={handleAdminSidebarCollapsedChange}
          permissions={session?.permissions ?? []}
          showCollapseToggle={shouldManageSidebar}
        />

        <div className={`flex min-w-0 flex-1 flex-col ${isFullHeightWorkspace ? "h-full min-h-0" : "min-h-screen"}`}>
          <AppTopbar
            onLogout={() => void handleLogout()}
            onWorkspaceChange={handleWorkspaceChange}
            searchPlaceholder={getSearchPlaceholder(location.pathname)}
            userLogin={session?.user_login ?? "operator"}
            userRoleLabel={deriveRoleLabel(session?.actor_role)}
            workspaceOptions={workspaceOptions}
            workspaceValue={workspaceValue}
          />

          {currentWorkspace === "requester" ? (
            <RequesterMobileNavigation
              currentPath={`${location.pathname}${location.search}${location.hash}`}
              permissions={session?.permissions ?? []}
            />
          ) : null}

          <main className={isFullHeightWorkspace ? "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden" : "min-w-0 flex-1 overflow-x-hidden px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6"}>
            {!isFullHeightWorkspace ? <DomainTabs permissions={session?.permissions ?? []} /> : null}
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
