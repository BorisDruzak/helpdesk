import { PageHeading } from "../../components/ui/page-heading";
import { PlaybookBuilderPanel } from "../../features/playbooks/playbook-builder-panel";


export function AdminPlaybooksPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        description="Low-code сценарии диагностики собирают факты и прикладывают результат к тикету без изменения устройства."
        eyebrow="Playbooks"
        title="Плейбуки диагностики"
      />

      <PlaybookBuilderPanel />
    </section>
  );
}
