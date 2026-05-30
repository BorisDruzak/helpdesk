import { X } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { AdminServiceCatalogService } from "../service-catalog/api";
import { PROCESS_PROFILES, createDraftFromWizard, type StudioDraft } from "./draft-model";

type WizardState = {
  processProfile: string;
  serviceCode: string;
  title: string;
  description: string;
  visibility: "public" | "internal" | "restricted";
};

export function CreateRequestWizard({
  open,
  services,
  value,
  onChange,
  onClose,
  onCreateDraft,
}: {
  open: boolean;
  services: AdminServiceCatalogService[];
  value: WizardState;
  onChange: (value: WizardState) => void;
  onClose: () => void;
  onCreateDraft: (draft: StudioDraft) => void;
}) {
  if (!open) {
    return null;
  }
  const canCreate = Boolean(value.processProfile && value.serviceCode && value.title.trim());
  return (
    <section className="rounded-md border border-brand-200 bg-white p-5 shadow-soft" aria-label="Мастер создания обращения">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Создать тип обращения</h2>
          <p className="mt-1 text-sm text-slate-600">MVP создаёт черновик на основе существующего раздела и типовой формы.</p>
        </div>
        <button className="rounded p-2 text-slate-500 hover:bg-slate-100" onClick={onClose} type="button" aria-label="Закрыть мастер">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div>
          <p className="text-sm font-semibold text-slate-800">Тип процесса</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {PROCESS_PROFILES.map((profile) => (
              <button
                className={`rounded-pill border px-3 py-2 text-sm font-semibold ${
                  value.processProfile === profile ? "border-brand-600 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-700"
                }`}
                key={profile}
                onClick={() => onChange({ ...value, processProfile: profile })}
                type="button"
              >
                {profile}
              </button>
            ))}
          </div>
        </div>

        <label className="block text-sm font-semibold text-slate-800">
          Раздел
          <select className="field-base mt-2 px-3 py-2" value={value.serviceCode} onChange={(event) => onChange({ ...value, serviceCode: event.currentTarget.value })}>
            <option value="">Выберите раздел</option>
            {services
              .filter((service) => service.lifecycle_status !== "retired")
              .map((service) => (
                <option key={service.code} value={service.code}>
                  {service.public_title || service.code}
                </option>
              ))}
          </select>
        </label>

        <label className="block text-sm font-semibold text-slate-800">
          Название для пользователей
          <input className="field-base mt-2 px-3 py-2" value={value.title} onChange={(event) => onChange({ ...value, title: event.currentTarget.value })} />
        </label>

        <label className="block text-sm font-semibold text-slate-800">
          Видимость
          <select className="field-base mt-2 px-3 py-2" value={value.visibility} onChange={(event) => onChange({ ...value, visibility: event.currentTarget.value as WizardState["visibility"] })}>
            <option value="public">Публичный</option>
            <option value="internal">Внутренний</option>
            <option value="restricted">Restricted</option>
          </select>
        </label>

        <label className="block text-sm font-semibold text-slate-800 lg:col-span-2">
          Краткое описание
          <textarea className="field-base mt-2 min-h-20 px-3 py-2" value={value.description} onChange={(event) => onChange({ ...value, description: event.currentTarget.value })} />
        </label>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" type="button" onClick={onClose}>Отмена</Button>
        <Button
          disabled={!canCreate}
          type="button"
          onClick={() => {
            onCreateDraft(createDraftFromWizard(value));
            onClose();
          }}
        >
          Создать черновик
        </Button>
      </div>
    </section>
  );
}
