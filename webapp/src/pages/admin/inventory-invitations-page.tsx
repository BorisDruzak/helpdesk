import { PageHeading } from "../../components/ui/page-heading";
import { InventoryInvitationAdmin } from "../../features/admin/registry/inventory-invitation-admin";
import { useSessionCapabilities } from "../../features/auth/use-session-capabilities";

export function AdminInventoryInvitationsPage() {
  const capabilities = useSessionCapabilities();
  return (
    <section className="space-y-4">
      <PageHeading eyebrow="Управление сервисом" title="Приглашения из инвентаризации"
        description="Выдавайте и отзывайте одноразовые коды регистрации сотрудников." />
      {capabilities?.inventory_invitation_enabled === false
        ? <p>Приглашения из инвентаризации недоступны.</p>
        : <InventoryInvitationAdmin />}
    </section>
  );
}
