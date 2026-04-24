import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation, type RouteObject } from "react-router-dom";

import { ADMIN_HOME_PATH, SUPPORT_HOME_PATH } from "./navigation";
import { AppShell } from "./layouts/app-shell";
import { LoginPage } from "../features/auth/login-page";
import { useSession } from "../features/auth/session-provider";
import {
  hasWorkspaceAccess,
  resolveDefaultWorkspacePath,
  type AppWorkspace
} from "../features/auth/workspace-access";
import { AdminDevicePage } from "../pages/admin/device-page";
import { AdminFormsPage } from "../pages/admin/forms-page";
import { AdminInventoryPage } from "../pages/admin/inventory-page";
import { AdminModulesPage } from "../pages/admin/modules-page";
import { AdminObserverPage } from "../pages/admin/observer-page";
import { AdminRegistryPage } from "../pages/admin/registry-page";
import { KnowledgeBasePage } from "../pages/knowledge";
import { ReportsPage } from "../pages/reports";
import { SettingsPage } from "../pages/settings";
import { TicketDetailPage } from "../pages/tickets/detail-page";
import { TicketListPage } from "../pages/tickets/list-page";

function SessionState({
  description,
  title
}: {
  description: string;
  title: string;
}) {
  return (
    <section className="flex min-h-screen items-center justify-center bg-app px-4 py-6">
      <div className="surface-panel max-w-xl px-8 py-10 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">pc_client</p>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
        <p className="mt-4 text-sm leading-7 text-slate-500">{description}</p>
      </div>
    </section>
  );
}

function NoWorkspacePage() {
  const { session } = useSession();

  return (
    <SessionState
      description={`Сеанс под ролью ${session?.actor_role ?? "unknown"} открыт, но для него пока не назначены новые рабочие зоны /app/*. Используйте корректную роль или дождитесь следующего среза доступа.`}
      title="Для этой роли рабочая зона пока не назначена"
    />
  );
}

function ProtectedWorkspaceLayout() {
  const location = useLocation();
  const { session, status } = useSession();

  if (status === "loading") {
    return (
      <SessionState
        description="Поднимаем web boundary и проверяем доступ к нужной рабочей зоне."
        title="Проверяем сессию"
      />
    );
  }

  if (status === "anonymous") {
    const nextPath = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate replace to={`/app/login?next=${encodeURIComponent(nextPath)}`} />;
  }

  if (!resolveDefaultWorkspacePath(session)) {
    return (
      <AppShell>
        <NoWorkspacePage />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function WorkspaceIndexRedirect() {
  const { session } = useSession();
  const defaultPath = resolveDefaultWorkspacePath(session);

  if (!defaultPath) {
    return <NoWorkspacePage />;
  }

  return <Navigate replace to={defaultPath} />;
}

type WorkspaceAccessGateProps = {
  workspace: AppWorkspace;
  children: ReactNode;
};

function WorkspaceAccessGate({ workspace, children }: WorkspaceAccessGateProps) {
  const { session } = useSession();

  if (hasWorkspaceAccess(session, workspace)) {
    return <>{children}</>;
  }

  const defaultPath = resolveDefaultWorkspacePath(session);
  if (!defaultPath) {
    return <NoWorkspacePage />;
  }

  return <Navigate replace to={defaultPath} />;
}

export const appRoutes: RouteObject[] = [
  {
    path: "/app",
    children: [
      {
        path: "login",
        element: <LoginPage />
      },
      {
        element: <ProtectedWorkspaceLayout />,
        children: [
          {
            index: true,
            element: <WorkspaceIndexRedirect />
          },
          {
            path: "support",
            element: (
              <WorkspaceAccessGate workspace="support">
                <Navigate replace to={SUPPORT_HOME_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "tickets",
            element: (
              <WorkspaceAccessGate workspace="support">
                <TicketListPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "tickets/:ticketId",
            element: (
              <WorkspaceAccessGate workspace="support">
                <TicketDetailPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "reports",
            element: (
              <WorkspaceAccessGate workspace="support">
                <ReportsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "knowledge",
            element: (
              <WorkspaceAccessGate workspace="support">
                <KnowledgeBasePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "settings",
            element: (
              <WorkspaceAccessGate workspace="support">
                <SettingsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <Navigate replace to={ADMIN_HOME_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/inventory",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminInventoryPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/device",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminDevicePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/registry",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminRegistryPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/modules",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminModulesPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/forms",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminFormsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/observer",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminObserverPage />
              </WorkspaceAccessGate>
            )
          }
        ]
      }
    ]
  }
];
