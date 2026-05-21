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

function readFormsSidebarCollapsed() {
  if (typeof window === "undefined") {
    return true;
  }
  return window.localStorage.getItem(FORMS_BUILDER_SIDEBAR_STORAGE_KEY) !== "expanded";
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useSession();
  const hasSupport = hasWorkspaceAccess(session, "support");
  const hasAdmin = hasWorkspaceAccess(session, "admin");
  const isTicketWorkspaceRoute = /^\/app\/tickets(?:\/[^/]+)?\/?$/.test(location.pathname);
  const isFormsBuilderRoute = /^\/app\/admin\/forms\/?$/.test(location.pathname);
  const [formsSidebarCollapsed, setFormsSidebarCollapsed] = useState(readFormsSidebarCollapsed);
  const currentWorkspace = getActiveWorkspace(location.pathname) ?? "support";

  useEffect(() => {
    if (isFormsBuilderRoute) {
      setFormsSidebarCollapsed(readFormsSidebarCollapsed());
    }
  }, [isFormsBuilderRoute]);

  useEffect(() => {
    const currentPath = `${location.pathname}${location.search}${location.hash}`;
    rememberWorkspacePath(currentPath, session);
  }, [location.hash, location.pathname, location.search, session]);

  if (isTicketWorkspaceRoute) {
    return <div className="min-h-screen bg-[#07111f] text-slate-100">{children}</div>;
  }

  const workspaceOptions = [
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

  function handleFormsSidebarCollapsedChange(collapsed: boolean) {
    setFormsSidebarCollapsed(collapsed);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(FORMS_BUILDER_SIDEBAR_STORAGE_KEY, collapsed ? "collapsed" : "expanded");
    }
  }

  return (
    <div className="min-h-screen bg-app text-slate-950">
      <div className="flex min-h-screen">
        <AppSidebar
          collapsed={isFormsBuilderRoute ? formsSidebarCollapsed : false}
          hasAdminAccess={hasAdmin}
          hasSupportAccess={hasSupport}
          onCollapsedChange={handleFormsSidebarCollapsedChange}
          permissions={session?.permissions ?? []}
          showCollapseToggle={isFormsBuilderRoute}
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
