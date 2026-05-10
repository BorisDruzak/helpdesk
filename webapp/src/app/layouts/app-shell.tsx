import { startTransition, type ChangeEvent, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  ADMIN_HOME_PATH,
  SUPPORT_HOME_PATH,
  getSearchPlaceholder,
  isAdminRoute
} from "../navigation";
import { AppSidebar } from "../../components/shell/app-sidebar";
import { AppTopbar } from "../../components/shell/app-topbar";
import { useSession } from "../../features/auth/session-provider";
import { hasWorkspaceAccess } from "../../features/auth/workspace-access";

type AppShellProps = {
  children: ReactNode;
};

function deriveRoleLabel(value: string | null | undefined) {
  if (value === "admin") {
    return "Администратор";
  }

  if (value === "support") {
    return "Поддержка";
  }

  return value ?? "Оператор";
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useSession();
  const hasSupport = hasWorkspaceAccess(session, "support");
  const hasAdmin = hasWorkspaceAccess(session, "admin");
  const isTicketWorkspaceRoute = /^\/app\/tickets(?:\/[^/]+)?\/?$/.test(location.pathname);

  if (isTicketWorkspaceRoute) {
    return <div className="min-h-screen bg-[#07111f] text-slate-100">{children}</div>;
  }

  const workspaceOptions = [
    hasSupport ? { label: "Поддержка", value: SUPPORT_HOME_PATH } : null,
    hasAdmin ? { label: "Администрирование", value: ADMIN_HOME_PATH } : null
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  const workspaceValue = isAdminRoute(location.pathname) ? ADMIN_HOME_PATH : SUPPORT_HOME_PATH;

  async function handleLogout() {
    await logout();
    startTransition(() => {
      navigate("/app/login", { replace: true });
    });
  }

  function handleWorkspaceChange(event: ChangeEvent<HTMLSelectElement>) {
    startTransition(() => {
      navigate(event.target.value);
    });
  }

  return (
    <div className="min-h-screen bg-app text-slate-950">
      <div className="flex min-h-screen">
        <AppSidebar
          hasAdminAccess={hasAdmin}
          hasSupportAccess={hasSupport}
          permissions={session?.permissions ?? []}
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

          <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
