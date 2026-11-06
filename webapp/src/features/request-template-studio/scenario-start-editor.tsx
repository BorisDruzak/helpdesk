import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { ScenarioPurpose } from "./scenario-purpose";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

export type StartSection = "service" | "catalog" | "entries";
type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; disabled: boolean; existing: boolean; section: StartSection; onSection: (section: StartSection) => void; onChange: (next: ScenarioDraftDefinition) => void; onEntry: (key: string, target: string) => void; onConnect: (target: string) => void; onProcessing: () => void };
export function ScenarioStartEditor({ section, onSection, onEntry, onConnect, onProcessing, ...props }: Props) {
  const { definition, disabled } = props;
  return <section aria-label="Подпункты начала" className="min-w-0 space-y-3">
    <ScenarioPurpose {...props} section={section} onSection={onSection} />
    <details open={section === "entries"} onToggle={event => { if (event.currentTarget.open && section !== "entries") onSection("entries"); }}>
      <summary className="cursor-pointer font-semibold">Входы в каталог</summary>
      <div className="space-y-3 pt-3">
        <p className="text-sm text-slate-500">Каждый вход открывает свой первый шаг. Условия дальнейшего пути задаются на связях карты.</p>
        {(definition.entry_points ?? []).map(entry => <Button key={entry.key} variant="outline" aria-label={`Настроить вход ${entry.title}`} onClick={() => onEntry(entry.key, entry.target_block_id)}>{entry.title}{entry.enabled === false ? " · отключён" : ""}</Button>)}
        {!definition.entry_points?.length && <p>Входы пока не созданы.</p>}
        <label className="block">Добавить вход к шагу<Select disabled={disabled} value="" onChange={event => onConnect(event.target.value)}><option value="">Выберите блок на карте</option>{(definition.blocks ?? []).map(block => <option key={block.id} value={block.id}>{block.title}</option>)}</Select></label>
      </div>
    </details>
    <Button variant="outline" onClick={onProcessing}>Обработка и SLA</Button>
  </section>;
}
