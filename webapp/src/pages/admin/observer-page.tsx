import { PageHeading } from "../../components/ui/page-heading";
import { ObserverQuickPanel } from "../../features/tech/observer-quick-panel";


export function AdminObserverPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        description="Observer-вкладка теперь показывает реальные hot traces, деградации, dangerous flows и drilldown в том же интерфейсе, без моковых карточек."
        eyebrow="Observability"
        title="Observer"
      />

      <ObserverQuickPanel deviceId={null} deviceLabel="всему контуру администрирования" />
    </section>
  );
}
