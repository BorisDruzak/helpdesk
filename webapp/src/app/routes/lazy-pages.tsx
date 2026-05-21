import { lazy } from "react";

export const TicketListPage = lazy(() =>
  import("../../pages/tickets/list-page").then((module) => ({ default: module.TicketListPage })),
);

export const TicketDetailPage = lazy(() =>
  import("../../pages/tickets/list-page").then((module) => ({ default: module.TicketListPage })),
);

export const TicketPassportPrintPage = lazy(() =>
  import("../../pages/tickets/passport-print-page").then((module) => ({
    default: module.TicketPassportPrintPage,
  })),
);

export const SupportCommandCenterPage = lazy(() =>
  import("../../pages/support/command-center-page").then((module) => ({ default: module.SupportCommandCenterPage })),
);

export const ApprovalConsentCenterPage = lazy(() =>
  import("../../pages/support/approval-consent-center-page").then((module) => ({
    default: module.ApprovalConsentCenterPage,
  })),
);

export const ReportsPage = lazy(() =>
  import("../../pages/reports").then((module) => ({ default: module.ReportsPage })),
);

export const KnowledgeBasePage = lazy(() =>
  import("../../pages/knowledge").then((module) => ({ default: module.KnowledgeBasePage })),
);

export const HelpPage = lazy(() =>
  import("../../pages/help").then((module) => ({ default: module.HelpPage })),
);

export const RequesterTicketPage = lazy(() =>
  import("../../pages/requester-ticket").then((module) => ({ default: module.RequesterTicketPage })),
);

export const SettingsPage = lazy(() =>
  import("../../pages/settings").then((module) => ({ default: module.SettingsPage })),
);

export const AdminCenterPage = lazy(() =>
  import("../../pages/admin").then((module) => ({ default: module.AdminCenterPage })),
);

export const AdminDevicePage = lazy(() =>
  import("../../pages/admin/device-page").then((module) => ({ default: module.AdminDevicePage })),
);

export const AdminDeviceOperationsPage = lazy(() =>
  import("../../pages/admin/device-operations-page").then((module) => ({ default: module.AdminDeviceOperationsPage })),
);

export const AdminAgentUpdatesPage = lazy(() =>
  import("../../pages/admin/agent-updates-page").then((module) => ({ default: module.AdminAgentUpdatesPage })),
);

export const AdminAccessPage = lazy(() =>
  import("../../pages/admin/access-page").then((module) => ({ default: module.AdminAccessPage })),
);

export const AdminCapabilitiesPage = lazy(() =>
  import("../../pages/admin/capabilities-page").then((module) => ({ default: module.AdminCapabilitiesPage })),
);

export const AdminFormsPage = lazy(() =>
  import("../../pages/admin/forms-page").then((module) => ({ default: module.AdminFormsPage })),
);

export const AdminInventoryPage = lazy(() =>
  import("../../pages/admin/inventory-page").then((module) => ({ default: module.AdminInventoryPage })),
);

export const AdminModulesPage = lazy(() =>
  import("../../pages/admin/modules-page").then((module) => ({ default: module.AdminModulesPage })),
);

export const AdminObserverPage = lazy(() =>
  import("../../pages/admin/observer-page").then((module) => ({ default: module.AdminObserverPage })),
);

export const AdminPlaybooksPage = lazy(() =>
  import("../../pages/admin/playbooks-page").then((module) => ({ default: module.AdminPlaybooksPage })),
);

export const AdminPolicyHealthPage = lazy(() =>
  import("../../pages/admin/policy-health-page").then((module) => ({ default: module.AdminPolicyHealthPage })),
);

export const AdminServiceCatalogPage = lazy(() =>
  import("../../pages/admin/service-catalog-page").then((module) => ({ default: module.AdminServiceCatalogPage })),
);

export const AdminKnowledgePage = lazy(() =>
  import("../../pages/admin/knowledge-page").then((module) => ({ default: module.AdminKnowledgePage })),
);

export const AdminQualityPage = lazy(() =>
  import("../../pages/admin/quality-page").then((module) => ({ default: module.AdminQualityPage })),
);

export const AdminProblemsPage = lazy(() =>
  import("../../pages/admin/problems-page").then((module) => ({ default: module.AdminProblemsPage })),
);

export const AdminChangesPage = lazy(() =>
  import("../../pages/admin/changes-page").then((module) => ({ default: module.AdminChangesPage })),
);

export const AdminRegistryPage = lazy(() =>
  import("../../pages/admin/registry-page").then((module) => ({ default: module.AdminRegistryPage })),
);

export const AdminRequestTemplateStudioPage = lazy(() =>
  import("../../pages/admin/request-template-studio-page").then((module) => ({ default: module.AdminRequestTemplateStudioPage })),
);
