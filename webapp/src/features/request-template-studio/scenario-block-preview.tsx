import type { ScenarioBlock } from "./scenario-contract";
import { RequestFormFieldControl } from "../requester/dynamic-form";
import { ScenarioFields } from "../requester/scenario-fields";
import { Button } from "../../components/ui/button";

export function ScenarioBlockPreview({ block }: { block: ScenarioBlock }) {
  return <div className="min-w-0 space-y-4 break-words rounded-xl border bg-slate-50 p-4">
    <h3 className="font-semibold">{block.title}</h3>
    <p className="text-xs text-slate-500">Вид выбранного шага. Условия и переходы проверяйте на этапе «Тестирование» через сервер.</p>
    {block.kind === "form_page" && <fieldset disabled className="grid min-w-0 gap-4"><ScenarioFields layout={block.layout} fields={block.fields.map(field => ({ ...field, visible_when: undefined }))} renderField={field => <>
      <RequestFormFieldControl field={field} value={undefined} onChange={() => {}} />
      {field.allow_unknown && <label className="flex gap-2"><input type="checkbox" />Не знаю</label>}
      {block.fields.find(item => item.key === field.key)?.visible_when && <p className="text-xs">Вопрос показывается по серверному условию в тестовом прогоне.</p>}
    </>} /></fieldset>}
    {block.kind === "instruction" && <><p className="whitespace-pre-wrap">{block.content.body}</p><label className="flex gap-2"><input type="checkbox" disabled />Инструкция выполнена</label></>}
    {block.kind === "resolution_check" && <div className="flex flex-wrap gap-2">{["Да, решено", "Нет, нужна помощь", "Не знаю"].map(label => <Button key={label} disabled>{label}</Button>)}</div>}
    {block.kind === "diagnostic" && <p>Диагностика недоступна. Можно продолжить без неё.</p>}
    {block.kind === "review" && <p>Проверьте ответы перед продолжением.</p>}
    {block.kind === "submit_ticket" && <Button disabled>Проверить обработку</Button>}
    {block.kind === "finish" && <p>{block.message}</p>}
    {block.kind === "decision" && <p>Автоматический выбор следующего шага сервером</p>}
  </div>;
}
