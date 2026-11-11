import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { InventoryInvitationAdmin } from "../../features/admin/registry/inventory-invitation-admin";
import { RegistryWorkspace } from "../../features/admin/registry/registry-workspace";

export function AdminRegistryPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const legacyTab = params.get("tab");
  if (["people", "access_groups", "password_reset", "profile_schema"].includes(legacyTab ?? "")) {
    const target = new URLSearchParams(params);
    target.set("tab", legacyTab === "access_groups" ? "access" : legacyTab === "people" ? "people" : "operations");
    if (legacyTab === "password_reset" || legacyTab === "profile_schema") target.set("operation_tab", legacyTab);
    return <Navigate replace to={`/app/admin/users?${target}`} />;
  }
  return <>
    <InventoryInvitationAdmin />
    <RegistryWorkspace
    initialTab={legacyTab}
    onOpenPerson={(personId) => navigate(`/app/admin/users?person=${encodeURIComponent(personId)}&tab=operations`)}
    onOpenAccount={login => navigate(`/app/admin/users?login=${encodeURIComponent(login)}`)}
    />
  </>;
}

export function RegistryPersonOperations({ personId }: { personId: string | null }) {
  const [params] = useSearchParams();
  return <RegistryWorkspace key={personId ?? "none"} personMode personId={personId} initialTab={params.get("operation_tab")} />;
}
