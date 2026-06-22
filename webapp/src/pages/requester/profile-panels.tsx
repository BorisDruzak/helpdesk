import { Save, X } from "lucide-react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import {
  RequesterProfileFieldControl,
  formatProfileValue,
  type RequesterProfileValues,
} from "../../features/requester/profile-runtime";
import type {
  RequesterProfileCompletion,
  RequesterProfileSchemaField,
} from "../../features/requester/types";
import { Button, FormActions, StickyActionBar } from "../../features/requester/ui/form-controls";
import {
  fieldValue,
  groupedFields,
  sectionTitle,
  setFieldValue,
  type ProfileMode,
  type RequesterProfileSystemValues,
} from "./profile-workflow";

export function ProfileCompletionAlert({ completion }: { completion: RequesterProfileCompletion | undefined }) {
  if (!completion?.missing_fields?.length) {
    return null;
  }
  return (
    <div className="rounded-panel border border-amber-200 bg-amber-50 px-4 py-3">
      <p className="text-sm font-semibold text-amber-900">Нужно заполнить</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {completion.missing_fields.map((field) => (
          <span className="rounded-panel bg-white px-3 py-1 text-xs font-semibold text-amber-900" key={field.key}>
            {field.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ProfileReadSections({
  displayName,
  fields,
  profileComplete,
  systemValues,
  values,
}: {
  displayName: string;
  fields: RequesterProfileSchemaField[];
  profileComplete: boolean;
  systemValues?: RequesterProfileSystemValues;
  values: RequesterProfileValues;
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-4">
        {groupedFields(fields).map(([section, sectionFields]) => (
          <div className="surface-panel px-5 py-4" key={section}>
            <h2 className="text-lg font-semibold text-slate-950">{sectionTitle(section)}</h2>
            <dl className="mt-4 grid gap-3 md:grid-cols-2">
              {sectionFields.map((field) => (
                <div className="rounded-panel border border-slate-200 bg-white px-3 py-2" key={field.key}>
                  <dt className="text-xs font-semibold uppercase text-slate-500">{field.label || field.key}</dt>
                  <dd className="mt-1 break-words text-sm font-semibold text-slate-950">
                    {formatProfileValue(field, fieldValue(values, field, systemValues))}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
      <aside className="surface-panel h-fit px-5 py-4">
        <p className="text-sm font-semibold text-slate-950">{displayName}</p>
        <p className="mt-2 text-sm text-slate-600">
          {profileComplete ? "Профиль заполнен. Данные можно обновить, если изменилось подразделение, место работы или способ связи." : "Профиль нужно заполнить перед созданием обычного обращения."}
        </p>
      </aside>
    </section>
  );
}

export function ProfileEditSections({
  cancelEdit,
  dirty,
  fieldErrors,
  fieldRefs,
  fields,
  mode,
  onSubmit,
  savePending,
  setFieldErrors,
  setValues,
  systemValues,
  values,
}: {
  cancelEdit: () => void;
  dirty: boolean;
  fieldErrors: Record<string, string>;
  fieldRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  fields: RequesterProfileSchemaField[];
  mode: ProfileMode;
  onSubmit: () => void;
  savePending: boolean;
  setFieldErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setValues: Dispatch<SetStateAction<RequesterProfileValues>>;
  systemValues?: RequesterProfileSystemValues;
  values: RequesterProfileValues;
}) {
  return (
    <form className="space-y-5" noValidate onSubmit={(event) => {
      event.preventDefault();
      onSubmit();
    }}>
      {groupedFields(fields).map(([section, sectionFields], index) => (
        <section aria-labelledby={`requester-profile-section-${index}`} className="surface-panel px-5 py-4" key={section}>
          <h2 className="text-lg font-semibold text-slate-950" id={`requester-profile-section-${index}`}>{sectionTitle(section)}</h2>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {sectionFields.map((field) => (
              <RequesterProfileFieldControl
                error={fieldErrors[field.key]}
                field={field}
                inputRef={(element) => {
                  fieldRefs.current[field.key] = element;
                }}
                key={field.key}
                onChange={(value) => {
                  setValues((current) => setFieldValue(current, field, value));
                  setFieldErrors((current) => {
                    if (!current[field.key]) return current;
                    const next = { ...current };
                    delete next[field.key];
                    return next;
                  });
                }}
                value={fieldValue(values, field, systemValues) ?? (field.type === "checkbox" ? false : "")}
              />
            ))}
          </div>
        </section>
      ))}
      <StickyActionBar className="bottom-4 justify-between rounded-panel shadow-lg">
        <p className="text-sm text-slate-600">
          {dirty ? "Есть несохраненные изменения" : "Изменений нет"}
        </p>
        <FormActions>
          <Button leadingIcon={<X className="h-4 w-4" />} onClick={cancelEdit} type="button" variant="outline">
            Отменить
          </Button>
          <Button disabled={savePending || (!dirty && mode !== "setup")} leadingIcon={<Save className="h-4 w-4" />} type="submit">
            {savePending ? "Сохраняем..." : "Сохранить профиль"}
          </Button>
        </FormActions>
      </StickyActionBar>
    </form>
  );
}
