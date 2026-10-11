import { useState } from "react";
import { Button } from "../../components/ui/button";
import { type ScenarioCatalog, type ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPurpose } from "./scenario-purpose";
import { ScenarioBlockBuilder } from "./scenario-block-builder";
import { ScenarioPublication } from "./scenario-publication";
import { ScenarioSimulationPanel } from "./scenario-simulation";
import { ScenarioVersionHistory } from "./scenario-version-history";
import { ScenarioProcessing } from "./scenario-processing";

export const scenarioSteps = ["Категория и назначение", "Пользовательский сценарий", "Обработка обращения", "Тестирование", "Публикация"];
type Props = { definition: ScenarioDraftDefinition; detail: ScenarioDetail | null; catalog: ScenarioCatalog; disabled: boolean; dirty: boolean; onChange: (value: ScenarioDraftDefinition) => void; onAccept?: (value: ScenarioDetail) => void; onCategoryDirty?: (dirty: boolean) => void; onCategoryCreated?: () => Promise<void>; onCategoryOpen?: (open: boolean) => void };
export function ScenarioWizard({ definition, detail, catalog, disabled, dirty, onChange, onAccept, onCategoryDirty, onCategoryCreated, onCategoryOpen }: Props) {
  const [step, setStep] = useState(0);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const offering = catalog.offerings.find(item => item.full_code === definition.offering_full_code);
  const purposeReady = !!detail && !!definition.title.trim() && !!offering && offering.service_code === definition.service_code;
  return <div className="min-w-0 space-y-5">
    <nav aria-label="Этапы настройки"><ol className="flex min-w-0 flex-wrap gap-2">{scenarioSteps.map((label, index) => <li key={label}><Button disabled={categoryOpen || (index > 0 && !purposeReady)} variant={step === index ? "secondary" : "ghost"} aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)}>{index + 1}. {label}</Button></li>)}</ol></nav>
    <section aria-label={scenarioSteps[step]} className="min-w-0 rounded-xl border bg-white p-5">
      {step === 0 && <ScenarioPurpose definition={definition} catalog={catalog} disabled={disabled} existing={!!detail} onChange={onChange} onCategoryDirty={onCategoryDirty} onCategoryOpen={open => { setCategoryOpen(open); onCategoryOpen?.(open); }} onCategoryCreated={onCategoryCreated} />}
      {step === 1 && <ScenarioBlockBuilder definition={definition} disabled={disabled} onChange={onChange} onSimulate={() => setStep(3)} />}
      {step === 2 && <ScenarioProcessing definition={definition} disabled={disabled} onChange={onChange} />}
      {step === 3 && (detail ? <ScenarioSimulationPanel key={detail.scenario.id} id={detail.scenario.id} revision={detail.draft.revision} dirty={dirty} disabled={disabled} definition={definition} /> : <p>Сначала сохраните сценарий.</p>)}
      {step === 4 && (detail ? <><ScenarioPublication key={detail.scenario.id} id={detail.scenario.id} revision={detail.draft.revision} dirty={dirty} disabled={disabled} definition={definition} offeringTitle={offering?.public_title} />{onAccept && <ScenarioVersionHistory id={detail.scenario.id} revision={detail.draft.revision} disabled={disabled || dirty} onAccept={onAccept} />}</> : <p>Сначала сохраните сценарий.</p>)}
    </section>
    {!purposeReady && <p className="text-sm text-slate-500">Выберите услугу и сохраните назначение сценария, прежде чем переходить к следующим этапам.</p>}
    <div className="flex flex-wrap justify-between gap-2"><Button variant="ghost" disabled={categoryOpen || step === 0} onClick={() => setStep(step - 1)}>Предыдущий этап</Button><Button disabled={categoryOpen || !purposeReady || step === scenarioSteps.length - 1} onClick={() => setStep(step + 1)}>Следующий этап</Button></div>
  </div>;
}
