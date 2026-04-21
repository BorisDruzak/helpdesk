import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AdminFormsFieldItem,
  type AdminFormsFieldOption,
  type AdminFormsFieldType,
  type AdminFormsPayload,
  type AdminFormsSaveRequest,
  fetchAdminFormsCatalog,
  saveAdminFormsCatalog
} from "./api";


type ActionFeedback =
  | {
      tone: "success" | "error";
      text: string;
    }
  | null;

type DraftField = {
  key: string;
  label: string;
  type: AdminFormsFieldType;
  required: boolean;
  placeholder: string;
  help_text: string;
  options: AdminFormsFieldOption[];
  visible_when: {
    field: string;
    equals: string;
    values: string[];
  };
};

type DraftForm = {
  key: string;
  request_kind: string;
  title: string;
  description: string;
  fields: DraftField[];
};

type DraftCatalog = {
  title: string;
  description: string;
  forms: DraftForm[];
};


function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}


function hydrateDraft(payload: AdminFormsPayload): DraftCatalog {
  return {
    title: payload.summary.title,
    description: payload.summary.description ?? "",
    forms: payload.forms.map((form) => ({
      key: form.key,
      request_kind: form.request_kind,
      title: form.title,
      description: form.description ?? "",
      fields: form.fields.map((field) => ({
        key: field.key,
        label: field.label,
        type: field.type,
        required: field.required,
        placeholder: field.placeholder ?? "",
        help_text: field.help_text ?? "",
        options: field.options.map((option) => ({
          value: option.value,
          label: option.label
        })),
        visible_when: {
          field: field.visible_when?.field ?? "",
          equals: field.visible_when?.equals ?? "",
          values: [...(field.visible_when?.values ?? [])]
        }
      }))
    }))
  };
}


function serializeDraft(catalog: DraftCatalog): AdminFormsSaveRequest {
  return {
    title: catalog.title,
    description: catalog.description,
    forms: catalog.forms.map((form) => ({
      key: form.key,
      request_kind: form.request_kind,
      title: form.title,
      description: form.description,
      fields: form.fields.map((field) => {
        const options = field.options.filter((option) => option.value.trim() && option.label.trim());
        const values = field.visible_when.values.filter((item) => item.trim());
        const visibleWhen =
          field.visible_when.field.trim() && (field.visible_when.equals.trim() || values.length)
            ? {
                field: field.visible_when.field.trim(),
                ...(field.visible_when.equals.trim()
                  ? {
                      equals: field.visible_when.equals.trim()
                    }
                  : {}),
                ...(values.length
                  ? {
                      values
                    }
                  : {})
              }
            : undefined;

        return {
          key: field.key,
          label: field.label,
          type: field.type,
          required: field.required,
          ...(field.placeholder.trim()
            ? {
                placeholder: field.placeholder.trim()
              }
            : {}),
          ...(field.help_text.trim()
            ? {
                help_text: field.help_text.trim()
              }
            : {}),
          options,
          ...(visibleWhen
            ? {
                visible_when: visibleWhen
              }
            : {})
        };
      })
    }))
  };
}


function buildDraftFingerprint(catalog: DraftCatalog): string {
  return JSON.stringify(serializeDraft(catalog));
}


function createEmptyField(type: AdminFormsFieldType, index: number): DraftField {
  const baseKey = type === "checkbox" ? "confirmed" : "field";
  return {
    key: `${baseKey}_${index}`,
    label: "Новое поле",
    type,
    required: false,
    placeholder: "",
    help_text: "",
    options:
      type === "select" || type === "radio"
        ? [
            { value: "option_1", label: "Вариант 1" },
            { value: "option_2", label: "Вариант 2" }
          ]
        : [],
    visible_when: {
      field: "",
      equals: "",
      values: []
    }
  };
}


function createEmptyForm(index: number): DraftForm {
  const key = `new_form_${index}`;
  return {
    key,
    request_kind: key,
    title: "Новая форма",
    description: "",
    fields: [createEmptyField("text", 1)]
  };
}


function nextFormIndex(forms: DraftForm[]): number {
  return forms.length + 1;
}


function nextFieldIndex(fields: DraftField[]): number {
  return fields.length + 1;
}


function fieldOptionsToText(field: DraftField): string {
  return field.options.map((option) => `${option.value}|${option.label}`).join("\n");
}


function parseFieldOptions(text: string): AdminFormsFieldOption[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [valuePart, ...labelParts] = line.split("|");
      const value = valuePart?.trim() || `option_${index + 1}`;
      const label = labelParts.join("|").trim() || value;
      return {
        value,
        label
      };
    });
}


function valuesToText(values: string[]): string {
  return values.join("\n");
}


function parseValueLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}


function updateFormInCatalog(
  catalog: DraftCatalog,
  formKey: string,
  updater: (form: DraftForm) => DraftForm
): DraftCatalog {
  return {
    ...catalog,
    forms: catalog.forms.map((form) => (form.key === formKey ? updater(form) : form))
  };
}


function updateFieldInCatalog(
  catalog: DraftCatalog,
  formKey: string,
  fieldKey: string,
  updater: (field: DraftField) => DraftField
): DraftCatalog {
  return updateFormInCatalog(catalog, formKey, (form) => ({
    ...form,
    fields: form.fields.map((field) => (field.key === fieldKey ? updater(field) : field))
  }));
}


function fieldTypeRequiresOptions(field: AdminFormsFieldItem | DraftField | null): boolean {
  return field?.type === "select" || field?.type === "radio";
}


export function FormsBuilderPanel() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<DraftCatalog | null>(null);
  const [selectedFormKey, setSelectedFormKey] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [newFieldType, setNewFieldType] = useState<AdminFormsFieldType>("text");
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);

  const formsQuery = useQuery({
    queryKey: ["admin-forms-builder"],
    queryFn: fetchAdminFormsCatalog,
    retry: false
  });

  const saveMutation = useMutation({
    mutationFn: saveAdminFormsCatalog,
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text: result.message
      });
      queryClient.setQueryData<AdminFormsPayload | undefined>(["admin-forms-builder"], (current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          summary: result.summary,
          forms: result.forms
        };
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-forms-builder"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать каталог форм."
      });
    }
  });

  useEffect(() => {
    if (!formsQuery.data) {
      return;
    }
    setDraft(hydrateDraft(formsQuery.data));
  }, [formsQuery.data]);

  useEffect(() => {
    if (!draft?.forms.length) {
      if (selectedFormKey !== null) {
        setSelectedFormKey(null);
      }
      return;
    }

    if (!selectedFormKey || !draft.forms.some((form) => form.key === selectedFormKey)) {
      setSelectedFormKey(draft.forms[0].key);
    }
  }, [draft, selectedFormKey]);

  const selectedForm = draft?.forms.find((form) => form.key === selectedFormKey) ?? draft?.forms[0] ?? null;

  useEffect(() => {
    if (!selectedForm?.fields.length) {
      if (selectedFieldKey !== null) {
        setSelectedFieldKey(null);
      }
      return;
    }

    if (!selectedFieldKey || !selectedForm.fields.some((field) => field.key === selectedFieldKey)) {
      setSelectedFieldKey(selectedForm.fields[0].key);
    }
  }, [selectedFieldKey, selectedForm]);

  const selectedField =
    selectedForm?.fields.find((field) => field.key === selectedFieldKey) ?? selectedForm?.fields[0] ?? null;

  const hasUnsavedChanges =
    Boolean(draft) &&
    Boolean(formsQuery.data) &&
    buildDraftFingerprint(draft!) !== buildDraftFingerprint(hydrateDraft(formsQuery.data!));

  return (
    <section className="support-workspace__panel admin-forms-panel">
      <div className="support-workspace__panel-head">
        <div>
          <h2>Конструктор форм заявок</h2>
          <p>
            Новый typed slice управляет рабочим каталогом `request_forms` без legacy iframe: формы,
            поля и публикация новой версии теперь живут прямо в `/app/admin`.
          </p>
        </div>
      </div>

      {formsQuery.isLoading ? (
        <div className="support-detail-note">Загружаем текущий каталог форм и активную версию…</div>
      ) : null}

      {formsQuery.isError ? (
        <div className="support-detail-error">
          {formsQuery.error instanceof Error ? formsQuery.error.message : "Не удалось загрузить каталог форм."}
        </div>
      ) : null}

      {actionFeedback ? (
        <div className={actionFeedback.tone === "success" ? "support-detail-note" : "support-detail-error"}>
          {actionFeedback.text}
        </div>
      ) : null}

      {formsQuery.data && draft ? (
        <>
          <div className="support-snapshot-grid">
            <article className="support-snapshot-card">
              <span>Активная версия</span>
              <strong>{formsQuery.data.summary.version}</strong>
              <p>Форм в каталоге: {formsQuery.data.summary.forms_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>Всего полей</span>
              <strong>{formsQuery.data.summary.fields_count}</strong>
              <p>Обязательных: {formsQuery.data.summary.required_fields_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>Последняя публикация</span>
              <strong>{formsQuery.data.summary.last_published_by ?? "builtin_default"}</strong>
              <p>{formatDateTime(formsQuery.data.summary.last_published_at)}</p>
            </article>
          </div>

          <section className="admin-forms-toolbar">
            <label className="support-filter-search">
              <span>Название каталога</span>
              <input
                aria-label="Название каталога"
                value={draft.title}
                onChange={(event) => {
                  const value = event.currentTarget.value;
                  setActionFeedback(null);
                  setDraft((current) => (current ? { ...current, title: value } : current));
                }}
                placeholder="Каталог заявок"
              />
            </label>

            <details className="admin-forms-advanced">
              <summary>Расширенные настройки каталога</summary>
              <label className="support-filter-search">
                <span>Описание каталога</span>
                <textarea
                  aria-label="Описание каталога"
                  value={draft.description}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setActionFeedback(null);
                    setDraft((current) => (current ? { ...current, description: value } : current));
                  }}
                  placeholder="Краткое описание каталога для операторов"
                />
              </label>
              <p className="admin-forms-advanced__hint">
                После сохранения сервер сам выпустит новую активную версию каталога и сразу сделает её рабочей.
              </p>
            </details>

            <button
              type="button"
              className="admin-modules-action"
              disabled={!hasUnsavedChanges || saveMutation.isPending}
              onClick={() => {
                if (!draft) {
                  return;
                }
                setActionFeedback(null);
                saveMutation.mutate(serializeDraft(draft));
              }}
            >
              {saveMutation.isPending ? "Публикуем…" : "Сохранить изменения"}
            </button>
          </section>

          <div className="admin-forms-grid">
            <article className="support-operation-card admin-forms-list">
              <div className="support-operations__head">
                <strong>Формы каталога</strong>
                <span>{draft.forms.length}</span>
              </div>

              <button
                type="button"
                className="admin-modules-action admin-forms-inline-action"
                onClick={() => {
                  setActionFeedback(null);
                  setDraft((current) => {
                    if (!current) {
                      return current;
                    }
                    const nextIndex = nextFormIndex(current.forms);
                    const nextForm = createEmptyForm(nextIndex);
                    setSelectedFormKey(nextForm.key);
                    setSelectedFieldKey(nextForm.fields[0]?.key ?? null);
                    return {
                      ...current,
                      forms: [...current.forms, nextForm]
                    };
                  });
                }}
              >
                Новая форма
              </button>

              {draft.forms.length ? (
                draft.forms.map((form) => (
                  <button
                    key={form.key}
                    type="button"
                    className={`admin-module-card${selectedForm?.key === form.key ? " active" : ""}`}
                    onClick={() => {
                      setActionFeedback(null);
                      setSelectedFormKey(form.key);
                      setSelectedFieldKey(form.fields[0]?.key ?? null);
                    }}
                  >
                    <div className="admin-observer-item__head">
                      <strong>{form.title || form.key}</strong>
                      <span>{form.fields.length} полей</span>
                    </div>
                    <p>Ключ: {form.key}</p>
                    <p>request_kind: {form.request_kind || form.key}</p>
                  </button>
                ))
              ) : (
                <div className="support-queue-empty">В каталоге пока нет форм. Добавьте первую форму слева.</div>
              )}
            </article>

            <article className="support-operation-card admin-forms-editor">
              <div className="support-operations__head">
                <strong>Редактор формы</strong>
                <span>{selectedForm?.key ?? "Нет выбора"}</span>
              </div>

              {selectedForm ? (
                <>
                  <div className="admin-forms-editor__header">
                    <label className="support-filter-search">
                      <span>Название формы</span>
                      <input
                        aria-label="Название формы"
                        value={selectedForm.title}
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          setActionFeedback(null);
                          setDraft((current) =>
                            current
                              ? updateFormInCatalog(current, selectedForm.key, (form) => ({ ...form, title: value }))
                              : current
                          );
                        }}
                        placeholder="Печать / принтер"
                      />
                    </label>

                    <label className="support-filter-search">
                      <span>Ключ формы</span>
                      <input
                        aria-label="Ключ формы"
                        value={selectedForm.key}
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          setActionFeedback(null);
                          setDraft((current) => {
                            if (!current) {
                              return current;
                            }
                            return {
                              ...current,
                              forms: current.forms.map((form) =>
                                form.key === selectedForm.key
                                  ? {
                                      ...form,
                                      key: value,
                                      request_kind: form.request_kind === selectedForm.key ? value : form.request_kind
                                    }
                                  : form
                              )
                            };
                          });
                          setSelectedFormKey(value);
                        }}
                        placeholder="printer"
                      />
                    </label>

                    <button
                      type="button"
                      className="admin-modules-action admin-forms-inline-action"
                      disabled={draft.forms.length <= 1}
                      onClick={() => {
                        setActionFeedback(null);
                        setDraft((current) => {
                          if (!current) {
                            return current;
                          }
                          const nextForms = current.forms.filter((form) => form.key !== selectedForm.key);
                          setSelectedFormKey(nextForms[0]?.key ?? null);
                          setSelectedFieldKey(nextForms[0]?.fields[0]?.key ?? null);
                          return {
                            ...current,
                            forms: nextForms
                          };
                        });
                      }}
                    >
                      Удалить форму
                    </button>
                  </div>

                  <details className="admin-forms-advanced" open>
                    <summary>Расширенные настройки формы</summary>
                    <div className="admin-forms-advanced__grid">
                      <label className="support-filter-search">
                        <span>request_kind</span>
                        <input
                          aria-label="Request kind"
                          value={selectedForm.request_kind}
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            setActionFeedback(null);
                            setDraft((current) =>
                              current
                                ? updateFormInCatalog(current, selectedForm.key, (form) => ({ ...form, request_kind: value }))
                                : current
                            );
                          }}
                          placeholder="printer"
                        />
                      </label>
                      <label className="support-filter-search">
                        <span>Описание формы</span>
                        <textarea
                          aria-label="Описание формы"
                          value={selectedForm.description}
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            setActionFeedback(null);
                            setDraft((current) =>
                              current
                                ? updateFormInCatalog(current, selectedForm.key, (form) => ({ ...form, description: value }))
                                : current
                            );
                          }}
                          placeholder="Краткое описание, которое увидит пользователь"
                        />
                      </label>
                    </div>
                  </details>

                  <section className="admin-forms-fields">
                    <div className="support-operations__head">
                      <strong>Поля формы</strong>
                      <span>{selectedForm.fields.length}</span>
                    </div>

                    <div className="admin-forms-fields__toolbar">
                      <label className="support-filter-select">
                        <span>Тип нового поля</span>
                        <select
                          aria-label="Тип нового поля"
                          value={newFieldType}
                          onChange={(event) => {
                            setNewFieldType(event.currentTarget.value as AdminFormsFieldType);
                          }}
                        >
                          {formsQuery.data.capabilities.field_type_options.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <button
                        type="button"
                        className="admin-modules-action admin-forms-inline-action"
                        onClick={() => {
                          setActionFeedback(null);
                          setDraft((current) => {
                            if (!current) {
                              return current;
                            }
                            const form = current.forms.find((item) => item.key === selectedForm.key);
                            const field = createEmptyField(newFieldType, nextFieldIndex(form?.fields ?? []));
                            setSelectedFieldKey(field.key);
                            return updateFormInCatalog(current, selectedForm.key, (item) => ({
                              ...item,
                              fields: [...item.fields, field]
                            }));
                          });
                        }}
                      >
                        Добавить поле
                      </button>
                    </div>

                    <div className="admin-forms-fields__grid">
                      <div className="admin-forms-field-list">
                        {selectedForm.fields.length ? (
                          selectedForm.fields.map((field) => (
                            <button
                              key={field.key}
                              type="button"
                              className={`admin-module-card${selectedField?.key === field.key ? " active" : ""}`}
                              onClick={() => {
                                setActionFeedback(null);
                                setSelectedFieldKey(field.key);
                              }}
                            >
                              <div className="admin-observer-item__head">
                                <strong>{field.label || field.key}</strong>
                                <span>{field.type}</span>
                              </div>
                              <p>Ключ: {field.key}</p>
                              <p>{field.required ? "Обязательное поле" : "Необязательное поле"}</p>
                            </button>
                          ))
                        ) : (
                          <div className="support-queue-empty">В форме пока нет полей. Добавьте первое поле.</div>
                        )}
                      </div>

                      <div className="admin-forms-field-editor">
                        {selectedField ? (
                          <>
                            <div className="admin-forms-editor__header">
                              <strong>Параметры поля</strong>
                              <button
                                type="button"
                                className="admin-modules-action admin-forms-inline-action"
                                disabled={selectedForm.fields.length <= 1}
                                onClick={() => {
                                  setActionFeedback(null);
                                  setDraft((current) => {
                                    if (!current) {
                                      return current;
                                    }
                                    const remainingFields = selectedForm.fields.filter((field) => field.key !== selectedField.key);
                                    setSelectedFieldKey(remainingFields[0]?.key ?? null);
                                    return updateFormInCatalog(current, selectedForm.key, (form) => ({
                                      ...form,
                                      fields: form.fields.filter((field) => field.key !== selectedField.key)
                                    }));
                                  });
                                }}
                              >
                                Удалить поле
                              </button>
                            </div>

                            <div className="admin-forms-advanced__grid">
                              <label className="support-filter-search">
                                <span>Название поля</span>
                                <input
                                  aria-label="Название поля"
                                  value={selectedField.label}
                                  onChange={(event) => {
                                    const value = event.currentTarget.value;
                                    setActionFeedback(null);
                                    setDraft((current) =>
                                      current
                                        ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                            ...field,
                                            label: value
                                          }))
                                        : current
                                    );
                                  }}
                                  placeholder="Кабинет"
                                />
                              </label>

                              <label className="support-filter-search">
                                <span>Ключ поля</span>
                                <input
                                  aria-label="Ключ поля"
                                  value={selectedField.key}
                                  onChange={(event) => {
                                    const value = event.currentTarget.value;
                                    setActionFeedback(null);
                                    setDraft((current) =>
                                      current
                                        ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                            ...field,
                                            key: value
                                          }))
                                        : current
                                    );
                                    setSelectedFieldKey(value);
                                  }}
                                  placeholder="room"
                                />
                              </label>

                              <label className="support-filter-select">
                                <span>Тип поля</span>
                                <select
                                  aria-label="Тип поля"
                                  value={selectedField.type}
                                  onChange={(event) => {
                                    const value = event.currentTarget.value as AdminFormsFieldType;
                                    setActionFeedback(null);
                                    setDraft((current) =>
                                      current
                                        ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                            ...field,
                                            type: value,
                                            options:
                                              value === "select" || value === "radio"
                                                ? field.options.length
                                                  ? field.options
                                                  : [
                                                      { value: "option_1", label: "Вариант 1" },
                                                      { value: "option_2", label: "Вариант 2" }
                                                    ]
                                                : []
                                          }))
                                        : current
                                    );
                                  }}
                                >
                                  {formsQuery.data.capabilities.field_type_options.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              </label>

                              <label className="admin-modules-toggle">
                                <input
                                  type="checkbox"
                                  checked={selectedField.required}
                                  onChange={(event) => {
                                    const checked = event.currentTarget.checked;
                                    setActionFeedback(null);
                                    setDraft((current) =>
                                      current
                                        ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                            ...field,
                                            required: checked
                                          }))
                                        : current
                                    );
                                  }}
                                />
                                <span>Поле обязательно</span>
                              </label>
                            </div>

                            <details className="admin-forms-advanced" open>
                              <summary>Расширенные настройки поля</summary>
                              <div className="admin-forms-advanced__grid">
                                <label className="support-filter-search">
                                  <span>Placeholder</span>
                                  <input
                                    aria-label="Placeholder"
                                    value={selectedField.placeholder}
                                    onChange={(event) => {
                                      const value = event.currentTarget.value;
                                      setActionFeedback(null);
                                      setDraft((current) =>
                                        current
                                          ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                              ...field,
                                              placeholder: value
                                            }))
                                          : current
                                      );
                                    }}
                                    placeholder="Подсказка в поле ввода"
                                  />
                                </label>

                                <label className="support-filter-search">
                                  <span>Help text</span>
                                  <textarea
                                    aria-label="Help text"
                                    value={selectedField.help_text}
                                    onChange={(event) => {
                                      const value = event.currentTarget.value;
                                      setActionFeedback(null);
                                      setDraft((current) =>
                                        current
                                          ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                              ...field,
                                              help_text: value
                                            }))
                                          : current
                                      );
                                    }}
                                    placeholder="Краткое пояснение для пользователя"
                                  />
                                </label>

                                {fieldTypeRequiresOptions(selectedField) ? (
                                  <label className="support-filter-search admin-forms-options-field">
                                    <span>Варианты ответа</span>
                                    <textarea
                                      aria-label="Варианты ответа"
                                      value={fieldOptionsToText(selectedField)}
                                      onChange={(event) => {
                                        const value = event.currentTarget.value;
                                        setActionFeedback(null);
                                        setDraft((current) =>
                                          current
                                            ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                                ...field,
                                                options: parseFieldOptions(value)
                                              }))
                                            : current
                                        );
                                      }}
                                      placeholder={"value|label\nprinter|Принтер"}
                                    />
                                  </label>
                                ) : null}

                                <label className="support-filter-search">
                                  <span>visible_when.field</span>
                                  <input
                                    aria-label="Поле условия"
                                    value={selectedField.visible_when.field}
                                    onChange={(event) => {
                                      const value = event.currentTarget.value;
                                      setActionFeedback(null);
                                      setDraft((current) =>
                                        current
                                          ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                              ...field,
                                              visible_when: {
                                                ...field.visible_when,
                                                field: value
                                              }
                                            }))
                                          : current
                                      );
                                    }}
                                    placeholder="issue_kind"
                                  />
                                </label>

                                <label className="support-filter-search">
                                  <span>visible_when.equals</span>
                                  <input
                                    aria-label="Значение условия"
                                    value={selectedField.visible_when.equals}
                                    onChange={(event) => {
                                      const value = event.currentTarget.value;
                                      setActionFeedback(null);
                                      setDraft((current) =>
                                        current
                                          ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                              ...field,
                                              visible_when: {
                                                ...field.visible_when,
                                                equals: value
                                              }
                                            }))
                                          : current
                                      );
                                    }}
                                    placeholder="site_down"
                                  />
                                </label>

                                <label className="support-filter-search">
                                  <span>visible_when.values</span>
                                  <textarea
                                    aria-label="Список значений условия"
                                    value={valuesToText(selectedField.visible_when.values)}
                                    onChange={(event) => {
                                      const value = event.currentTarget.value;
                                      setActionFeedback(null);
                                      setDraft((current) =>
                                        current
                                          ? updateFieldInCatalog(current, selectedForm.key, selectedField.key, (field) => ({
                                              ...field,
                                              visible_when: {
                                                ...field.visible_when,
                                                values: parseValueLines(value)
                                              }
                                            }))
                                          : current
                                      );
                                    }}
                                    placeholder={"single\nmultiple"}
                                  />
                                </label>
                              </div>
                            </details>
                          </>
                        ) : (
                          <div className="support-queue-empty">Выберите поле слева, чтобы настроить его параметры.</div>
                        )}
                      </div>
                    </div>
                  </section>
                </>
              ) : (
                <div className="support-queue-empty">Выберите форму слева или создайте новую форму.</div>
              )}
            </article>
          </div>
        </>
      ) : null}
    </section>
  );
}
