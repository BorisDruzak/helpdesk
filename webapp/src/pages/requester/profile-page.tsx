import { CheckCircle2, Pencil } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useBlocker, useLocation } from "react-router-dom";

import { updateRequesterProfile } from "../../features/requester/api";
import {
  requesterInvalidations,
  requesterQueryKeys,
  useRequesterProfileQuery,
  useRequesterRegistryOptionsQuery,
} from "../../features/requester/queries";
import {
  buildProfilePayload,
  buildProfileValues,
  missingProfileFields,
  type RequesterProfileValues,
} from "../../features/requester/profile-runtime";
import { requesterErrorMessage } from "../../features/requester/labels";
import {
  fieldsWithRuntimeOptions,
  safeNextPath,
  type ProfileMode,
} from "./profile-workflow";
import { Button, InlineAlert } from "../../features/requester/ui/form-controls";
import {
  ProfileCompletionAlert,
  ProfileEditSections,
  ProfileReadSections,
} from "./profile-panels";

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
  const navigationBlocker = useBlocker(({ currentLocation, nextLocation }) => {
    if (!dirty) {
      return false;
    }
    return `${currentLocation.pathname}${currentLocation.search}` !== `${nextLocation.pathname}${nextLocation.search}`;
  });
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
      setLocalError(requesterErrorMessage(error, "Не удалось сохранить профиль", { domain: "profile", operation: "profile_save" }));
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

  useEffect(() => {
    if (navigationBlocker.state !== "blocked") {
      return;
    }
    if (window.confirm("Есть несохраненные изменения профиля. Покинуть страницу?")) {
      navigationBlocker.proceed();
      return;
    }
    navigationBlocker.reset();
  }, [navigationBlocker]);

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
        {requesterErrorMessage(loadError, "Не удалось загрузить профиль", { domain: "profile" })}
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
              <Button
                leadingIcon={<Pencil className="h-4 w-4" />}
                onClick={() => {
                  setNotice(null);
                  setMode("edit");
                }}
                type="button"
                variant="outline"
              >
                Редактировать
              </Button>
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

      <ProfileCompletionAlert completion={completion} />

      {notice ? (
        <InlineAlert aria-live="polite" role="status" tone="success">
          {notice}
        </InlineAlert>
      ) : null}
      {localError ? (
        <InlineAlert aria-live="assertive" role="alert" tone="danger">
          {localError}
        </InlineAlert>
      ) : null}

      {!isEditing ? (
        <ProfileReadSections
          displayName={displayName}
          fields={readFields}
          profileComplete={profileComplete}
          values={values}
        />
      ) : (
        <ProfileEditSections
          cancelEdit={cancelEdit}
          dirty={dirty}
          fieldErrors={fieldErrors}
          fieldRefs={fieldRefs}
          fields={readFields}
          mode={mode}
          onSubmit={() => {
            if (!validateBeforeSave()) {
              return;
            }
            saveMutation.mutate();
          }}
          savePending={saveMutation.isPending}
          setFieldErrors={setFieldErrors}
          setValues={setValues}
          values={values}
        />
      )}
    </div>
  );
}
