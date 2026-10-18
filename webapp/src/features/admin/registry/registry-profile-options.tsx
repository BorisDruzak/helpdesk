import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { normalizeProfileOption } from "../../requester/profile-runtime";

type Option = string | { value: string; label: string };

export function ProfileSelectOptions({ options, onChange }: { options: Option[]; onChange: (options: Option[]) => void }) {
  const normalized = options.map(normalizeProfileOption);
  function patch(index: number, changes: Partial<{ label: string; value: string }>) {
    onChange(normalized.map((option, i) => i === index ? { ...option, ...changes } : option));
  }
  return (
    <fieldset className="mt-3 space-y-2 border-t border-border pt-3">
      <legend className="text-sm font-semibold">Варианты списка</legend>
      <p className="text-xs text-slate-500">Значение сохраняется в профиле. Если оно используется в профилях, сервер запретит его удаление или замену. Название можно менять.</p>
      {normalized.map((option, index) => (
        <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]" key={index}>
          <label className="text-xs">Название для сотрудника
            <Input aria-label={`Название варианта ${index + 1}`} value={option.label} onChange={(event) => patch(index, { label: event.target.value })} />
          </label>
          <label className="text-xs">Машинное значение
            <Input aria-label={`Значение варианта ${index + 1}`} value={option.value} onChange={(event) => patch(index, { value: event.target.value })} />
          </label>
          <Button className="self-end" variant="outline" type="button" aria-label={`Удалить вариант ${index + 1}`} onClick={() => onChange(normalized.filter((_, i) => i !== index))}>Удалить</Button>
        </div>
      ))}
      <Button variant="outline" type="button" onClick={() => onChange([...normalized, { value: "", label: "" }])}>Добавить вариант</Button>
    </fieldset>
  );
}
