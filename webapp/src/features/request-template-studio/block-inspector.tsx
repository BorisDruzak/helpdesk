import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import type { ProcessBlock, RequestStudioItem, RequestStudioMode, StudioLinks } from "./studio-model";
import { statusLabel, statusTone, tech } from "./studio-model";

export function BlockInspector({
  block,
  item,
  mode,
  expertLinks,
}: {
  block: ProcessBlock | null;
  item: RequestStudioItem;
  mode: RequestStudioMode;
  expertLinks: StudioLinks;
}) {
  if (!block) {
    return null;
  }

  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-950">{block.title}</h2>
            <Badge tone={statusTone(block.status)}>{statusLabel(block.status)}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600">{block.explanation}</p>
        </div>
        <InspectorAction blockKey={block.key} expertLinks={expertLinks} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {detailsForBlock(block.key, item).map((detail) => (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3" key={detail.label}>
            <p className="text-xs font-semibold text-slate-500">{detail.label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{detail.value}</p>
            {detail.description ? <p className="mt-1 text-xs text-slate-600">{detail.description}</p> : null}
          </div>
        ))}
      </div>

      {mode !== "basic" ? (
        <details className="mt-4 rounded-md border border-slate-200 bg-white p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Технические детали</summary>
          <dl className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-3">
            <ContextRow label="service_code" value={item.technicalRefs.serviceCode} />
            <ContextRow label="offering_code" value={item.technicalRefs.offeringCode} />
            <ContextRow label="template_code" value={item.technicalRefs.templateCode} />
          </dl>
        </details>
      ) : null}
    </section>
  );
}

function InspectorAction({ blockKey, expertLinks }: { blockKey: ProcessBlock["key"]; expertLinks: StudioLinks }) {
  if (blockKey === "form") {
    return <Link className="rounded-pill bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700" to={expertLinks.forms}>Открыть экспертный конструктор</Link>;
  }
  if (blockKey === "publication" || blockKey === "identity") {
    return <Link className="rounded-pill bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700" to={expertLinks.serviceCatalog}>Открыть экспертную публикацию</Link>;
  }
  return <Link className="rounded-pill bg-surface-subtle px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-brand-50 hover:text-brand-800" to={expertLinks.policyHealth}>Открыть экспертную проверку</Link>;
}

function detailsForBlock(blockKey: ProcessBlock["key"], item: RequestStudioItem) {
  const template = item.template;
  const offering = item.offering;
  if (blockKey === "routing") {
    return [
      { label: "Кто будет выполнять заявку?", value: template?.routing_policy_code || offering?.routing_policy_code || "Не выбрано", description: "В базовом режиме показывается итоговое правило, без raw policy refs." },
      { label: "Fallback", value: "Единая очередь Service Desk", description: "Если правило не сработает, заявка должна попадать в triage." },
    ];
  }
  if (blockKey === "sla") {
    return [
      { label: "Когда оператор должен ответить?", value: template?.sla_policy_code ? "По SLA policy" : "Не выбрано" },
      { label: "Когда заявка должна быть решена?", value: template?.sla_policy_code || offering?.sla_policy_code || "Не выбрано" },
    ];
  }
  if (blockKey === "approval") {
    return [
      { label: "Нужно ли согласование?", value: template?.approval_policy_code || offering?.approval_policy_code ? "Требуется" : "Не требуется / рекомендуется проверить" },
      { label: "Источник согласования", value: "Руководитель, владелец услуги или группа", description: "Конкретный источник виден в экспертном Policy Health." },
    ];
  }
  if (blockKey === "closure") {
    return [
      { label: "Что требуется при закрытии?", value: template?.closure_policy_code || offering?.closure_policy_code ? "Результат и сообщение пользователю" : "Не настроено" },
      { label: "Подтверждение пользователя", value: "По политике закрытия" },
    ];
  }
  if (blockKey === "form") {
    return [
      { label: "Название формы", value: item.formPreview?.title ?? "Форма не найдена" },
      { label: "Поля", value: String(item.formPreview?.fields.length ?? 0), description: "JSON формы скрыт в базовом режиме." },
    ];
  }
  if (blockKey === "processing") {
    return [
      { label: "Профиль обработки", value: item.processProfile.profileName },
      { label: "Включено", value: item.processProfile.readyLabels.length ? item.processProfile.readyLabels.join(", ") : "Пока ничего не подтверждено" },
    ];
  }
  return [
    { label: "Раздел", value: item.service.public_title || item.service.code },
    { label: "Тип обращения", value: item.offering?.public_title || item.offering?.full_code || "Не выбран" },
    { label: "Сценарий", value: template?.public_title || template?.template_code || "Не выбран" },
  ];
}

function ContextRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 font-mono text-slate-900">{tech(value)}</dd>
    </div>
  );
}
