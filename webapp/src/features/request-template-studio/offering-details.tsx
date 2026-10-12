import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { EmptyState } from "../../components/ui-page/page-components";
import { OfferingCardSummary, catalogEntries, scenarioEditingLabel } from "./offering-card";
import type { ScenarioCatalog, ScenarioItem } from "./scenario-api";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import { OfferingPublication } from "./offering-publication";

export function OfferingDetails({ data, code, canEdit, onOpen, onCreate }: { data: ScenarioCatalog; code: string; canEdit: boolean;
  onOpen: (item: ScenarioItem) => void; onCreate: (offering: AdminServiceCatalogOffering) => void }) {
  const card = catalogEntries(data).find(item => item.offering.full_code === code);
  if (!card) return <EmptyState title="Услуга не найдена" description="Вернитесь в каталог и выберите доступную услугу." />;
  const current = card.scenarios.filter(item => !item.archived && item.status !== "archived");
  const archive = card.scenarios.filter(item => item.archived || item.status === "archived");
  return <section className="min-w-0 space-y-5" aria-label="Страница услуги">
    {canEdit && card.offering.lifecycle_status === "draft" && <OfferingPublication code={code} />}
    <div className="flex flex-wrap gap-3">
      {card.requester_available && <Link className="inline-flex min-h-11 items-center rounded-pill border px-4 text-sm font-semibold" target="_blank" to={`/app/requester/new?${new URLSearchParams({ offering: code })}`}>Открыть в кабинете сотрудника</Link>}
      {card.offering.request_template_key && <Link className="inline-flex min-h-11 items-center rounded-pill border px-4 text-sm font-semibold" to={`/app/admin/forms?template=${encodeURIComponent(card.offering.request_template_key)}`}>Открыть обычную форму</Link>}
      {canEdit && !current.length && card.offering.request_template_key && <Button onClick={() => onCreate(card.offering)}>Создать сценарий для услуги</Button>}
      <Link className="inline-flex min-h-11 items-center px-3 text-sm underline" to={`/app/admin/service-catalog/offerings/${encodeURIComponent(code)}`}>Настройки услуги</Link>
    </div>
    <div className="rounded-xl border bg-white p-5"><OfferingCardSummary card={card} data={data} />
      {card.offering.short_description && <p className="mt-3 break-words text-sm">{card.offering.short_description}</p>}
      <p className="mt-3 text-sm text-slate-500">Черновик и архив не заменяют действующую форму. Сценарий становится доступен после публикации и включения.</p>
    </div>
    <section aria-label="Сценарии услуги" className="space-y-3">
      <h2 className="text-lg font-semibold">Настройка сценария</h2>
      {!current.length && <p className="text-sm text-slate-500">{card.requester_available === false ? "Услуга пока недоступна сотрудникам. Проверьте форму и публикацию в настройках услуги." : "Сценарий не настроен. Сотрудники используют обычную форму."}</p>}
      {current.map(item => <div key={item.id} className="rounded-xl border p-4"><Button className="h-auto max-w-full whitespace-normal text-left" variant="secondary" onClick={() => onOpen(item)}>{item.title}</Button><p className="mt-2 text-sm">{scenarioEditingLabel(item)}</p></div>)}
    </section>
    {!!archive.length && <details className="rounded-xl border p-4"><summary className="cursor-pointer font-semibold">Архив сценариев · {archive.length}</summary><ul className="mt-3 space-y-2">{archive.map(item => <li key={item.id}><Button className="h-auto max-w-full whitespace-normal text-left" variant="ghost" onClick={() => onOpen(item)}>{item.title}</Button><p className="text-sm text-slate-500">Архив · {item.published_version ? `версия ${item.published_version}` : "без публикации"}</p></li>)}</ul></details>}
  </section>;
}
