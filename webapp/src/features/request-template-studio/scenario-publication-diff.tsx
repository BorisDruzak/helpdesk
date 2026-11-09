import type { ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

function changeLabel(path: string, definition?: ScenarioDraftDefinition): string {
  const parts = path.split(".");
  if (parts[0] === "blocks") {
    if (parts[1] === "order") return "Порядок шагов";
    const block = definition?.blocks?.find(item => item.id === parts[1]);
    const field = block?.kind === "form_page" ? block.fields.find(item => item.key === parts[3]) : undefined;
    return field ? `Вопрос «${field.label}»` : block ? `Шаг «${block.title}»` : "Состав шагов и вопросов";
  }
  if (parts[0] === "entry_points") {
    const entry = definition?.entry_points?.find(item => item.key === parts[1]);
    return entry ? `Пункт каталога «${entry.title}»` : "Состав пунктов каталога";
  }
  return ({ processing: "Направления и сроки обработки карты", editor_layout: "Расположение блоков", process_binding: "Правила обработки", category_id: "Категория услуги",
    service_code: "Раздел каталога", entry_block_id: "Вход в маршрут", publish_offering: "Публикация услуги", offering: "Доступность услуги" } as Record<string, string>)[parts[0]] ?? "Настройки услуги";
}
export function ScenarioPublicationDiff({ diff, definition }: { diff: ScenarioPublicationPreview["diff"]; definition?: ScenarioDraftDefinition }) {
  return <section className="scenario-publication-section" aria-label="Изменения версии"><h2>Изменения относительно опубликованной версии</h2>
    {diff.length ? <>
      {diff.filter(change => ["title", "description"].includes(change.path)).map(change => <div key={change.path} className="rounded border p-3"><h3>{change.path === "title" ? "Название услуги" : "Описание"}</h3><p className="text-sm text-slate-500">Было</p><p>{String(change.before ?? "Не задано")}</p><p className="mt-2 text-sm text-slate-500">Будет</p><p>{String(change.after ?? "Не задано")}</p></div>)}
      <ul className="list-disc pl-5">{[...new Set(diff.filter(change => !["title", "description", "scenario_key", "offering_full_code", "schema_version", "process_binding.request_template_key"].includes(change.path)).map(change => changeLabel(change.path, definition)))].map(label => <li key={label}>{label}</li>)}</ul>
      <p className="text-sm text-slate-500">Проверьте вопросы, пункты каталога и пути на карте. Декларацию целиком можно получить через экспорт JSON / YAML.</p>
    </> : <p>Содержимое сценария не изменилось. Будет создана новая версия с проверенной обработкой.</p>}
  </section>;
}
