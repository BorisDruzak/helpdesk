import { Link } from "react-router-dom";
import type { OfferingCard, ScenarioCatalog, ScenarioItem } from "./scenario-api";

export function catalogEntries(data: ScenarioCatalog): OfferingCard[] {
  if (data.entries) return data.entries;
  // Compatibility with catalog responses before offering-card projection.
  const visible = new Set([...data.scenarios.map(item => item.offering_full_code), ...(data.legacy_offerings ?? []).map(item => item.full_code)]);
  return data.offerings.filter(item => visible.has(item.full_code)).map(offering => {
    const scenarios = data.scenarios.filter(item => item.offering_full_code === offering.full_code);
    return { offering: { ...offering, service_code: offering.service_code ?? scenarios[0]?.service_code }, scenarios, active_mode: "form", category_ids: scenarios.flatMap(item => item.category_id ? [item.category_id] : []) };
  });
}
export function scenarioEditingLabel(item: ScenarioItem): string {
  if (item.archived || item.status === "archived") return "Архив";
  if (item.issues?.length) return "Черновик: есть ошибки";
  return item.published_version_id ? "Версия опубликована; черновик доступен для редактирования" : "Черновик: не опубликован";
}
export function offeringLocation(data: ScenarioCatalog, card: OfferingCard): string {
  const titles: string[] = [];
  let id = card.category_ids[0];
  const seen = new Set<string>();
  while (id && !seen.has(id)) {
    seen.add(id);
    const node = data.categories.find(item => item.id === id && item.service_code === card.offering.service_code);
    if (!node) break;
    titles.unshift(node.title); id = node.parent_id ?? "";
  }
  titles.unshift(data.services.find(item => item.code === card.offering.service_code)?.public_title ?? "Раздел недоступен");
  return titles.join(" → ");
}
export function OfferingCardSummary({ card, data }: { card: OfferingCard; data: ScenarioCatalog }) {
  const editing = card.scenarios.find(item => !item.archived && item.status !== "archived");
  return <>
    <p className="mt-2 text-sm font-medium">{card.requester_available === false ? "Недоступна сотрудникам: проверьте публикацию, видимость и форму услуги" : card.active_mode === "scenario" ? "Для сотрудника: пошаговый сценарий" : "Для сотрудника: обычная форма"}</p>
    <p className="mt-1 break-words text-sm text-slate-500">{offeringLocation(data, card)}</p>
    {editing && <p className="mt-2 text-sm text-amber-800">{scenarioEditingLabel(editing)}</p>}
    {editing?.description && <p className="mt-2 break-words text-sm">{editing.description}</p>}
    {editing?.published_version && <p className="mt-1 text-sm">Версия {editing.published_version}</p>}
    {editing?.updated_at && Number.isFinite(Date.parse(editing.updated_at)) && <p className="mt-1 text-sm text-slate-500">Изменён: <time dateTime={editing.updated_at}>{new Date(editing.updated_at).toLocaleString("ru-RU")}</time></p>}
  </>;
}
export function OfferingCardLink({ card, data }: { card: OfferingCard; data: ScenarioCatalog }) {
  return <li className="min-w-0 rounded-xl border bg-white p-4" data-offering-code={card.offering.full_code}>
    <Link className="break-words text-base font-semibold text-brand-800 underline-offset-4 hover:underline" to={`/app/admin/request-template-studio/services/${encodeURIComponent(card.offering.full_code)}`}>{card.offering.public_title}</Link>
    <OfferingCardSummary card={card} data={data} />
  </li>;
}
