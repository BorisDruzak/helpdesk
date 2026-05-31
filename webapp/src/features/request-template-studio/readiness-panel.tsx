import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import type { ReadinessSummary } from "./readiness";
import type { RequestStudioItem, StudioLinks } from "./studio-model";
import { statusTone, tech } from "./studio-model";

export function ReadinessPanel({
  item,
  readiness,
  expertLinks,
  onAutoFix,
}: {
  item: RequestStudioItem | null;
  readiness: ReadinessSummary;
  expertLinks: StudioLinks;
  onAutoFix?: () => void;
}) {
  return (
    <aside className="space-y-5">
      <section className="surface-panel p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">Готовность к публикации</h2>
          <Badge tone={statusTone(readiness.status)}>{readiness.status === "ok" ? "готово к экспертной публикации" : readiness.status === "warning" ? "есть рекомендации" : "заблокировано"}</Badge>
        </div>
        <ReadinessSection title="Блокирующие проблемы" items={readiness.blockers} empty="Блокирующих проблем нет." tone="danger" />
        <ReadinessSection title="Рекомендации" items={readiness.recommendations} empty="Рекомендаций нет." tone="warning" />
        <ReadinessSection title="Готово" items={readiness.ready} empty="Готовые блоки появятся после выбора обращения." tone="success" />
        <div className="mt-4 space-y-2">
          <Button className="w-full" onClick={onAutoFix} type="button" variant="secondary">
            Исправить автоматически
          </Button>
          <Link className="flex h-10 items-center justify-center rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700" to={expertLinks.serviceCatalog}>
            Открыть экспертную публикацию
          </Link>
        </div>
      </section>

      <section className="surface-panel p-5">
        <h2 className="text-lg font-semibold text-slate-950">Выбранный контекст</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <ContextRow label="Раздел" value={item?.service.public_title || item?.service.code} />
          <ContextRow label="Тип обращения" value={item?.offering?.public_title || item?.offering?.full_code} />
          <ContextRow label="Форма" value={item?.formPreview?.title} />
          <ContextRow label="Профиль" value={item?.processProfile.profileName} />
          <ContextRow label="Policy Health" value={item?.health?.health_status} />
        </dl>
      </section>

      <section className="surface-panel p-5">
        <h2 className="text-lg font-semibold text-slate-950">Экспертные ссылки</h2>
        <div className="mt-3 space-y-2">
          <ExpertLink href={expertLinks.serviceCatalog} label="Полный каталог услуг" />
          <ExpertLink href={expertLinks.forms} label="Полный конструктор форм" />
          <ExpertLink href={expertLinks.policyHealth} label="Проверка политик" />
        </div>
      </section>
    </aside>
  );
}

function ReadinessSection({
  title,
  items,
  empty,
  tone,
}: {
  title: string;
  items: string[];
  empty: string;
  tone: "danger" | "warning" | "success";
}) {
  return (
    <div className="mt-4">
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <div className="mt-2 space-y-2">
        {items.length ? (
          items.map((item) => (
            <div className="rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-700" key={item}>
              <Badge tone={tone}>{tone === "danger" ? "проблема" : tone === "warning" ? "совет" : "готово"}</Badge>
              <p className="mt-2">{item}</p>
            </div>
          ))
        ) : (
          <p className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            <CheckCircle2 className="h-4 w-4" />
            {empty}
          </p>
        )}
      </div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 text-right font-semibold text-slate-900">{tech(value)}</dd>
    </div>
  );
}

function ExpertLink({ href, label }: { href: string; label: string }) {
  return (
    <Link className="flex h-10 items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" to={href}>
      <span>{label}</span>
      <ExternalLink className="h-4 w-4" />
    </Link>
  );
}
