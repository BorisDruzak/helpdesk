import { useSearchParams } from "react-router-dom";

import { PageHeading } from "../../components/ui/page-heading";
import { AgentUpdatesPanel } from "../../features/agent-updates/agent-updates-panel";


export function AdminAgentUpdatesPage() {
  const [searchParams] = useSearchParams();

  return (
    <section className="space-y-6">
      <PageHeading
        description="Реестр сборок Maria Agent, назначение preferred rollout по target и быстрый контекст выбранного устройства. Source of truth остаётся на серверной rollout policy."
        eyebrow="Agent updates"
        title="Обновления агента"
      />

      <AgentUpdatesPanel
        deviceId={searchParams.get("device")}
        initialTarget={searchParams.get("target")}
      />
    </section>
  );
}
