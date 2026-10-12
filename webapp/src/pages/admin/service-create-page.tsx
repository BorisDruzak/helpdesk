import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageShell, PageHeader, ErrorState, LoadingState } from "../../components/ui-page/page-components";
import { useSession } from "../../features/auth/session-provider";
import { fetchScenarioCatalog } from "../../features/request-template-studio/scenario-api";
import { ScenarioOfferingForm } from "../../features/request-template-studio/scenario-offering-form";
import { useScenarioDirtyGuard } from "../../features/request-template-studio/use-scenario-dirty-guard";

export function AdminServiceCreatePage() {
  const { session } = useSession();
  const [params] = useSearchParams();
  const cache = useQueryClient();
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["scenario-catalog", "new-service"], queryFn: () => fetchScenarioCatalog() });
  const [dirty, setDirty] = useState(false);
  const [destination, setDestination] = useState<string | null>(null);
  useScenarioDirtyGuard(dirty && !destination);
  useEffect(() => { if (destination) void navigate(destination, { replace: true }); }, [destination, navigate]);
  if (destination) return <LoadingState label="Открываем страницу услуги" />;
  return <PageShell width="wide">
    <PageHeader title="Создать услугу" description="Услуга — карточка в каталоге сотрудника. Сначала создайте её с обычной формой; пошаговый сценарий можно добавить позже." actions={<Link className="text-sm underline" to="/app/admin/request-template-studio">Вернуться в каталог</Link>} />
    {session?.actor_role !== "admin" ? <p>Создание услуг доступно администратору.</p> : catalog.isPending ? <LoadingState label="Загрузка разделов и форм" /> : catalog.isError ? <ErrorState title="Каталог недоступен" message="Не удалось загрузить разделы услуг." onRetry={() => void catalog.refetch()} /> : catalog.data && <ScenarioOfferingForm standalone catalog={catalog.data} initialServiceCode={params.get("service") ?? ""} onDirty={setDirty} onCancel={() => setDestination("/app/admin/request-template-studio")} onDone={async offering => {
      await cache.invalidateQueries({ queryKey: ["scenario-catalog"] });
      setDestination(`/app/admin/request-template-studio/services/${encodeURIComponent(offering.full_code)}`);
    }} />}
  </PageShell>;
}
