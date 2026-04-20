import { Navigate, Outlet, useLocation, type RouteObject } from "react-router-dom";

import { AppShell } from "./layouts/app-shell";
import { AdminWorkspacePage } from "../pages/admin";
import { SupportWorkspacePage } from "../pages/support";
import { LoginPage } from "../features/auth/login-page";
import { useSession } from "../features/auth/session-provider";


function ProtectedWorkspaceLayout() {
  const location = useLocation();
  const { status } = useSession();

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

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
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
            element: <SupportWorkspacePage />
          },
          {
            path: "support",
            element: <SupportWorkspacePage />
          },
          {
            path: "admin",
            element: <AdminWorkspacePage />
          }
        ]
      }
    ]
  }
];
