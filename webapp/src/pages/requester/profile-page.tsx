import { CheckCircle2, Pencil, Save, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { updateRequesterProfile } from "../../features/requester/api";
import {
  requesterInvalidations,
  requesterQueryKeys,
  useRequesterProfileQuery,
  useRequesterRegistryOptionsQuery,
} from "../../features/requester/queries";
import type {
  RequesterProfile,
  RequesterProfileSchema,
  RequesterProfileSchemaField,
} from "../../features/requester/types";
import {
  RequesterProfileFieldControl,
  buildProfilePayload,
  buildProfileValues,
  formatProfileValue,
  missingProfileFields,
  profileFieldsFromSchema,
  type RequesterProfileValue,
  type RequesterProfileValues,
} from "../../features/requester/profile-runtime";
import { requesterErrorMessage } from "../../features/requester/labels";

type ProfileMode = "read" | "edit" | "setup";

const SAFE_APP_PATH_RE = /^\/app(\/[A-Za-z0-9/_-]*)?(\?[A-Za-z0-9%._~=&-]*)?(#[A-Za-z0-9_-]*)?$/;

function safeNextPath(search: string): string {
  const next = new URLSearchParams(search).get("next") || "/app/requester";
  return SAFE_APP_PATH_RE.test(next) ? next : "/app/requester";
}

function fieldValue(values: RequesterProfileValues, field: RequesterProfileSchemaField): RequesterProfileValue {
  if (field.custom) {
    return values.custom_fields[field.key];
  }
  if (field.key === "full_name") return values.full_name;
  if (field.key === "department_id") return values.department_id;
  if (field.key === "location_id") return values.location_id;
  if (field.key === "phone") return values.phone;
  if (field.key === "internal_extension") return values.internal_extension;
  if (field.key === "position") return values.position;
  if (field.key === "workplace_label") return values.workplace_label;
  if (field.key === "preferred_contact_method") return values.preferred_contact_method;
  return undefined;
}

function setFieldValue(
  values: RequesterProfileValues,
  field: RequesterProfileSchemaField,
  value: RequesterProfileValue,
): RequesterProfileValues {
  if (field.custom) {
    return {
      ...values,
      custom_fields: {
        ...values.custom_fields,
        [field.key]: value,
      },
    };
  }
  if (field.key in values && field.key !== "custom_fields") {
    return { ...values, [field.key]: value } as RequesterProfileValues;
  }
  return values;
}

function fieldsWithRuntimeOptions(
  schema: RequesterProfileSchema | null | undefined,
  departments: Array<{ value: string; label: string }>,
  locations: Array<{ value: string; label: string }>,
): RequesterProfileSchemaField[] {
  return profileFieldsFromSchema(schema)
    .map((field) => {
      if (field.key === "department_id") {
        return { ...field, type: "select", options: field.options?.length ? field.options : departments };
      }
      if (field.key === "location_id") {
        return { ...field, type: "select", options: field.options?.length ? field.options : locations };
      }
      if (field.key === "preferred_contact_method" && !(field.options ?? []).length) {
        return {
          ...field,
          type: "select",
          options: [
            { value: "phone", label: "Телефон" },
            { value: "chat", label: "Чат в обращении" },
            { value: "email", label: "Email" },
          ],
        };
      }
      return field;
    })
    .sort((left, right) => (left.order ?? 1000) - (right.order ?? 1000));
}

function sectionTitle(section: string): string {
  if (section === "identity") return "Основные данные";
  if (section === "contact") return "Связь";
  if (section === "work") return "Рабочий контекст";
  if (section === "custom") return "Дополнительные поля";
  return section;
}

function groupedFields(fields: RequesterProfileSchemaField[]): Array<[string, RequesterProfileSchemaField[]]> {
  const groups = new Map<string, RequesterProfileSchemaField[]>();
  for (const field of fields) {
    const section = field.section || (field.custom ? "custom" : field.key === "phone" || field.key === "internal_extension" ? "contact" : field.key === "position" || field.key === "workplace_label" || field.key === "preferred_contact_method" ? "work" : "identity");
    groups.set(section, [...(groups.get(section) ?? []), field]);
  }
  return Array.from(groups.entries());
}

export function RequesterProfilePage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const profileQuery = useRequesterProfileQuery();
  const registryOptionsQuery = useRequesterRegistryOptionsQuery();
  const detail = profileQuery.data;
  const profile = detail?.profile ?? null;
  const isSetupRoute = location.pathname.endsWith("/profile/setup");
  const [mode, setMode] = useState<ProfileMode>(isSetupRoute ? "setup" : "read");
  const [values, setValues] = useState<RequesterProfileValues>(() => buildProfileValues(null));
  const [savedValues, setSavedValues] = useState<RequesterProfileValues>(() => buildProfileValues(null));
  const [notice, setNotice] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});

  const schema = detail?.profile_schema ?? null;
  const departments = registryOptionsQuery.data?.departments ?? [];
  const locations = registryOptionsQuery.data?.locations ?? [];
  const fields = useMemo(() => fieldsWithRuntimeOptions(schema, departments, locations), [departments, locations, schema]);
  const visibleEditableFields = useMemo(
    () => fields.filter((field) => field.visible !== false && field.editable !== false),
    [fields],
  );
  const readFields = useMemo(() => fields.filter((field) => field.visible !== false), [fields]);
  const isEditing = mode === "edit" || mode === "setup";
  const dirty = useMemo(() => JSON.stringify(values) !== JSON.stringify(savedValues), [savedValues, values]);
  const nextPath = safeNextPath(location.search);
  const saveMutation = useMutation({
    mutationFn: async () => {
      return updateRequesterProfile(buildProfilePayload(values, profile, visibleEditableFields));
    },
    onSuccess: async (result) => {
      const nextValues = buildProfileValues(result.profile);
      setValues(nextValues);
      setSavedValues(nextValues);
      setMode("read");
      setNotice("Профиль сохранен");
      setLocalError(null);
      setFieldErrors({});
      queryClient.setQueryData(requesterQueryKeys.profile(), {
        ...(detail ?? {}),
        profile: result.profile,
        profile_completion: result.profile_completion,
        profile_policy: result.profile_policy,
        profile_schema: result.profile_schema ?? detail?.profile_schema,
      });
      await requesterInvalidations.afterProfileUpdate(queryClient);
    },
    onError: (error) => {
      setLocalError(requesterErrorMessage(error, "Не удалось сохранить профиль"));
    },
  });

  useEffect(() => {
    if (!profileQuery.data) {
      return;
    }
    const nextValues = buildProfileValues(profileQuery.data.profile);
    setValues(nextValues);
    setSavedValues(nextValues);
    if (isSetupRoute || profileQuery.data.profile_completion?.complete === false) {
      setMode("setup");
    }
  }, [isSetupRoute, profileQuery.data]);

  useEffect(() => {
    if (!dirty) {
      return undefined;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  function cancelEdit() {
    if (dirty && !window.confirm("Есть несохраненные изменения профиля. Отменить их?")) {
      return;
    }
    setValues(savedValues);
    setLocalError(null);
    setFieldErrors({});
    setMode(detail?.profile_completion?.complete === false || isSetupRoute ? "setup" : "read");
  }

  function validateBeforeSave(): boolean {
    const missing = missingProfileFields(schema, values);
    if (!missing.length) {
      setFieldErrors({});
      setLocalError(null);
      return true;
    }
    const nextErrors = Object.fromEntries(missing.map((field) => [field.key, `Заполните поле: ${field.label}.`]));
    setFieldErrors(nextErrors);
    setLocalError(`Заполните обязательные поля: ${missing.map((field) => field.label).join(", ")}.`);
    window.requestAnimationFrame(() => {
      const firstKey = missing[0]?.key;
      if (firstKey) {
        fieldRefs.current[firstKey]?.focus();
      }
    });
    return false;
  }

  if (profileQuery.isLoading || registryOptionsQuery.isLoading) {
    return (
      <section className="space-y-4">
        <p className="text-sm text-slate-500">Загружаем профиль...</p>
      </section>
    );
  }

  const loadError = profileQuery.error ?? registryOptionsQuery.error;
  if (loadError) {
    return (
      <section className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
        {requesterErrorMessage(loadError, "Не удалось загрузить профиль")}
      </section>
    );
  }

  const completion = detail?.profile_completion;
  const profileComplete = completion?.complete !== false;
  const pageTitle = mode === "setup" ? "Заполните профиль" : "Профиль";
  const displayName = values.full_name || profile?.display_name || "Пользователь";

  return (
    <div aria-labelledby="requester-profile-title" className="space-y-5">
      <header className="surface-panel px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="workspace-boot__eyebrow">Кабинет пользователя</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950" id="requester-profile-title">{pageTitle}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Данные профиля помогают поддержке понять, где находится рабочее место и как быстрее связаться с вами.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!isEditing ? (
              <button
                className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800"
                onClick={() => {
                  setNotice(null);
                  setMode("edit");
                }}
                type="button"
              >
                <Pencil className="h-4 w-4" />
                Редактировать
              </button>
            ) : null}
            {notice && profileComplete ? (
              <Link
                className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-3 py-2 text-sm font-semibold text-white"
                to={nextPath}
              >
                <CheckCircle2 className="h-4 w-4" />
                Продолжить
              </Link>
            ) : null}
          </div>
        </div>
      </header>

      {completion?.missing_fields?.length ? (
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
      ) : null}

      {notice ? (
        <div aria-live="polite" className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700" role="status">
          {notice}
        </div>
      ) : null}
      {localError ? (
        <div aria-live="assertive" className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
          {localError}
        </div>
      ) : null}

      {!isEditing ? (
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            {groupedFields(readFields).map(([section, sectionFields]) => (
              <div className="surface-panel px-5 py-4" key={section}>
                <h2 className="text-lg font-semibold text-slate-950">{sectionTitle(section)}</h2>
                <dl className="mt-4 grid gap-3 md:grid-cols-2">
                  {sectionFields.map((field) => (
                    <div className="rounded-panel border border-slate-200 bg-white px-3 py-2" key={field.key}>
                      <dt className="text-xs font-semibold uppercase text-slate-500">{field.label || field.key}</dt>
                      <dd className="mt-1 break-words text-sm font-semibold text-slate-950">
                        {formatProfileValue(field, fieldValue(values, field))}
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
      ) : (
        <form className="space-y-5" noValidate onSubmit={(event) => {
          event.preventDefault();
          if (!validateBeforeSave()) {
            return;
          }
          saveMutation.mutate();
        }}>
          {groupedFields(readFields).map(([section, sectionFields], index) => (
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
                    value={fieldValue(values, field) ?? (field.type === "checkbox" ? false : "")}
                  />
                ))}
              </div>
            </section>
          ))}
          <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-panel border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
            <p className="text-sm text-slate-600">
              {dirty ? "Есть несохраненные изменения" : "Изменений нет"}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800"
                onClick={cancelEdit}
                type="button"
              >
                <X className="h-4 w-4" />
                Отменить
              </button>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={saveMutation.isPending || (!dirty && mode !== "setup")}
                type="submit"
              >
                <Save className="h-4 w-4" />
                {saveMutation.isPending ? "Сохраняем..." : "Сохранить профиль"}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
