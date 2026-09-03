import { Suspense, type ReactNode } from "react";
import { Link, Navigate, Outlet, useLocation, type RouteObject } from "react-router-dom";

import { AppShell } from "./layouts/app-shell";
import {
  AdminCenterPage,
  AdminAiIntegrationPage,
  AdminChangesPage,
  AdminCapabilitiesPage,
  AdminDevicePage,
  AdminAccessPage,
  AdminFormsPage,
  AdminInventoryPage,
  AdminModulesPage,
  AdminObserverPage,
  AdminOperationDetailPage,
  AdminPlaybooksPage,
  AdminPolicyHealthPage,
  AdminProblemsPage,
  AdminQualityPage,
  AdminRegistryPage,
  AdminRequestTemplateStudioPage,
  ApprovalConsentCenterPage,
  AdminServiceCatalogPage,
  AdminTechPage,
  HelpPage,
  ReportsPage,
  RequesterDeviceLinkPage,
  RequesterDevicesPage,
  RequesterHomePage,
  RequesterNewRequestPage,
  RequesterProfilePage,
  RequesterTicketPage,
  RequesterTicketsPage,
  DevicePairCodePage,
  DevicePairingPage,
  SettingsPage,
  SupportCommandCenterPage,
  TicketDetailPage,
  TicketListPage,
  TicketPassportPrintPage,
} from "./routes/lazy-pages";
import { LoginPage } from "../features/auth/login-page";
import { RegisterPage } from "../features/auth/register-page";
import { useSession } from "../features/auth/session-provider";
import {
  hasWorkspaceAccess,
  resolveDefaultWorkspacePath,
  type AppWorkspace
} from "../features/auth/workspace-access";
import { hasPermission } from "../features/auth/permissions";
import {
  REQUESTER_DEVICES_PATH,
  REQUESTER_HOME_PATH,
  REQUESTER_NEW_PATH,
  REQUESTER_PROFILE_PATH,
  REQUESTER_TICKETS_PATH,
} from "./navigation";

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

function WorkspaceFallback() {
  return (
    <SessionState
      description="Подгружаем нужный раздел и данные для этой рабочей области."
      title="Загружаем рабочую область"
    />
  );
}

function PublicPageFallback() {
  return (
    <SessionState
      description="Подгружаем страницу обращения и публичный контракт тикета."
      title="Загружаем страницу"
    />
  );
}

function PublicPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PublicPageFallback />}>{children}</Suspense>;
}

function ProtectedDevicePage({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { status } = useSession();

  if (status === "loading") {
    return (
      <SessionState
        description="Проверяем web-сессию перед подтверждением устройства."
        title="Проверяем сессию"
      />
    );
  }

  if (status === "anonymous") {
    const nextPath = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate replace to={`/app/login?next=${encodeURIComponent(nextPath)}`} />;
  }

  return <Suspense fallback={<PublicPageFallback />}>{children}</Suspense>;
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
      <Suspense fallback={<WorkspaceFallback />}>
        <Outlet />
      </Suspense>
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
  permission?: string;
  workspace: AppWorkspace;
  children: ReactNode;
};

function WorkspaceAccessGate({ permission, workspace, children }: WorkspaceAccessGateProps) {
  const { session } = useSession();

  if (hasWorkspaceAccess(session, workspace) && (!permission || hasPermission(session, permission))) {
    return <>{children}</>;
  }

  const defaultPath = resolveDefaultWorkspacePath(session);
  if (!defaultPath) {
    return <NoWorkspacePage />;
  }

  return <Navigate replace to={defaultPath} />;
}

function RequesterLegacyRedirect({ target }: { target: string }) {
  const location = useLocation();
  return <Navigate replace to={`${target}${location.search}${location.hash}`} />;
}

function RequesterNotFoundPage() {
  return (
    <section aria-labelledby="requester-not-found-title" className="mx-auto max-w-3xl px-4 py-10">
      <p className="workspace-boot__eyebrow">Кабинет пользователя</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-950" id="requester-not-found-title">Раздел не найден</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        Этот раздел кабинета недоступен или был перенесен. Перейдите на главную страницу кабинета пользователя.
      </p>
      <Link className="mt-5 inline-flex items-center justify-center rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white" to={REQUESTER_HOME_PATH}>
        Вернуться на главную
      </Link>
    </section>
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
        path: "register",
        element: <RegisterPage />
      },
      {
        path: "help",
        element: (
          <PublicPage>
            <HelpPage />
          </PublicPage>
        )
      },
      {
        path: "ticket",
        element: (
          <PublicPage>
            <RequesterTicketPage />
          </PublicPage>
        )
      },
      {
        path: "ticket/:ticketId",
        element: (
          <PublicPage>
            <RequesterTicketPage />
          </PublicPage>
        )
      },
      {
        path: "device/pair",
        element: (
          <ProtectedDevicePage>
            <DevicePairCodePage />
          </ProtectedDevicePage>
        )
      },
      {
        path: "device/login",
        element: (
          <ProtectedDevicePage>
            <DevicePairingPage purpose="login" />
          </ProtectedDevicePage>
        )
      },
      {
        path: "device/register",
        element: (
          <ProtectedDevicePage>
            <DevicePairingPage purpose="registration" />
          </ProtectedDevicePage>
        )
      },
      {
        element: <ProtectedWorkspaceLayout />,
        children: [
          {
            index: true,
            element: <WorkspaceIndexRedirect />
          },
          {
            path: "requester",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterHomePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/new",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterNewRequestPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/tickets",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterTicketsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/tickets/:ticketId",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterTicketsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/profile",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterProfilePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/profile/setup",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterProfilePage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/devices",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterDevicesPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/devices/link",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterDeviceLinkPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/create",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterLegacyRedirect target={REQUESTER_NEW_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/dashboard",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterLegacyRedirect target={REQUESTER_HOME_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/device",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterLegacyRedirect target={REQUESTER_DEVICES_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/overview",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterLegacyRedirect target={REQUESTER_HOME_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/requests",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterLegacyRedirect target={REQUESTER_TICKETS_PATH} />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "requester/*",
            element: (
              <WorkspaceAccessGate workspace="requester">
                <RequesterNotFoundPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "support",
            element: (
              <WorkspaceAccessGate workspace="support">
                <SupportCommandCenterPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "support/approvals",
            element: (
              <WorkspaceAccessGate workspace="support">
                <ApprovalConsentCenterPage />
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
            path: "tickets/:ticketId/passport/print",
            element: (
              <WorkspaceAccessGate workspace="support">
                <TicketPassportPrintPage />
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
                <AdminCenterPage />
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
            path: "admin/operations/:operationId",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminOperationDetailPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/access",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminAccessPage />
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
            path: "admin/capabilities",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminCapabilitiesPage />
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
            path: "admin/request-template-studio",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminRequestTemplateStudioPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/service-catalog",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminServiceCatalogPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/policy-health",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminPolicyHealthPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/quality",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminQualityPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/problems",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminProblemsPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/changes",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminChangesPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/playbooks",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminPlaybooksPage />
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
          },
          {
            path: "admin/tech",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminTechPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/ai-integration",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <AdminAiIntegrationPage />
              </WorkspaceAccessGate>
            )
          },
          {
            path: "admin/settings",
            element: (
              <WorkspaceAccessGate workspace="admin">
                <SettingsPage />
              </WorkspaceAccessGate>
            )
          }
        ]
      }
    ]
  }
];
