import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioCondition, ScenarioField, ScenarioScalar } from "./scenario-contract";
import { ScenarioSeparatedInput } from "./scenario-separated-input";

type Props = {
  label: string; value: ScenarioCondition | null | undefined; fields: ScenarioField[];
  resultValues?: string[]; disabled: boolean; onChange: (value: ScenarioCondition | null) => void; depth?: number;
};
const operators = { eq: "Равно", neq: "Не равно", gt: "Больше", gte: "Не меньше", lt: "Меньше", lte: "Не больше", in: "Один из", exists: "Ответ задан", and: "Все условия", or: "Любое условие", not: "Не выполняется" };
export function ScenarioConditionEditor({ label, value, fields, resultValues = [], disabled, onChange, depth = 0 }: Props) {
  const seed = (): ScenarioCondition => fields.length
    ? { op: "exists", source: "answer", field: fields[0].key }
    : { op: "eq", source: "current_result", value: resultValues[0] ?? "yes" };
  const leaf = value && "source" in value ? value : seed();
  const field = "field" in leaf ? fields.find(item => item.key === leaf.field) : undefined;
  const choices: { value: ScenarioScalar; label: string }[] = field?.options?.length ? field.options
    : field?.type === "checkbox" ? [{ value: true, label: "Да" }, { value: false, label: "Нет" }]
    : "source" in leaf && leaf.source === "current_result" ? resultValues.map(result => ({ value: result, label: ({ yes: "Да", no: "Нет", unknown: "Не знаю", acknowledged: "Прочитано", unavailable: "Недоступно" } as Record<string, string>)[result] })) : [];
  function scalar(text: string): ScenarioScalar {
    if (field?.type === "checkbox") return text === "true";
    if (field?.type !== "number") return text;
    if (!text.trim()) return null;
    const number = Number(text);
    // Keep invalid input explicit; JSON must never silently turn Infinity/NaN into null.
    return Number.isFinite(number) && Math.abs(number) <= Number.MAX_SAFE_INTEGER ? number : text;
  }
  function operatorAllowed(op: string) {
    if (["and", "or", "not", "in", "exists"].includes(op)) return true;
    if (["gt", "gte", "lt", "lte"].includes(op)) return field?.type === "number";
    return field?.type !== "multi_select";
  }
  function operator(op: ScenarioCondition["op"]) {
    if (op === "and" || op === "or") onChange({ op, conditions: [value ?? seed()] });
    else if (op === "not") onChange({ op, condition: value ?? seed() });
    else {
      const source = "source" in leaf && leaf.source === "answer" ? { source: "answer" as const, field: leaf.field } : { source: "current_result" as const };
      const value = field?.type === "number" ? 0 : field?.type === "checkbox" ? true : field?.options?.[0]?.value ?? resultValues[0] ?? "";
      if (op === "exists") onChange({ ...source, op });
      else if (op === "in") onChange({ ...source, op, value: [value] });
      else onChange({ ...source, op, value });
    }
  }
  return <fieldset className="min-w-0 space-y-2 rounded-md border p-3" disabled={disabled}>
    <legend className="px-1 font-medium">{label}</legend>
    {!value ? <Button disabled={disabled || (!fields.length && !resultValues.length)} variant="ghost" onClick={() => onChange(seed())}>Добавить условие</Button> : <>
      <div className="flex flex-wrap gap-2">
        <label className="min-w-0 flex-1">Правило<Select value={value.op} onChange={event => operator(event.target.value as ScenarioCondition["op"])}>{Object.entries(operators).map(([op, title]) => <option key={op} value={op} disabled={!operatorAllowed(op)}>{title}</option>)}</Select></label>
        <Button variant="ghost" onClick={() => onChange(null)}>Убрать условие</Button>
      </div>
      {depth >= 8 ? <p role="alert">Глубокое условие сохранено. Упростите его перед редактированием.</p> : value.op === "and" || value.op === "or" ? <>
        {value.conditions.map((item, index) => <ScenarioConditionEditor key={index} label={`Условие ${index + 1}`} value={item} fields={fields} resultValues={resultValues} disabled={disabled} depth={depth + 1} onChange={next => {
          const conditions = value.conditions.flatMap((old, i) => i === index ? next ? [next] : [] : [old]);
          onChange(conditions.length ? { ...value, conditions } : null);
        }} />)}
        <Button variant="ghost" disabled={value.conditions.length >= 20} onClick={() => onChange({ ...value, conditions: [...value.conditions, seed()] })}>Ещё условие</Button>
      </> : value.op === "not" ? <ScenarioConditionEditor label="Исключение" value={value.condition} fields={fields} resultValues={resultValues} disabled={disabled} depth={depth + 1} onChange={next => onChange(next ? { ...value, condition: next } : null)} /> : "source" in value && <>
        <label className="block">Источник<Select value={value.source === "answer" ? value.field : "__result"} onChange={event => {
          const source = event.target.value === "__result" ? { source: "current_result" as const } : { source: "answer" as const, field: event.target.value };
          // Changing a source retains only the operator, never an incompatible typed value.
          onChange({ ...source, op: "exists" });
        }}>
          {value.source === "answer" && !field && <option value={value.field}>Ответ больше не найден</option>}
          {fields.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}
          {(resultValues.length > 0 || value.source === "current_result") && <option disabled={!resultValues.length} value="__result">Результат текущего блока</option>}
        </Select></label>
        {value.op !== "exists" && <div className="space-y-2">{value.op === "in" ? "Значения (каждое с новой строки)" : "Значение"}
          {value.op === "in" ? choices.length ? <fieldset className="space-y-2"><legend>Допустимые значения</legend>
              {choices.map(choice => <label key={String(choice.value)} className="block"><input type="checkbox" checked={value.value.includes(choice.value)} onChange={event => onChange({ ...value, value: event.target.checked ? [...value.value, choice.value] : value.value.filter(item => item !== choice.value) })} /> {choice.label}</label>)}
              {value.value.filter(item => !choices.some(choice => choice.value === item)).map((item, index) => <div key={index}><p role="alert">Сохранённое значение больше не допустимо: {String(item)}</p><Button variant="ghost" onClick={() => onChange({ ...value, value: value.value.filter(old => old !== item) })}>Удалить недопустимое значение</Button></div>)}
            </fieldset> : <ScenarioSeparatedInput label="Список значений" values={value.value.map(String)} separator={"\n"} disabled={disabled} limit={100} onChange={items => onChange({ ...value, value: items.map(scalar) })} />
            : field?.options?.length || field?.type === "checkbox" || value.source === "current_result" ? <Select aria-label="Значение условия" value={String(value.value ?? "")} onChange={event => onChange({ ...value, value: scalar(event.target.value) })}>
                <option value="">Выберите значение</option>
                {choices.map(item => <option key={String(item.value)} value={String(item.value)}>{item.label}</option>)}
              </Select>
            : <Input aria-label="Значение условия" type={field?.type === "number" ? "number" : "text"} value={String(value.value ?? "")} onChange={event => onChange({ ...value, value: scalar(event.target.value) })} />}
        </div>}
        {(!operatorAllowed(value.op) || value.source === "current_result" && (!resultValues.length || value.op !== "exists" && (value.op === "in" ? value.value : [value.value]).some(item => !resultValues.includes(String(item))))) && <p role="alert">Условие сохранено, но несовместимо с этим источником. Исправьте правило или значение.</p>}
        {value.source === "answer" && !field && <p role="alert">Ответ недоступен на этом шаге. Выберите вопрос текущей или предыдущей страницы.</p>}
        {field?.type === "number" && value.op !== "exists" && (value.op === "in" ? value.value : [value.value]).some(item => item !== null && (typeof item !== "number" || !Number.isFinite(item) || Math.abs(item) > Number.MAX_SAFE_INTEGER)) && <p role="alert">Введите конечные числа в допустимом диапазоне, по одному на строку.</p>}
      </>}
    </>}
  </fieldset>;
}
