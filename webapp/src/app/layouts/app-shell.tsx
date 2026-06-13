import { startTransition, useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  getSearchPlaceholder,
  getActiveWorkspace,
} from "../navigation";
import { AppSidebar } from "../../components/shell/app-sidebar";
import { AppTopbar } from "../../components/shell/app-topbar";
import { DomainTabs } from "../../components/shell/domain-tabs";
import { useSession } from "../../features/auth/session-provider";
import {
  hasWorkspaceAccess,
  rememberWorkspacePath,
  resolveWorkspaceSwitchPath,
  type AppWorkspace,
} from "../../features/auth/workspace-access";

type AppShellProps = {
  children: ReactNode;
};

const ADMIN_SIDEBAR_STORAGE_KEY = "pc-client:admin-sidebar-collapsed";
const FORMS_BUILDER_SIDEBAR_STORAGE_KEY = "pc-client:forms-builder-sidebar-collapsed";

function deriveRoleLabel(value: string | null | undefined) {
  if (value === "admin") {
    return "Администратор";
  }

  if (value === "support") {
    return "Поддержка";
  }

  return value ?? "Оператор";
}

function readAdminSidebarCollapsed(isFormsBuilderRoute: boolean) {
  if (typeof window === "undefined") {
    return isFormsBuilderRoute;
  }
  const storedValue = window.localStorage.getItem(ADMIN_SIDEBAR_STORAGE_KEY);
  if (storedValue) {
    return storedValue === "collapsed";
  }
  if (isFormsBuilderRoute) {
    return window.localStorage.getItem(FORMS_BUILDER_SIDEBAR_STORAGE_KEY) !== "expanded";
  }
  return false;
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useSession();
  const hasSupport = hasWorkspaceAccess(session, "support");
  const hasAdmin = hasWorkspaceAccess(session, "admin");
  const hasRequester = hasWorkspaceAccess(session, "requester");
  const isTicketWorkspaceRoute = /^\/app\/tickets(?:\/[^/]+)?\/?$/.test(location.pathname);
  const isFormsBuilderRoute = /^\/app\/admin\/forms\/?$/.test(location.pathname);
  const currentWorkspace = getActiveWorkspace(location.pathname) ?? "support";
  const [adminSidebarCollapsed, setAdminSidebarCollapsed] = useState(() => readAdminSidebarCollapsed(isFormsBuilderRoute));
  const shouldManageSidebar = currentWorkspace === "admin";

  useEffect(() => {
    if (currentWorkspace === "admin") {
      setAdminSidebarCollapsed(readAdminSidebarCollapsed(isFormsBuilderRoute));
    }
  }, [currentWorkspace, isFormsBuilderRoute]);

  useEffect(() => {
    const currentPath = `${location.pathname}${location.search}${location.hash}`;
    rememberWorkspacePath(currentPath, session);
  }, [location.hash, location.pathname, location.search, session]);

  if (isTicketWorkspaceRoute) {
    return <div className="min-h-screen bg-[#07111f] text-slate-100">{children}</div>;
  }

  const workspaceOptions = [
    hasRequester ? { label: "Requester", value: "requester" } : null,
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
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ADMIN_SIDEBAR_STORAGE_KEY, collapsed ? "collapsed" : "expanded");
      if (isFormsBuilderRoute) {
        window.localStorage.setItem(FORMS_BUILDER_SIDEBAR_STORAGE_KEY, collapsed ? "collapsed" : "expanded");
      }
    }
  }

  function handleSidebarNavigate() {
    if (currentWorkspace === "admin") {
      handleAdminSidebarCollapsedChange(true);
    }
  }

  return (
    <div className="min-h-screen bg-app text-slate-950">
      <div className="flex min-h-screen">
        <AppSidebar
          collapsed={shouldManageSidebar ? adminSidebarCollapsed : false}
          hasAdminAccess={hasAdmin}
          hasRequesterAccess={hasRequester}
          hasSupportAccess={hasSupport}
          onCollapsedChange={handleAdminSidebarCollapsedChange}
          onNavigate={handleSidebarNavigate}
          permissions={session?.permissions ?? []}
          showCollapseToggle={shouldManageSidebar}
        />

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <AppTopbar
            canViewAdminConnectionRequests={hasAdmin}
            onLogout={() => void handleLogout()}
            onWorkspaceChange={handleWorkspaceChange}
            searchPlaceholder={getSearchPlaceholder(location.pathname)}
            userLogin={session?.user_login ?? "operator"}
            userRoleLabel={deriveRoleLabel(session?.actor_role)}
            workspaceOptions={workspaceOptions}
            workspaceValue={workspaceValue}
          />

          <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6">
            <DomainTabs permissions={session?.permissions ?? []} />
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
