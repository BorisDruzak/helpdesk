import { ModulesPanel } from "../../features/modules/modules-panel";
import { PageHeading } from "../../components/ui/page-heading";
import { useSession } from "../../features/auth/session-provider";
import { DiagnosticProviderConfigPanel } from "../../features/diagnostics/provider-config-panel";


export function AdminModulesPage() {
  const { session } = useSession();

  return (
    <section className="space-y-6">
      <PageHeading
        description="Реестр модулей, preferred versions и rollout policy теперь работают на настоящем backend. Визуально это тот же новый shell, а внутри — живой typed workbench."
        eyebrow="Registry"
        title="Модули"
      />

      <ModulesPanel permissions={session?.permissions ?? []} />
      <DiagnosticProviderConfigPanel />
    </section>
  );
}
