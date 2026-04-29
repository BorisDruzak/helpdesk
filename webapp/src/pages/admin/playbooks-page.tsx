import { PageHeading } from "../../components/ui/page-heading";
import { useSession } from "../../features/auth/session-provider";
import { PlaybookBuilderPanel } from "../../features/playbooks/playbook-builder-panel";


export function AdminPlaybooksPage() {
  const { session } = useSession();

  return (
    <section className="space-y-6">
      <PageHeading
        description="Low-code сценарии диагностики собирают факты и прикладывают результат к тикету без изменения устройства."
        eyebrow="Playbooks"
        title="Плейбуки диагностики"
      />

      <PlaybookBuilderPanel permissions={session?.permissions ?? []} />
    </section>
  );
}
