import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import type { ScenarioDraftDefinition, ScenarioField, ScenarioFieldType, ScenarioRole } from "./scenario-contract";
import { changeFieldType, compatibleRole, conditionFields, fieldLabels, fieldUses, isChoice, newKey, roleLabels } from "./scenario-builder-model";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import { ScenarioSeparatedInput } from "./scenario-separated-input";

type Props = { field: ScenarioField; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (field: ScenarioField) => void };
export function ScenarioFieldEditor({ field, definition, disabled, onChange }: Props) {
  const currentPage = definition.blocks?.find(block => block.kind === "form_page" && block.fields.some(item => item.key === field.key));
  const fields = conditionFields(definition, currentPage?.id ?? "", field.key);
  const roles = field.process_mapping?.roles ?? [];
  const uses = fieldUses(definition, field.key);
  function bound(key: keyof NonNullable<ScenarioField["validation"]>, text: string) {
    onChange({ ...field, validation: { ...field.validation, [key]: text === "" ? null : Number(text) } });
  }
  return <fieldset aria-label="Редактор вопроса" disabled={disabled} className="min-w-0 space-y-4 rounded-lg border p-4">
    <label className="block">Что спросить?<Input maxLength={300} value={field.label} onChange={event => onChange({ ...field, label: event.target.value })} /></label>
    <label className="block">Тип ответа<Select value={field.type} onChange={event => onChange(changeFieldType(field, event.target.value as ScenarioFieldType))}>
      {Object.entries(fieldLabels).map(([type, label]) => <option key={type} value={type}>{label}</option>)}
      <option disabled value="file">Вложение — защищённый backend пока недоступен</option>
    </Select></label>
    <div className="flex flex-wrap gap-4">
      <label><input type="checkbox" checked={!!field.required} onChange={event => onChange({ ...field, required: event.target.checked })} /> Обязательный ответ</label>
      <label><input type="checkbox" checked={!!field.allow_unknown} onChange={event => onChange({ ...field, allow_unknown: event.target.checked })} /> Разрешить «Не знаю»</label>
    </div>
    <label className="block">Подсказка<Input maxLength={2000} value={field.help_text ?? ""} onChange={event => onChange({ ...field, help_text: event.target.value })} /></label>
    {roles.some(role => role.startsWith("priority_")) && <p className="studio-next-help">Ответ используется действующей политикой Helpdesk.</p>}
    <label className="block">Пример ответа<Input maxLength={500} value={field.placeholder ?? ""} onChange={event => onChange({ ...field, placeholder: event.target.value })} /></label>
    {isChoice(field.type) && <fieldset className="space-y-3"><legend className="font-medium">Варианты ответа</legend>
      {(field.options ?? []).map((option, index) => <div key={index} className="space-y-2 rounded-md border p-3">
        <label className="block">Вариант {index + 1}<Input maxLength={300} value={option.label} onChange={event => onChange({ ...field, options: field.options!.map((old, i) => i === index ? { ...old, label: event.target.value } : old) })} /></label>
        <Button variant="ghost" disabled={disabled || field.options!.length <= 1} onClick={() => onChange({ ...field, options: field.options!.filter((_, i) => i !== index) })}>Удалить вариант {index + 1}</Button>
        <AdvancedDisclosure title="Расширенные настройки"><label className="block">Машинное значение<Input maxLength={100} value={option.value} onChange={event => onChange({ ...field, options: field.options!.map((old, i) => i === index ? { ...old, value: event.target.value } : old) })} /></label><p className="text-sm text-slate-500">Изменение значения может потребовать исправить условия переходов.</p></AdvancedDisclosure>
      </div>)}
      <Button variant="secondary" disabled={disabled || (field.options?.length ?? 0) >= 100} onClick={() => onChange({ ...field, options: [...(field.options ?? []), { value: newKey("option"), label: "Новый вариант" }] })}>Добавить вариант</Button>
    </fieldset>}
    <AdvancedDisclosure title="Расширенные настройки" description="Условия, проверка ответа и несколько назначений поля">
      <div className="space-y-4">
        <ScenarioConditionEditor label="Когда показывать вопрос" value={field.visible_when} fields={fields} disabled={disabled} onChange={value => onChange({ ...field, visible_when: value })} />
        <ScenarioConditionEditor label="Когда ответ обязателен" value={field.required_when} fields={fields} disabled={disabled} onChange={value => onChange({ ...field, required_when: value })} />
        <fieldset className="space-y-2"><legend className="font-medium">Проверка ответа</legend>
          {field.type === "number" ? <div className="grid gap-2 sm:grid-cols-2">
            <label>Минимальное число<Input type="number" value={field.validation?.min_value ?? ""} onChange={event => bound("min_value", event.target.value)} /></label>
            <label>Максимальное число<Input type="number" value={field.validation?.max_value ?? ""} onChange={event => bound("max_value", event.target.value)} /></label>
          </div> : !["checkbox", "multi_select"].includes(field.type) && <div className="grid gap-2 sm:grid-cols-2">
            <label>Минимум символов<Input type="number" min={0} max={10000} value={field.validation?.min_length ?? ""} onChange={event => bound("min_length", event.target.value)} /></label>
            <label>Максимум символов<Input type="number" min={1} max={10000} value={field.validation?.max_length ?? ""} onChange={event => bound("max_length", event.target.value)} /></label>
          </div>}
        </fieldset>
        <fieldset className="grid gap-2 sm:grid-cols-2"><legend className="font-medium">Назначения ответа</legend>
          {Object.entries(roleLabels).map(([role, title]) => <label key={role} className="text-sm"><input type="checkbox" disabled={disabled || !compatibleRole(field.type, role as ScenarioRole)} checked={roles.includes(role as ScenarioRole)} onChange={event => onChange({ ...field, process_mapping: { ...field.process_mapping, roles: event.target.checked ? [...roles, role as ScenarioRole] : roles.filter(item => item !== role) } })} /> {title}</label>)}
        </fieldset>
        <p className="text-sm text-slate-500">При смене типа несовместимые назначения снимаются. Приоритет и полномочия вычисляет сервер. Выбранные сущности должны быть проверены по серверному контексту.</p>
        <label className="block">Ключ факта<Input maxLength={100} pattern="[a-z0-9][a-z0-9_]*" value={field.process_mapping?.fact_key ?? ""} placeholder={field.key} onChange={event => onChange({ ...field, process_mapping: { ...field.process_mapping, fact_key: event.target.value || null } })} /></label>
        {field.group && <p className="break-all">Ключ раздела: {field.group}</p>}
        <ScenarioSeparatedInput label="Прежние ключи (через запятую)" values={field.aliases ?? []} separator="," disabled={disabled} limit={8} onChange={aliases => onChange({ ...field, aliases })} />
        <p className="break-all text-sm">Стабильный ключ: {field.key}</p>
        <div><p className="font-medium">Используется в условиях</p>{uses.length ? <ul>{uses.map((use, index) => <li key={index}>{use}</li>)}</ul> : <p className="text-sm">Зависимостей нет</p>}</div>
      </div>
    </AdvancedDisclosure>
  </fieldset>;
}
