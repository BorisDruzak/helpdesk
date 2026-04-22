import { PageHeading } from "../../components/ui/page-heading";
import { FormsBuilderPanel } from "../../features/forms-builder/forms-builder-panel";


export function AdminFormsPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        description="Конструктор intake-форм остаётся в новом SaaS-слое, но читает и публикует реальный каталог форм через typed web boundary."
        eyebrow="Forms builder"
        title="Конструктор форм"
      />

      <FormsBuilderPanel />
    </section>
  );
}
