import { Trash2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { AdminFormsFieldType } from "../forms-builder/api";
import { PUBLISHABLE_DYNAMIC_REQUEST_FIELD_TYPES } from "../requester/dynamic-form";
import { PROCESS_MEANINGS, newDraftField, type StudioDraft, type StudioDraftField } from "./draft-model";

const FIELD_TYPE_LABELS: Partial<Record<AdminFormsFieldType, string>> = {
  text: "Короткий текст",
  textarea: "Длинный текст",
  email: "Email",
  phone: "Телефон",
  url: "Ссылка",
  select: "Список",
  radio: "Один вариант",
  multi_select: "Несколько вариантов",
  checkbox: "Да/нет",
  date: "Дата",
  datetime: "Дата и время",
  department_picker: "Подразделение",
  location_picker: "Локация",
  device_picker: "Устройство",
  service_picker: "Услуга",
  user_picker: "Пользователь",
};

const FIELD_TYPES: Array<{ value: AdminFormsFieldType; label: string }> = PUBLISHABLE_DYNAMIC_REQUEST_FIELD_TYPES.map((value) => ({
  value: value as AdminFormsFieldType,
  label: FIELD_TYPE_LABELS[value as AdminFormsFieldType] ?? value,
}));

export function FormFieldEditor({
  draft,
  selectedIndex,
  onSelectIndex,
  onChange,
}: {
  draft: StudioDraft;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
  onChange: (draft: StudioDraft) => void;
}) {
  const safeIndex = Math.min(Math.max(selectedIndex, 0), Math.max(draft.fields.length - 1, 0));
  const selectedField = draft.fields[safeIndex] ?? null;

  function updateField(patch: Partial<StudioDraftField>) {
    if (!selectedField) {
      return;
    }
    onChange({
      ...draft,
      fields: draft.fields.map((field, index) => (index === safeIndex ? { ...field, ...patch } : field)),
    });
  }

  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Форма пользователя</h2>
          <p className="mt-1 text-sm text-slate-600">Базовые поля редактируются здесь. Raw JSON и process mapping скрыты в базовом режиме.</p>
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            const next = { ...draft, fields: [...draft.fields, newDraftField(draft.fields.length)] };
            onChange(next);
            onSelectIndex(next.fields.length - 1);
          }}
        >
          Добавить поле
        </Button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div className="space-y-2">
          {draft.fields.map((field, index) => (
            <button
              className={`w-full rounded-md border px-3 py-2 text-left text-sm ${index === safeIndex ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-white"}`}
              key={`${field.key}:${index}`}
              onClick={() => onSelectIndex(index)}
              type="button"
            >
              <span className="block font-semibold text-slate-950">{field.label}</span>
              <span className="mt-1 block text-xs text-slate-500">{field.required ? "обязательное" : "необязательное"} · {field.type}</span>
            </button>
          ))}
        </div>

        {selectedField ? (
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-800">
                Название поля
                <input className="field-base mt-1 px-3 py-2" value={selectedField.label} onChange={(event) => updateField({ label: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                Ключ поля
                <input className="field-base mt-1 px-3 py-2" value={selectedField.key} onChange={(event) => updateField({ key: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                Тип поля
                <select className="field-base mt-1 px-3 py-2" value={selectedField.type} onChange={(event) => updateField({ type: event.currentTarget.value as AdminFormsFieldType })}>
                  {FIELD_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 pt-7 text-sm font-semibold text-slate-800">
                <input checked={selectedField.required} onChange={(event) => updateField({ required: event.currentTarget.checked })} type="checkbox" />
                Обязательное поле
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                Placeholder
                <input className="field-base mt-1 px-3 py-2" value={selectedField.placeholder} onChange={(event) => updateField({ placeholder: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                Подсказка
                <input className="field-base mt-1 px-3 py-2" value={selectedField.helpText} onChange={(event) => updateField({ helpText: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800 md:col-span-2">
                Варианты
                <textarea className="field-base mt-1 min-h-20 px-3 py-2" value={selectedField.optionsText} onChange={(event) => updateField({ optionsText: event.currentTarget.value })} placeholder="value=Label, по одному варианту на строку" />
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                Показывать если поле
                <input className="field-base mt-1 px-3 py-2" value={selectedField.visibleWhenField} onChange={(event) => updateField({ visibleWhenField: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800">
                равно
                <input className="field-base mt-1 px-3 py-2" value={selectedField.visibleWhenValue} onChange={(event) => updateField({ visibleWhenValue: event.currentTarget.value })} />
              </label>
              <label className="block text-sm font-semibold text-slate-800 md:col-span-2">
                Значение для процесса
                <select className="field-base mt-1 px-3 py-2" value={selectedField.processMeaning} onChange={(event) => updateField({ processMeaning: event.currentTarget.value })}>
                  {PROCESS_MEANINGS.map((meaning) => <option key={meaning.value} value={meaning.value}>{meaning.label}</option>)}
                </select>
              </label>
            </div>
            <div className="mt-3 flex justify-end">
              <Button
                type="button"
                variant="ghost"
                leadingIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => onChange({ ...draft, fields: draft.fields.filter((_, index) => index !== safeIndex) })}
              >
                Удалить поле
              </Button>
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Добавьте первое поле формы.</div>
        )}
      </div>
    </section>
  );
}
