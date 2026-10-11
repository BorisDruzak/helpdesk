import { useState } from "react";
import { Button } from "../../components/ui/button";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { type ScenarioCatalog, type ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioPurpose } from "./scenario-purpose";
import { ScenarioBlockBuilder } from "./scenario-block-builder";
import { ScenarioPublication } from "./scenario-publication";
import { ScenarioSimulationPanel } from "./scenario-simulation";
import { ScenarioVersionHistory } from "./scenario-version-history";

export const scenarioSteps = ["Категория и назначение", "Пользовательский сценарий", "Обработка обращения", "Тестирование", "Публикация"];
type Props = { definition: ScenarioDraftDefinition; detail: ScenarioDetail | null; catalog: ScenarioCatalog; disabled: boolean; dirty: boolean; onChange: (value: ScenarioDraftDefinition) => void; onAccept?: (value: ScenarioDetail) => void };
export function ScenarioWizard({ definition, detail, catalog, disabled, dirty, onChange, onAccept }: Props) {
  const [step, setStep] = useState(0);
  const offering = catalog.offerings.find(item => item.full_code === definition.offering_full_code);
  const purposeReady = !!detail && !!definition.title.trim() && !!offering && offering.service_code === definition.service_code;
  return <div className="min-w-0 space-y-5">
    <nav aria-label="Этапы настройки"><ol className="flex min-w-0 flex-wrap gap-2">{scenarioSteps.map((label, index) => <li key={label}><Button disabled={index > 0 && !purposeReady} variant={step === index ? "secondary" : "ghost"} aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)}>{index + 1}. {label}</Button></li>)}</ol></nav>
    <section aria-label={scenarioSteps[step]} className="min-w-0 rounded-xl border bg-white p-5">
      {step === 0 && <ScenarioPurpose definition={definition} catalog={catalog} disabled={disabled} existing={!!detail} onChange={onChange} />}
      {step === 1 && <ScenarioBlockBuilder definition={definition} disabled={disabled} onChange={onChange} />}
      {step === 2 && <div className="space-y-4"><h2 className="text-lg font-semibold">Обработка обращения</h2><p>Приоритет, маршрут, сроки и согласования определяет сервер через политики выбранной услуги и шаблона.</p><dl className="space-y-2"><div><dt className="font-medium">Услуга</dt><dd>{offering?.public_title ?? "Не выбрана"}</dd></div><div><dt className="font-medium">Маршрутизация</dt><dd>{offering?.routing_policy_code ? "Назначена политикой услуги" : "Наследуется от шаблона"}</dd></div><div><dt className="font-medium">Сроки обслуживания</dt><dd>{offering?.sla_policy_code ? "Назначены политикой услуги" : "Наследуются от шаблона"}</dd></div></dl><AdvancedDisclosure title="Расширенные настройки"><p className="break-all">Шаблон: {definition.process_binding.request_template_key || "не выбран"}</p><p>Источник приоритета: существующий серверный runtime политик.</p></AdvancedDisclosure></div>}
      {step === 3 && (detail ? <ScenarioSimulationPanel key={detail.scenario.id} id={detail.scenario.id} revision={detail.draft.revision} dirty={dirty} disabled={disabled} /> : <p>Сначала сохраните сценарий.</p>)}
      {step === 4 && (detail ? <><ScenarioPublication key={detail.scenario.id} id={detail.scenario.id} revision={detail.draft.revision} dirty={dirty} disabled={disabled} />{onAccept && <ScenarioVersionHistory id={detail.scenario.id} revision={detail.draft.revision} disabled={disabled || dirty} onAccept={onAccept} />}</> : <p>Сначала сохраните сценарий.</p>)}
    </section>
    {!purposeReady && <p className="text-sm text-slate-500">Выберите услугу и сохраните назначение сценария, прежде чем переходить к следующим этапам.</p>}
    <div className="flex flex-wrap justify-between gap-2"><Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Предыдущий этап</Button><Button disabled={!purposeReady || step === scenarioSteps.length - 1} onClick={() => setStep(step + 1)}>Следующий этап</Button></div>
  </div>;
}
