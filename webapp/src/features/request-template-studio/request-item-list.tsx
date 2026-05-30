import { Badge } from "../../components/ui/badge";
import type { RequestStudioItem } from "./studio-model";
import { statusTone } from "./studio-model";

const GROUP_ORDER = ["Рабочее место", "Доступы", "Сеть", "Почта", "Другое", "Тестовые / выведенные"];

export function RequestItemList({
  items,
  selectedItemId,
  showTechnicalItems,
  onToggleTechnicalItems,
  onSelectItem,
}: {
  items: RequestStudioItem[];
  selectedItemId: string | null;
  showTechnicalItems: boolean;
  onToggleTechnicalItems: (value: boolean) => void;
  onSelectItem: (itemId: string) => void;
}) {
  const visibleItems = items.filter((item) => showTechnicalItems || !item.isTechnical);
  const groups = GROUP_ORDER.map((group) => ({
    group,
    items: visibleItems.filter((item) => (item.isTechnical ? "Тестовые / выведенные" : item.group) === group),
  })).filter((group) => group.items.length);

  return (
    <aside className="surface-panel h-fit p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">Типы обращений</h2>
          <p className="mt-1 text-xs text-slate-500">Рабочие опубликованные типы показываются первыми.</p>
        </div>
      </div>
      <label className="mt-3 flex items-center gap-2 text-xs font-semibold text-slate-600">
        <input
          checked={showTechnicalItems}
          className="h-4 w-4"
          onChange={(event) => onToggleTechnicalItems(event.currentTarget.checked)}
          type="checkbox"
        />
        Показать тестовые и выведенные
      </label>
      <div className="mt-4 space-y-4">
        {groups.map((group) => (
          <section key={group.group}>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{group.group}</h3>
            <div className="mt-2 space-y-2">
              {group.items.map((item) => (
                <button
                  className={`w-full rounded-md border p-3 text-left text-sm transition ${
                    item.id === selectedItemId ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-brand-200"
                  }`}
                  key={item.id}
                  onClick={() => onSelectItem(item.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-slate-950">{item.offering?.public_title || item.service.public_title || item.service.code}</span>
                    <Badge tone={statusTone(item.readinessStatus)}>{item.readinessStatus === "ok" ? "ok" : item.readinessStatus}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge tone={statusTone(item.offering?.lifecycle_status ?? item.service.lifecycle_status)}>
                      {item.offering?.lifecycle_status === "published" || item.service.lifecycle_status === "published" ? "опубликовано" : item.offering?.lifecycle_status ?? item.service.lifecycle_status}
                    </Badge>
                    <Badge tone={item.formPreview?.fields.length ? "success" : "warning"}>форма {item.formPreview?.fields.length ? "есть" : "нет"}</Badge>
                    <Badge tone={item.processBlocks.find((block) => block.key === "routing")?.status === "ready" ? "success" : "warning"}>маршрут</Badge>
                    <Badge tone={item.processBlocks.find((block) => block.key === "sla")?.status === "ready" ? "success" : "warning"}>SLA</Badge>
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </aside>
  );
}
