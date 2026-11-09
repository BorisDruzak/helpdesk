import type { ReactNode } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { ScenarioPurpose } from "./scenario-purpose";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";

export type StartSection = "service" | "catalog" | "entries";
type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; section: StartSection; onSection: (section: StartSection) => void; onChange: (next: ScenarioDraftDefinition) => void; onEntry: (key: string, target: string) => void; onConnect: (target: string) => void; onProcessing: (kinds?: ScenarioPolicyKind[]) => void; catalogVisibility?: ReactNode; onAddEntrance?:()=>void };
export function ScenarioStartEditor({ section, onSection, onEntry, onConnect, onProcessing, onAddEntrance, catalogVisibility, ...props }: Props) {
  const { definition, disabled } = props;
  return <section aria-label="Подпункты начала" className="min-w-0 space-y-3">
    <ScenarioPurpose {...props} section={section} onSection={onSection} />
    <details open={section === "entries"} onToggle={event => { if (event.currentTarget.open && section !== "entries") onSection("entries"); }}>
      <summary className="cursor-pointer font-semibold">Входы в каталог</summary>
      <div className="space-y-3 pt-3">
        <p className="text-sm text-slate-500">Каждый вход открывает свой первый шаг. Условия дальнейшего пути задаются на связях карты.</p>
        {(definition.entry_points ?? []).map(entry => <Button key={entry.key} variant="outline" aria-label={`Настроить вход ${entry.title}`} onClick={() => onEntry(entry.key, entry.target_block_id)}>{entry.title}{entry.enabled === false ? " · отключён" : ""}</Button>)}
        {!definition.entry_points?.length && <p>Входы пока не созданы.</p>}
        {onAddEntrance && <Button disabled={disabled} onClick={onAddEntrance}>+ Вход из каталога</Button>}
        <details><summary>Подключение с клавиатуры</summary><label className="block">Добавить вход к шагу<Select disabled={disabled} value="" onChange={event => onConnect(event.target.value)}><option value="">Выберите блок на карте</option>{(definition.blocks ?? []).filter(block=>!isPolicyAttachment(block)).map(block => <option key={block.id} value={block.id}>{block.title}</option>)}</Select></label></details>
      </div>
    </details>
    {catalogVisibility && <section aria-label="Видимость услуги в каталоге" className="space-y-2 rounded border p-3"><h3 className="font-semibold">Видимость услуги в каталоге</h3>{catalogVisibility}</section>}
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" onClick={() => onProcessing(["visibility"])}>Видимость обращения</Button>
      <Button variant="outline" onClick={() => onProcessing(["priority", "ola", "approval", "notification", "closure"])}>Правила обработки</Button>
    </div>
    <p className="text-sm text-slate-500">Направления и сроки настраиваются в отдельных блоках «Маршрут обработки» и «Настройка SLA». Общие правила обработки и видимость обращения открываются на странице публикации.</p>
  </section>;
}
