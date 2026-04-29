import { PageHeading } from "../../components/ui/page-heading";
import { useSession } from "../../features/auth/session-provider";
import { FormsBuilderPanel } from "../../features/forms-builder/forms-builder-panel";


export function AdminFormsPage() {
  const { session } = useSession();

  return (
    <section className="space-y-6">
      <PageHeading
        description="Конструктор intake-форм остаётся в новом SaaS-слое, но читает и публикует реальный каталог форм через typed web boundary."
        eyebrow="Forms builder"
        title="Конструктор форм"
      />

      <FormsBuilderPanel permissions={session?.permissions ?? []} />
    </section>
  );
}
