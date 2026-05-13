import { Layers3 } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { ModulesPanel } from "../../features/modules/modules-panel";
import { PageHeading } from "../../components/ui/page-heading";
import { useSession } from "../../features/auth/session-provider";
import { DiagnosticProviderConfigPanel } from "../../features/diagnostics/provider-config-panel";


export function AdminModulesPage() {
  const { session } = useSession();

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Link to="/app/admin/capabilities">
            <Button leadingIcon={<Layers3 className="h-4 w-4" />} variant="outline">
              Capability Studio
            </Button>
          </Link>
        }
        description="Реестр модулей, preferred versions и rollout policy теперь работают на настоящем backend. Визуально это тот же новый shell, а внутри — живой typed workbench."
        eyebrow="Registry"
        title="Модули"
      />

      <ModulesPanel permissions={session?.permissions ?? []} />
      <DiagnosticProviderConfigPanel />
    </section>
  );
}
