import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioCondition, ScenarioDraftDefinition } from "./scenario-contract";
import { answerBranchChoices, answerBranchFields, connectAnswerBranch, defaultAnswerBranchField, findAnswerBranch } from "./scenario-answer-branches";

export function ScenarioAnswerBranches({ definition, block, disabled, sourceFieldKey, onSourceField, onChange, onAdd }: {
  definition: ScenarioDraftDefinition; block: ScenarioBlock; disabled: boolean;
  sourceFieldKey?: string; onSourceField?: (key: string) => void;
  onChange: (next: ScenarioDraftDefinition) => void; onAdd?: (when: ScenarioCondition) => void;
}) {
  const [localSource, setLocalSource] = useState("");
  const [error, setError] = useState("");
  const fields = answerBranchFields(definition, block.id);
  const field = defaultAnswerBranchField(definition, block.id, sourceFieldKey ?? localSource);
  if (!field) return null;
  const choices = answerBranchChoices(field);
  return <section className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50/30 p-3" aria-label="Ветвление по ответам">
    <h3 className="font-semibold">Ветвление по ответам</h3>
    <label className="block text-sm">Вопрос для ветвления<Select disabled={disabled} value={field.key} onChange={event => {
      setLocalSource(event.target.value); onSourceField?.(event.target.value); setError("");
    }}>{fields.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</Select></label>
    <p className="text-xs text-slate-600">Для каждого ответа добавьте новый шаг или выберите существующий. Ветви будут независимыми.</p>
    {error && <p role="alert">{error}</p>}
    {choices.map(choice => {
      const index = findAnswerBranch(block, choice.when);
      const edge = index >= 0 ? block.transitions?.[index] : undefined;
      const targets = (definition.blocks ?? []).filter(target => {
        try { connectAnswerBranch(definition, block.id, target.id, choice.when); return true; }
        catch { return false; }
      });
      return <fieldset key={choice.key} disabled={disabled} className="min-w-0 space-y-2 rounded border bg-white p-3" aria-label={`Ответ «${choice.label}»`}>
        <legend className="px-1 text-sm font-semibold">{choice.label}</legend>
        <label className="block text-sm">Следующий шаг<Select value={edge?.to ?? ""} onChange={event => {
          try { onChange(connectAnswerBranch(definition, block.id, event.target.value, choice.when)); setError(""); }
          catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось соединить ветвь"); }
        }}><option value="">Выберите существующий блок</option>{targets.map(target => <option key={target.id} value={target.id}>{target.title}</option>)}</Select></label>
        {!edge && onAdd && <Button variant="outline" onClick={() => onAdd(choice.when)}>Добавить шаг для «{choice.label}»</Button>}
        {edge && <p className="text-xs text-slate-500">Ветвь подключена. Продолжите её из следующего блока или через + на стрелке.</p>}
      </fieldset>;
    })}
    <p className="text-xs text-slate-500">Если ответа нет или он не подходит, используется отдельная ветвь «Иначе» ниже. Отсутствующий ответ не означает «Нет».</p>
  </section>;
}
