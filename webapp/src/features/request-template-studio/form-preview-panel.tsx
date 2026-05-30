import { Badge } from "../../components/ui/badge";
import type { RequestStudioItem, RequestStudioMode } from "./studio-model";

export function FormPreviewPanel({
  item,
  mode,
}: {
  item: RequestStudioItem;
  mode: RequestStudioMode;
}) {
  const form = item.formPreview;
  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Preview</h2>
          <p className="mt-1 text-sm text-slate-600">Как обращение увидит пользователь и исполнитель.</p>
        </div>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Как увидит пользователь</h3>
          <p className="mt-1 text-sm text-slate-600">{item.offering?.public_title || item.template?.public_title || "Тип обращения не выбран"}</p>
          {form ? (
            <div className="mt-4 space-y-2">
              {form.fields.slice(0, 8).map((field) => (
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3" key={field.key}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">{field.label}</span>
                    <Badge tone="neutral">{field.type}</Badge>
                    {field.required ? <Badge tone="warning">обязательное</Badge> : <Badge tone="neutral">необязательное</Badge>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Форма не найдена.</p>
          )}
        </article>
        <article className="rounded-md border border-slate-200 bg-white p-4">
          <h3 className="font-semibold text-slate-950">Как увидит исполнитель</h3>
          <dl className="mt-4 space-y-2 text-sm">
            <PreviewRow label="Заголовок тикета" value={item.offering?.public_title || item.template?.public_title} />
            <PreviewRow label="Очередь" value={mode === "basic" ? humanRouting(item.template?.routing_policy_code || item.offering?.routing_policy_code) : item.template?.routing_policy_code || item.offering?.routing_policy_code || "Будет определена маршрутом"} />
            <PreviewRow label="Приоритет" value={mode === "basic" ? "По правилам приоритета" : item.template?.priority_policy_code || "По политике приоритета"} />
            <PreviewRow label="SLA" value={mode === "basic" ? humanSla(item.template?.sla_policy_code || item.offering?.sla_policy_code) : item.template?.sla_policy_code || item.offering?.sla_policy_code || "Не выбрано"} />
            <PreviewRow label="Checklist закрытия" value={mode === "basic" ? humanClosure(item.template?.closure_policy_code) : item.template?.closure_policy_code || "Не настроено"} />
            <PreviewRow label="Согласование" value={item.template?.approval_policy_code || item.offering?.approval_policy_code || "Не требуется"} />
          </dl>
          {mode !== "basic" && form ? (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold text-slate-500">Process mapping</p>
              <p className="mt-1 text-sm text-slate-700">
                Полей с mapping: {form.fields.filter((field) => field.processMapping && Object.keys(field.processMapping).length > 0).length}
              </p>
            </div>
          ) : null}
        </article>
      </div>
    </section>
  );
}

function PreviewRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-semibold text-slate-900">{value || "не задано"}</dd>
    </div>
  );
}

function humanRouting(value?: string | null) {
  if (!value) {
    return "Будет определена маршрутом";
  }
  if (value.toLowerCase().includes("l1")) {
    return "Service Desk L1";
  }
  return "Выбранная очередь";
}

function humanSla(value?: string | null) {
  if (!value) {
    return "Не выбрано";
  }
  return "По выбранной политике сроков";
}

function humanClosure(value?: string | null) {
  if (!value) {
    return "Не настроено";
  }
  return "Результат и сообщение пользователю";
}
