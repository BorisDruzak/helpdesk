import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation, type RouteObject } from "react-router-dom";

import { AppShell } from "./layouts/app-shell";
import { AdminWorkspacePage } from "../pages/admin";
import { SupportWorkspacePage } from "../pages/support";
import { LoginPage } from "../features/auth/login-page";
import { useSession } from "../features/auth/session-provider";
import {
  hasWorkspaceAccess,
  resolveDefaultWorkspacePath,
  type AppWorkspace
} from "../features/auth/workspace-access";


function NoWorkspacePage() {
  const { session } = useSession();

  return (
    <section className="session-state" aria-live="polite">
      <div className="session-state__panel">
        <p className="app-shell__eyebrow">pc_client</p>
        <h1>Для этой роли новое рабочее место пока не назначено</h1>
        <p>
          Сеанс под ролью <strong>{session?.actor_role ?? "unknown"}</strong> успешно открыт, но для неё
          ещё не включён новый интерфейс `/app/*`. Используйте legacy shell или дождитесь следующего
          среза cutover.
        </p>
      </div>
    </section>
  );
}


function ProtectedWorkspaceLayout() {
  const location = useLocation();
  const { session, status } = useSession();

  if (status === "loading") {
    return (
      <section className="session-state" aria-live="polite">
        <div className="session-state__panel">
          <p className="app-shell__eyebrow">pc_client</p>
          <h1>Проверяем сессию</h1>
          <p>Поднимаем новый web boundary и проверяем доступ к рабочему месту.</p>
        </div>
      </section>
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
                <SupportWorkspacePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminWorkspacePage />
              </WorkspaceAccessGate>
            )
          }
        ]
      }
    ]
  }
];
