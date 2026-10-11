import type { ScenarioBlock } from "./scenario-contract";
import { fieldLabels } from "./scenario-builder-model";

export function ScenarioBlockPreview({ block }: { block: ScenarioBlock }) {
  return <div className="min-w-0 space-y-4 break-words rounded-xl border bg-slate-50 p-4">
    <h3 className="font-semibold">{block.title}</h3>
    <p className="text-xs text-slate-500">Вид выбранного шага. Условия и переходы проверяйте на этапе «Тестирование» через сервер.</p>
    {block.kind === "form_page" && block.fields.map(field => <div key={field.key} className="space-y-1">
      {block.layout === "section" && field.group && <p className="text-sm font-medium">{field.group}</p>}
      <p className="font-medium">{field.label}{field.required ? " *" : ""}</p>
      <div className="rounded border bg-white p-2 text-sm text-slate-500">{field.placeholder || fieldLabels[field.type]}</div>
      {!!field.options?.length && <p className="text-sm">{field.options.map(option => option.label).join(" / ")}</p>}
      {!!field.help_text && <p className="text-sm">{field.help_text}</p>}
      {field.visible_when && <p className="text-xs">Вопрос показывается по условию</p>}
    </div>)}
    {block.kind === "instruction" && <p className="whitespace-pre-wrap">{block.content.body}</p>}
    {block.kind === "resolution_check" && <p>Проблема решена? Да / Нет / Не знаю</p>}
    {block.kind === "diagnostic" && <p>Диагностика недоступна. Можно продолжить без неё.</p>}
    {block.kind === "review" && <p>Проверьте ответы перед продолжением.</p>}
    {block.kind === "submit_ticket" && <p>Отправить обращение</p>}
    {block.kind === "finish" && <p>{block.message}</p>}
    {block.kind === "decision" && <p>Автоматический выбор следующего шага сервером</p>}
  </div>;
}
