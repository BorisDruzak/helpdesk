import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ClipboardList,
  FileClock,
  FilePenLine,
  FolderClock,
  Plus,
  RefreshCcw,
  Save,
  Star,
  Trash2,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { cn } from "../../shared/ui/cn";
import {
  type AdminFormsFieldItem,
  type AdminFormsFieldOption,
  type AdminFormsFieldType,
  type AdminFormsPayload,
  type AdminFormsPlaybookTrigger,
  type AdminFormsRoutePreviewResult,
  type AdminFormsSaveRequest,
  fetchAdminFormsCatalog,
  previewAdminFormRoute,
  saveAdminFormsCatalog,
} from "./api";
import {
  fetchTicketFormsPackList,
  fetchTicketFormsPackVersion,
  setTicketFormsPackPreferred,
  type TicketFormsPackSummary,
} from "./catalog-api";

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
  playbook_triggers: AdminFormsPlaybookTrigger[];
  fields: DraftField[];
};

type DraftCatalog = {
  title: string;
  description: string;
  forms: DraftForm[];
};

type PreviewFormValues = Record<string, string | boolean>;

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
    timeStyle: "short",
  }).format(date);
}

function getPlaybookTriggerReadiness(trigger: AdminFormsPlaybookTrigger | undefined) {
  if (!trigger?.enabled) {
    return {
      tone: "neutral" as const,
      label: "Запуск выключен",
      detail: "Форма только создаёт тикет и передаёт данные в маршрутизацию.",
    };
  }

  if (!trigger.playbook_key.trim()) {
    return {
      tone: "warning" as const,
      label: "Нужен ключ плейбука",
      detail: "Укажите опубликованный playbook key, иначе автодиагностика не стартует.",
    };
  }

  return {
    tone: "success" as const,
    label: "Готов к запуску после создания тикета",
    detail: "После intake форма создаст тикет, routing выберет очередь, затем запустится диагностический сценарий.",
  };
}

function describeRouteCondition(condition: Record<string, unknown> | null): string {
  if (!condition) {
    return "Условие не задано";
  }

  const field = typeof condition.field === "string" ? condition.field : "";
  const op = typeof condition.op === "string" ? condition.op : "";
  const value = condition.value;
  const values = Array.isArray(condition.values) ? condition.values : null;
  const displayValue = values
    ? values.map((item) => String(item)).join(", ")
    : typeof value === "boolean"
      ? (value ? "true" : "false")
      : value === null || value === undefined
        ? ""
        : String(value);

  if (field && op) {
    const operatorLabel = op === "eq" ? "=" : op === "neq" ? "!=" : op === "in" ? "в списке" : op;
    return `${field} ${operatorLabel} ${displayValue}`.trim();
  }

  if (Array.isArray(condition.all) || Array.isArray(condition.any)) {
    return "Составное условие из нескольких правил";
  }

  return "Сложное условие правила";
}

function hydrateDraft(payload: Pick<AdminFormsPayload, "summary" | "forms">): DraftCatalog {
  return {
    title: payload.summary.title,
    description: payload.summary.description ?? "",
    forms: payload.forms.map((form) => ({
      key: form.key,
      request_kind: form.request_kind,
      title: form.title,
      description: form.description ?? "",
      playbook_triggers: form.playbook_triggers ?? [],
      fields: form.fields.map((field) => ({
        key: field.key,
        label: field.label,
        type: field.type,
        required: field.required,
        placeholder: field.placeholder ?? "",
        help_text: field.help_text ?? "",
        options: field.options.map((option) => ({
          value: option.value,
          label: option.label,
        })),
        visible_when: {
          field: field.visible_when?.field ?? "",
          equals: field.visible_when?.equals ?? "",
          values: [...(field.visible_when?.values ?? [])],
        },
      })),
    })),
  };
}

function hydrateDraftFromPack(pack: Record<string, unknown>): DraftCatalog {
  const formsRaw = Array.isArray(pack.forms) ? pack.forms : [];
  return {
    title: String(pack.title ?? "Каталог заявок"),
    description: String(pack.description ?? ""),
    forms: formsRaw.map((formRaw, formIndex) => {
      const form = typeof formRaw === "object" && formRaw !== null ? formRaw : {};
      const fieldsRaw = Array.isArray((form as { fields?: unknown[] }).fields)
        ? ((form as { fields: unknown[] }).fields ?? [])
        : [];

      return {
        key: String((form as { key?: unknown }).key ?? `form_${formIndex + 1}`),
        request_kind: String(
          (form as { request_kind?: unknown }).request_kind ??
            (form as { key?: unknown }).key ??
            `form_${formIndex + 1}`
        ),
        title: String((form as { title?: unknown }).title ?? "Новая форма"),
        description: String((form as { description?: unknown }).description ?? ""),
        playbook_triggers: Array.isArray((form as { playbook_triggers?: unknown[] }).playbook_triggers)
          ? ((form as { playbook_triggers: unknown[] }).playbook_triggers ?? [])
              .map((triggerRaw) => {
                const trigger = typeof triggerRaw === "object" && triggerRaw !== null ? triggerRaw : {};
                const moduleKind: AdminFormsPlaybookTrigger["module_kind"] =
                  String((trigger as { module_kind?: unknown }).module_kind ?? "diagnostic") === "remediation"
                    ? "remediation"
                    : "diagnostic";
                return {
                  event: "ticket_created" as const,
                  playbook_key: String((trigger as { playbook_key?: unknown }).playbook_key ?? ""),
                  module_kind: moduleKind,
                  enabled: Boolean((trigger as { enabled?: unknown }).enabled ?? true),
                };
              })
              .filter((trigger) => trigger.playbook_key.trim())
          : [],
        fields: fieldsRaw.map((fieldRaw, fieldIndex) => {
          const field = typeof fieldRaw === "object" && fieldRaw !== null ? fieldRaw : {};
          const optionsRaw = Array.isArray((field as { options?: unknown[] }).options)
            ? ((field as { options: unknown[] }).options ?? [])
            : [];
          const visibleWhen =
            typeof (field as { visible_when?: unknown }).visible_when === "object" &&
            (field as { visible_when?: unknown }).visible_when !== null
              ? ((field as { visible_when: Record<string, unknown> }).visible_when ?? {})
              : {};
          return {
            key: String((field as { key?: unknown }).key ?? `field_${fieldIndex + 1}`),
            label: String((field as { label?: unknown }).label ?? "Поле"),
            type: String((field as { type?: unknown }).type ?? "text") as AdminFormsFieldType,
            required: Boolean((field as { required?: unknown }).required),
            placeholder: String((field as { placeholder?: unknown }).placeholder ?? ""),
            help_text: String((field as { help_text?: unknown }).help_text ?? ""),
            options: optionsRaw
              .map((optionRaw) => {
                const option = typeof optionRaw === "object" && optionRaw !== null ? optionRaw : {};
                return {
                  value: String((option as { value?: unknown }).value ?? ""),
                  label: String((option as { label?: unknown }).label ?? ""),
                };
              })
              .filter((option) => option.value.trim() && option.label.trim()),
            visible_when: {
              field: String(visibleWhen.field ?? ""),
              equals: String(visibleWhen.equals ?? ""),
              values: Array.isArray(visibleWhen.values)
                ? visibleWhen.values.map((item) => String(item ?? ""))
                : Array.isArray(visibleWhen.in)
                  ? visibleWhen.in.map((item) => String(item ?? ""))
                  : [],
            },
          };
        }),
      };
    }),
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
      playbook_triggers: form.playbook_triggers,
      fields: form.fields.map((field) => {
        const options = field.options.filter((option) => option.value.trim() && option.label.trim());
        const values = field.visible_when.values.filter((item) => item.trim());
        const visibleWhen =
          field.visible_when.field.trim() && (field.visible_when.equals.trim() || values.length)
            ? {
                field: field.visible_when.field.trim(),
                ...(field.visible_when.equals.trim()
                  ? {
                      equals: field.visible_when.equals.trim(),
                    }
                  : {}),
                ...(values.length
                  ? {
                      values,
                    }
                  : {}),
              }
            : undefined;

        return {
          key: field.key,
          label: field.label,
          type: field.type,
          required: field.required,
          ...(field.placeholder.trim()
            ? {
                placeholder: field.placeholder.trim(),
              }
            : {}),
          ...(field.help_text.trim()
            ? {
                help_text: field.help_text.trim(),
              }
            : {}),
          options,
          ...(visibleWhen
            ? {
                visible_when: visibleWhen,
              }
            : {}),
        };
      }),
    })),
  };
}


function serializeDraftForm(form: DraftForm): AdminFormsSaveRequest["forms"][number] {
  return serializeDraft({
    title: "Preview",
    description: "",
    forms: [form],
  }).forms[0];
}

function buildDraftFingerprint(catalog: DraftCatalog | null): string {
  return JSON.stringify(catalog ? serializeDraft(catalog) : null);
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
            { value: "option_2", label: "Вариант 2" },
          ]
        : [],
    visible_when: {
      field: "",
      equals: "",
      values: [],
    },
  };
}

function createEmptyForm(index: number): DraftForm {
  const key = `new_form_${index}`;
  return {
    key,
    request_kind: key,
    title: "Новая форма",
    description: "",
    playbook_triggers: [],
    fields: [createEmptyField("text", 1)],
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
        label,
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


function isPreviewFieldVisible(field: DraftField, values: PreviewFormValues): boolean {
  const dependencyKey = field.visible_when.field.trim();
  if (!dependencyKey) {
    return true;
  }
  const currentValue = values[dependencyKey];
  if (field.visible_when.equals.trim()) {
    return String(currentValue ?? "").trim() === field.visible_when.equals.trim();
  }
  const allowed = field.visible_when.values.map((item) => item.trim()).filter(Boolean);
  if (allowed.length === 0) {
    return true;
  }
  return allowed.includes(String(currentValue ?? "").trim());
}


function buildPreviewValues(form: DraftForm | null, current: PreviewFormValues = {}): PreviewFormValues {
  if (!form) {
    return {};
  }
  return Object.fromEntries(
    form.fields.map((field) => {
      const existing = current[field.key];
      return [
        field.key,
        typeof existing !== "undefined" ? existing : field.type === "checkbox" ? false : "",
      ];
    })
  );
}

function updateFormInCatalog(
  catalog: DraftCatalog,
  formKey: string,
  updater: (form: DraftForm) => DraftForm
): DraftCatalog {
  return {
    ...catalog,
    forms: catalog.forms.map((form) => (form.key === formKey ? updater(form) : form)),
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
    fields: form.fields.map((field) => (field.key === fieldKey ? updater(field) : field)),
  }));
}


function clearVisibleWhenConfig(field: DraftField): DraftField {
  return {
    ...field,
    visible_when: {
      field: "",
      equals: "",
      values: [],
    },
  };
}


function renameFieldInForm(form: DraftForm, fromKey: string, toKey: string): DraftForm {
  return {
    ...form,
    fields: form.fields.map((field) => {
      if (field.key === fromKey) {
        return {
          ...field,
          key: toKey,
        };
      }
      if (field.visible_when.field !== fromKey) {
        return field;
      }
      return {
        ...field,
        visible_when: {
          ...field.visible_when,
          field: toKey,
        },
      };
    }),
  };
}


function removeFieldFromForm(form: DraftForm, fieldKey: string): DraftForm {
  return {
    ...form,
    fields: form.fields
      .filter((field) => field.key !== fieldKey)
      .map((field) => (field.visible_when.field === fieldKey ? clearVisibleWhenConfig(field) : field)),
  };
}

function fieldTypeRequiresOptions(field: AdminFormsFieldItem | DraftField | null): boolean {
  return field?.type === "select" || field?.type === "radio";
}

function fieldTypeLabel(type: AdminFormsFieldType): string {
  switch (type) {
    case "textarea":
      return "Многострочное";
    case "select":
      return "Список";
    case "radio":
      return "Переключатель";
    case "checkbox":
      return "Флажок";
    default:
      return "Текст";
  }
}

function versionMatchesSearch(item: TicketFormsPackSummary, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    item.version,
    item.title,
    item.description ?? "",
    item.created_by ?? "",
    item.notes ?? "",
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

export function FormsBuilderPanel() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<DraftCatalog | null>(null);
  const [baselineFingerprint, setBaselineFingerprint] = useState<string>("null");
  const [loadedVersion, setLoadedVersion] = useState<string | null>(null);
  const [loadedSourceLabel, setLoadedSourceLabel] = useState("Текущий рабочий каталог");
  const [selectedFormKey, setSelectedFormKey] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [newFieldType, setNewFieldType] = useState<AdminFormsFieldType>("text");
  const [versionSearch, setVersionSearch] = useState("");
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);
  const [previewValues, setPreviewValues] = useState<PreviewFormValues>({});

  const formsQuery = useQuery({
    queryKey: ["admin-forms-builder-current"],
    queryFn: fetchAdminFormsCatalog,
    retry: false,
  });

  const versionsQuery = useQuery({
    queryKey: ["admin-forms-builder-versions"],
    queryFn: fetchTicketFormsPackList,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: saveAdminFormsCatalog,
    onSuccess: async (result) => {
      const nextDraft = hydrateDraft({
        summary: result.summary,
        forms: result.forms,
      });
      setDraft(nextDraft);
      setBaselineFingerprint(buildDraftFingerprint(nextDraft));
      setLoadedVersion(result.summary.version);
      setLoadedSourceLabel(`Опубликованная версия ${result.summary.version}`);
      setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
      setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
      setActionFeedback({
        tone: "success",
        text: result.message,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать каталог форм.",
      });
    },
  });

  const preferredMutation = useMutation({
    mutationFn: setTicketFormsPackPreferred,
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text: `Активная версия каталога обновлена: ${result.preferred.version}.`,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-current"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-forms-builder-versions"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось обновить preferred-версию каталога.",
      });
    },
  });

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!selectedForm) {
        throw new Error("Сначала выберите форму для preview.");
      }
      return previewAdminFormRoute({
        form: serializeDraftForm(selectedForm),
        form_payload: previewValues,
      });
    },
  });

  useEffect(() => {
    if (!formsQuery.data || draft) {
      return;
    }
    const nextDraft = hydrateDraft(formsQuery.data);
    setDraft(nextDraft);
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setLoadedVersion(formsQuery.data.summary.version);
    setLoadedSourceLabel(`Текущая активная версия ${formsQuery.data.summary.version}`);
    setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
    setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
  }, [draft, formsQuery.data]);

  useEffect(() => {
    if (!draft?.forms.length) {
      setSelectedFormKey(null);
      return;
    }

    if (!selectedFormKey || !draft.forms.some((form) => form.key === selectedFormKey)) {
      setSelectedFormKey(draft.forms[0].key);
    }
  }, [draft, selectedFormKey]);

  const selectedForm =
    draft?.forms.find((form) => form.key === selectedFormKey) ?? draft?.forms[0] ?? null;

  useEffect(() => {
    if (!selectedForm?.fields.length) {
      setSelectedFieldKey(null);
      return;
    }

    if (!selectedFieldKey || !selectedForm.fields.some((field) => field.key === selectedFieldKey)) {
      setSelectedFieldKey(selectedForm.fields[0].key);
    }
  }, [selectedFieldKey, selectedForm]);

  const selectedField =
    selectedForm?.fields.find((field) => field.key === selectedFieldKey) ??
    selectedForm?.fields[0] ??
    null;

  useEffect(() => {
    setPreviewValues((current) => buildPreviewValues(selectedForm, current));
    previewMutation.reset();
  }, [selectedForm]);

  const hasUnsavedChanges = buildDraftFingerprint(draft) !== baselineFingerprint;
  const routePreview: AdminFormsRoutePreviewResult | undefined = previewMutation.data;
  const playbookTriggerReadiness = getPlaybookTriggerReadiness(selectedForm?.playbook_triggers[0]);

  const visibleVersions = useMemo(
    () => (versionsQuery.data?.packs ?? []).filter((item) => versionMatchesSearch(item, versionSearch)),
    [versionSearch, versionsQuery.data?.packs]
  );

  function ensureCanSwitch(): boolean {
    if (!hasUnsavedChanges) {
      return true;
    }
    return window.confirm(
      "В редакторе есть несохранённые изменения. Переключить версию и потерять локальный черновик?"
    );
  }

  async function loadCurrentCatalog() {
    if (!formsQuery.data || !ensureCanSwitch()) {
      return;
    }
    const nextDraft = hydrateDraft(formsQuery.data);
    setDraft(nextDraft);
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setLoadedVersion(formsQuery.data.summary.version);
    setLoadedSourceLabel(`Текущая активная версия ${formsQuery.data.summary.version}`);
    setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
    setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
    setActionFeedback(null);
  }

  async function loadVersion(version: string) {
    if (!ensureCanSwitch()) {
      return;
    }
    try {
      const payload = await queryClient.fetchQuery({
        queryKey: ["admin-forms-builder-version", version],
        queryFn: () => fetchTicketFormsPackVersion(version),
      });
      const nextDraft = hydrateDraftFromPack(payload.pack);
      setDraft(nextDraft);
      setBaselineFingerprint(buildDraftFingerprint(nextDraft));
      setLoadedVersion(version);
      setLoadedSourceLabel(`Черновик из версии ${version}`);
      setSelectedFormKey(nextDraft.forms[0]?.key ?? null);
      setSelectedFieldKey(nextDraft.forms[0]?.fields[0]?.key ?? null);
      setActionFeedback({
        tone: "success",
        text: `Версия ${version} загружена в редактор.`,
      });
    } catch (error) {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось загрузить выбранную версию каталога.",
      });
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
            Forms Builder
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
            Конструктор форм заявок
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-500 md:text-base">
            Рабочий каталог intake-форм, version registry и публикация preferred-версии теперь
            живут в одном интерфейсе без legacy iframe.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Активная версия</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {formsQuery.data?.summary.version ?? "—"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Предпочтительная версия каталога, которая сейчас идёт в `/help`.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Версий в реестре</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {versionsQuery.data?.packs.length ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Можно открыть старую версию в редакторе или сделать её preferred.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Форм в каталоге</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {draft?.forms.length ?? formsQuery.data?.summary.forms_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Полей: {draft?.forms.reduce((sum, form) => sum + form.fields.length, 0) ?? formsQuery.data?.summary.fields_count ?? 0}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Черновик</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {hasUnsavedChanges ? "Есть" : "Синхронен"}
          </p>
          <p className="mt-2 text-sm text-slate-500">{loadedSourceLabel}</p>
        </div>
      </div>

      {actionFeedback ? (
        <div
          className={cn(
            "rounded-[1.1rem] border px-4 py-3 text-sm shadow-soft",
            actionFeedback.tone === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          )}
        >
          {actionFeedback.text}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <Card className="xl:sticky xl:top-[9.5rem] xl:self-start">
          <CardHeader className="gap-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>Версии и публикация</CardTitle>
                <CardDescription>
                  Реальный реестр form-pack версий, preferred-переключение и быстрый возврат к текущей конфигурации.
                </CardDescription>
              </div>
              <Button
                leadingIcon={<RefreshCcw className="h-4 w-4" />}
                onClick={() => {
                  void Promise.all([formsQuery.refetch(), versionsQuery.refetch()]);
                }}
                size="sm"
                variant="outline"
              >
                Обновить
              </Button>
            </div>

            <div className="grid gap-2">
              <Button
                leadingIcon={<ClipboardList className="h-4 w-4" />}
                onClick={() => {
                  void loadCurrentCatalog();
                }}
                size="sm"
                variant="outline"
              >
                Загрузить текущую
              </Button>
              <Button
                disabled={!draft || saveMutation.isPending}
                leadingIcon={<Save className="h-4 w-4" />}
                onClick={() => {
                  if (!draft) {
                    return;
                  }
                  setActionFeedback(null);
                  saveMutation.mutate(serializeDraft(draft));
                }}
              >
                {saveMutation.isPending ? "Публикуем..." : "Опубликовать новую версию"}
              </Button>
            </div>

            <SearchField
              onChange={(event) => setVersionSearch(event.target.value)}
              placeholder="Версия, автор, заметка"
              value={versionSearch}
            />
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
              <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Preferred</p>
              <p className="mt-2 text-lg font-semibold text-slate-950">
                {versionsQuery.data?.preferred?.version ?? formsQuery.data?.summary.version ?? "—"}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                Последняя публикация: {formatDateTime(formsQuery.data?.summary.last_published_at)}
              </p>
            </div>

            <div className="max-h-[calc(100vh-24rem)] space-y-3 overflow-y-auto pr-1">
              {versionsQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Загружаем версии каталога...
                </div>
              ) : null}

              {versionsQuery.isError ? (
                <div className="rounded-[1.1rem] border border-dashed border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
                  {versionsQuery.error instanceof Error
                    ? versionsQuery.error.message
                    : "Не удалось загрузить версии каталога."}
                </div>
              ) : null}

              {visibleVersions.map((item) => {
                const isLoaded = loadedVersion === item.version;
                const isPreferred = versionsQuery.data?.preferred?.version === item.version;

                return (
                  <div
                    key={item.version}
                    className={cn(
                      "rounded-[1.15rem] border px-4 py-4",
                      isLoaded ? "border-brand-200 bg-brand-50" : "border-border bg-white"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-slate-950">{item.version}</p>
                          {isPreferred ? <Badge tone="success">preferred</Badge> : null}
                          {item.is_preferred ? <Badge tone="brand">current</Badge> : null}
                        </div>
                        <p className="mt-2 text-sm text-slate-600">{item.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.created_by ?? "builtin_default"} • {formatDateTime(item.created_at)}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">
                          Форм: {item.forms_count} • Полей: {item.fields_count} • Обязательных: {item.required_fields_count}
                        </p>
                      </div>
                      <FileClock className="h-4 w-4 shrink-0 text-slate-300" />
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        leadingIcon={<FilePenLine className="h-4 w-4" />}
                        onClick={() => {
                          void loadVersion(item.version);
                        }}
                        size="sm"
                        variant="outline"
                      >
                        В редактор
                      </Button>
                      <Button
                        disabled={isPreferred || preferredMutation.isPending}
                        leadingIcon={<Star className="h-4 w-4" />}
                        onClick={() => preferredMutation.mutate(item.version)}
                        size="sm"
                      >
                        {`Сделать preferred для ${item.version}`}
                      </Button>
                    </div>
                  </div>
                );
              })}

              {!versionsQuery.isLoading && !versionsQuery.isError && visibleVersions.length === 0 ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Под текущий фильтр версии каталога не найдены.
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Редактор каталога</CardTitle>
                <CardDescription>
                  Все формы, поля и публикация работают на реальном pack-registry без legacy iframe.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={hasUnsavedChanges ? "warning" : "success"}>
                  {hasUnsavedChanges ? "Есть несохранённые изменения" : "Черновик синхронизирован"}
                </Badge>
                <Button
                  disabled={!draft || saveMutation.isPending}
                  leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                  onClick={() => {
                    if (!draft) {
                      return;
                    }
                    setActionFeedback(null);
                    saveMutation.mutate(serializeDraft(draft));
                  }}
                  size="sm"
                >
                  {saveMutation.isPending ? "Публикуем..." : "Сохранить изменения"}
                </Button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            {!draft ? (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-10 text-center text-sm text-slate-500">
                Загружаем рабочий каталог форм...
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Название каталога</span>
                    <input
                      className="field-base h-11 w-full px-4 text-sm"
                      onChange={(event) => {
                        const value = event.currentTarget.value;
                        setActionFeedback(null);
                        setDraft((current) => (current ? { ...current, title: value } : current));
                      }}
                      value={draft.title}
                    />
                  </label>

                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Источник черновика</p>
                    <p className="mt-2 text-base font-semibold text-slate-950">{loadedSourceLabel}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      После публикации сервер выпустит новую версию и сделает её активной.
                    </p>
                  </div>
                </div>

                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Описание каталога</span>
                  <textarea
                    className="field-base min-h-[110px] w-full resize-y px-4 py-4 text-sm"
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setActionFeedback(null);
                      setDraft((current) => (current ? { ...current, description: value } : current));
                    }}
                    value={draft.description}
                  />
                </label>

                <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Формы каталога</p>
                        <p className="text-xs text-slate-500">Выберите форму или добавьте новую.</p>
                      </div>
                      <Button
                        leadingIcon={<Plus className="h-4 w-4" />}
                        onClick={() => {
                          setActionFeedback(null);
                          setDraft((current) => {
                            if (!current) {
                              return current;
                            }
                            const nextForm = createEmptyForm(nextFormIndex(current.forms));
                            setSelectedFormKey(nextForm.key);
                            setSelectedFieldKey(nextForm.fields[0]?.key ?? null);
                            return {
                              ...current,
                              forms: [...current.forms, nextForm],
                            };
                          });
                        }}
                        size="sm"
                      >
                        Новая форма
                      </Button>
                    </div>

                    <div className="max-h-[calc(100vh-27rem)] space-y-3 overflow-y-auto pr-1">
                      {draft.forms.map((form) => (
                        <button
                          key={form.key}
                          className={cn(
                            "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                            selectedForm?.key === form.key
                              ? "border-brand-200 bg-brand-50"
                              : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                          )}
                          onClick={() => {
                            setSelectedFormKey(form.key);
                            setSelectedFieldKey(form.fields[0]?.key ?? null);
                            setActionFeedback(null);
                          }}
                          type="button"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-semibold text-slate-950">{form.title || form.key}</p>
                              <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
                                {form.request_kind}
                              </p>
                            </div>
                            <Badge tone="neutral">{form.fields.length} полей</Badge>
                          </div>
                          <p className="mt-3 text-sm text-slate-500 line-clamp-2">
                            {form.description || "Описание формы пока не заполнено."}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-5">
                    {selectedForm ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">Параметры формы</p>
                            <p className="text-xs text-slate-500">
                              Ключ, request_kind и состав полей сохраняются в следующую версию каталога.
                            </p>
                          </div>
                          <Button
                            disabled={draft.forms.length <= 1}
                            leadingIcon={<Trash2 className="h-4 w-4" />}
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
                                  forms: nextForms,
                                };
                              });
                            }}
                            size="sm"
                            variant="outline"
                          >
                            Удалить форму
                          </Button>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Название формы</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        title: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.title}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Ключ формы</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
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
                                            request_kind:
                                              form.request_kind === selectedForm.key ? value : form.request_kind,
                                          }
                                        : form
                                    ),
                                  };
                                });
                                setSelectedFormKey(value);
                              }}
                              value={selectedForm.key}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>request_kind</span>
                            <input
                              className="field-base h-11 w-full px-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        request_kind: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.request_kind}
                            />
                          </label>
                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Описание формы</span>
                            <textarea
                              className="field-base min-h-[88px] w-full resize-y px-4 py-4 text-sm"
                              onChange={(event) => {
                                const value = event.currentTarget.value;
                                setDraft((current) =>
                                  current
                                    ? updateFormInCatalog(current, selectedForm.key, (form) => ({
                                        ...form,
                                        description: value,
                                      }))
                                    : current
                                );
                              }}
                              value={selectedForm.description}
                            />
                          </label>
                        </div>

                        <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-4">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Плейбук при создании тикета</p>
                              <p className="mt-1 text-xs text-slate-500">
                                Форма может запускать диагностический сценарий и прикладывать пакет фактов к тикету.
                              </p>
                            </div>
                            <div className="flex flex-col items-start gap-2 sm:items-end">
                              <Badge tone={playbookTriggerReadiness.tone}>{playbookTriggerReadiness.label}</Badge>
                              <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
                                <input
                                  checked={Boolean(selectedForm.playbook_triggers[0]?.enabled)}
                                  onChange={(event) => {
                                    const checked = event.currentTarget.checked;
                                    setDraft((current) =>
                                      current
                                        ? updateFormInCatalog(current, selectedForm.key, (form) => {
                                            const currentTrigger = form.playbook_triggers[0] ?? {
                                              event: "ticket_created" as const,
                                              playbook_key: "",
                                              module_kind: "diagnostic" as const,
                                              enabled: false,
                                            };
                                            return {
                                              ...form,
                                              playbook_triggers: [
                                                {
                                                  ...currentTrigger,
                                                  enabled: checked,
                                                },
                                              ],
                                            };
                                          })
                                        : current
                                    );
                                  }}
                                  type="checkbox"
                                />
                                Включить
                              </label>
                            </div>
                          </div>
                          <div className="mt-4 rounded-[0.9rem] border border-border bg-white px-3 py-3">
                            <p className="text-sm font-medium text-slate-900">{playbookTriggerReadiness.detail}</p>
                            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                              <span className="rounded-pill bg-slate-100 px-3 py-1">ticket_created</span>
                              <span className="rounded-pill bg-slate-100 px-3 py-1">diagnostic</span>
                              {selectedForm.playbook_triggers[0]?.playbook_key ? (
                                <span className="rounded-pill bg-brand-50 px-3 py-1 text-brand-800">
                                  {selectedForm.playbook_triggers[0]?.playbook_key}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <div className="mt-4 rounded-[0.9rem] border border-border bg-white px-3 py-3">
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Цепочка запуска</p>
                            <div className="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-3">
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Форма</p>
                                <p className="mt-1 text-xs text-slate-500">{selectedForm.title || selectedForm.key}</p>
                              </div>
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Роутинг</p>
                                <p className="mt-1 text-xs text-slate-500">request_kind: {selectedForm.request_kind || "не указан"}</p>
                              </div>
                              <div className="rounded-[0.8rem] bg-surface-subtle px-3 py-3">
                                <p className="font-semibold text-slate-950">Плейбук</p>
                                <p className="mt-1 text-xs text-slate-500">
                                  {selectedForm.playbook_triggers[0]?.playbook_key || "запуск не настроен"}
                                </p>
                              </div>
                            </div>
                          </div>
                          <div className="mt-4 grid gap-4 md:grid-cols-2">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Ключ плейбука</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => {
                                  const value = event.currentTarget.value;
                                  setDraft((current) =>
                                    current
                                      ? updateFormInCatalog(current, selectedForm.key, (form) => {
                                          const currentTrigger = form.playbook_triggers[0] ?? {
                                            event: "ticket_created" as const,
                                            playbook_key: "",
                                            module_kind: "diagnostic" as const,
                                            enabled: true,
                                          };
                                          return {
                                            ...form,
                                            playbook_triggers: [
                                              {
                                                ...currentTrigger,
                                                event: "ticket_created",
                                                module_kind: "diagnostic",
                                                playbook_key: value,
                                              },
                                            ],
                                          };
                                        })
                                      : current
                                  );
                                }}
                                placeholder="site_not_opening"
                                value={selectedForm.playbook_triggers[0]?.playbook_key ?? ""}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Класс сценария</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                disabled
                                value="diagnostic"
                              />
                            </label>
                          </div>
                        </div>

                        <div className="space-y-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Поля формы</p>
                              <p className="text-xs text-slate-500">
                                Редактор полей полностью живой: типы, options и visible_when уйдут в новую версию.
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Select
                                className="min-w-[160px]"
                                onChange={(event) => setNewFieldType(event.target.value as AdminFormsFieldType)}
                                value={newFieldType}
                              >
                                {formsQuery.data?.capabilities.field_type_options.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </Select>
                              <Button
                                leadingIcon={<Plus className="h-4 w-4" />}
                                onClick={() => {
                                  setDraft((current) => {
                                    if (!current) {
                                      return current;
                                    }
                                    const field = createEmptyField(
                                      newFieldType,
                                      nextFieldIndex(selectedForm.fields)
                                    );
                                    setSelectedFieldKey(field.key);
                                    return updateFormInCatalog(current, selectedForm.key, (form) => ({
                                      ...form,
                                      fields: [...form.fields, field],
                                    }));
                                  });
                                }}
                                size="sm"
                              >
                                Поле
                              </Button>
                            </div>
                          </div>

                          <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
                            <div className="max-h-[calc(100vh-32rem)] space-y-3 overflow-y-auto pr-1">
                              {selectedForm.fields.map((field) => (
                                <button
                                  key={field.key}
                                  className={cn(
                                    "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                                    selectedField?.key === field.key
                                      ? "border-brand-200 bg-brand-50"
                                      : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                                  )}
                                  onClick={() => setSelectedFieldKey(field.key)}
                                  type="button"
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <p className="font-medium text-slate-900">{field.label || field.key}</p>
                                      <p className="mt-1 text-xs text-slate-500">{field.key}</p>
                                    </div>
                                    <Badge tone="neutral">{fieldTypeLabel(field.type)}</Badge>
                                  </div>
                                  <p className="mt-3 text-xs text-slate-500">
                                    {field.required ? "Обязательное поле" : "Необязательное поле"}
                                  </p>
                                </button>
                              ))}
                            </div>

                            <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                              {selectedField ? (
                                <div className="space-y-4">
                                  <div className="flex items-center justify-between gap-3">
                                    <div>
                                      <p className="font-semibold text-slate-900">Параметры поля</p>
                                      <p className="text-xs text-slate-500">{selectedField.key}</p>
                                    </div>
                                    <Button
                                      disabled={selectedForm.fields.length <= 1}
                                      leadingIcon={<Trash2 className="h-4 w-4" />}
                                     onClick={() => {
                                        setDraft((current) => {
                                          if (!current) {
                                            return current;
                                          }
                                          const nextForm = removeFieldFromForm(selectedForm, selectedField.key);
                                          const remainingFields = nextForm.fields;
                                          setSelectedFieldKey(remainingFields[0]?.key ?? null);
                                          return updateFormInCatalog(current, selectedForm.key, () => nextForm);
                                        });
                                      }}
                                      size="sm"
                                      variant="outline"
                                    >
                                      Удалить
                                    </Button>
                                  </div>

                                  <div className="grid gap-4 md:grid-cols-2">
                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Название поля</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    label: value,
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.label}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Ключ поля</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFormInCatalog(current, selectedForm.key, (form) =>
                                                  renameFieldInForm(form, selectedField.key, value)
                                                )
                                              : current
                                          );
                                          setSelectedFieldKey(value);
                                        }}
                                        value={selectedField.key}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Тип поля</span>
                                      <Select
                                        onChange={(event) => {
                                          const value = event.target.value as AdminFormsFieldType;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    type: value,
                                                    options:
                                                      value === "select" || value === "radio"
                                                        ? field.options.length
                                                          ? field.options
                                                          : [
                                                              { value: "option_1", label: "Вариант 1" },
                                                              { value: "option_2", label: "Вариант 2" },
                                                            ]
                                                        : [],
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.type}
                                      >
                                        {formsQuery.data?.capabilities.field_type_options.map((option) => (
                                          <option key={option.value} value={option.value}>
                                            {option.label}
                                          </option>
                                        ))}
                                      </Select>
                                    </label>

                                    <label className="flex h-11 items-center gap-3 rounded-pill border border-border bg-white px-4">
                                      <input
                                        checked={selectedField.required}
                                        onChange={(event) => {
                                          const checked = event.currentTarget.checked;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    required: checked,
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        type="checkbox"
                                      />
                                      <span className="text-sm font-medium text-slate-700">Поле обязательное</span>
                                    </label>
                                  </div>

                                  <label className="space-y-2 text-sm font-medium text-slate-800">
                                    <span>Placeholder</span>
                                    <input
                                      className="field-base h-11 w-full px-4 text-sm"
                                      onChange={(event) => {
                                        const value = event.currentTarget.value;
                                        setDraft((current) =>
                                          current
                                            ? updateFieldInCatalog(
                                                current,
                                                selectedForm.key,
                                                selectedField.key,
                                                (field) => ({
                                                  ...field,
                                                  placeholder: value,
                                                })
                                              )
                                            : current
                                        );
                                      }}
                                      value={selectedField.placeholder}
                                    />
                                  </label>

                                  <label className="space-y-2 text-sm font-medium text-slate-800">
                                    <span>Help text</span>
                                    <textarea
                                      className="field-base min-h-[90px] w-full resize-y px-4 py-4 text-sm"
                                      onChange={(event) => {
                                        const value = event.currentTarget.value;
                                        setDraft((current) =>
                                          current
                                            ? updateFieldInCatalog(
                                                current,
                                                selectedForm.key,
                                                selectedField.key,
                                                (field) => ({
                                                  ...field,
                                                  help_text: value,
                                                })
                                              )
                                            : current
                                        );
                                      }}
                                      value={selectedField.help_text}
                                    />
                                  </label>

                                  {fieldTypeRequiresOptions(selectedField) ? (
                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>Варианты ответа</span>
                                      <textarea
                                        className="field-base min-h-[120px] w-full resize-y px-4 py-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    options: parseFieldOptions(value),
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        placeholder={"value|label\nprinter|Принтер"}
                                        value={fieldOptionsToText(selectedField)}
                                      />
                                    </label>
                                  ) : null}

                                  <div className="grid gap-4 md:grid-cols-3">
                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>visible_when.field</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    visible_when: {
                                                      ...field.visible_when,
                                                      field: value,
                                                    },
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.visible_when.field}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>visible_when.equals</span>
                                      <input
                                        className="field-base h-11 w-full px-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    visible_when: {
                                                      ...field.visible_when,
                                                      equals: value,
                                                    },
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={selectedField.visible_when.equals}
                                      />
                                    </label>

                                    <label className="space-y-2 text-sm font-medium text-slate-800">
                                      <span>visible_when.values</span>
                                      <textarea
                                        className="field-base min-h-[90px] w-full resize-y px-4 py-4 text-sm"
                                        onChange={(event) => {
                                          const value = event.currentTarget.value;
                                          setDraft((current) =>
                                            current
                                              ? updateFieldInCatalog(
                                                  current,
                                                  selectedForm.key,
                                                  selectedField.key,
                                                  (field) => ({
                                                    ...field,
                                                    visible_when: {
                                                      ...field.visible_when,
                                                      values: parseValueLines(value),
                                                    },
                                                  })
                                                )
                                              : current
                                          );
                                        }}
                                        value={valuesToText(selectedField.visible_when.values)}
                                      />
                                    </label>
                                  </div>
                                </div>
                              ) : (
                                <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-8 text-sm text-slate-500">
                                  Выберите поле слева, чтобы настроить его параметры.
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                        Выберите форму слева или создайте новую форму.
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="xl:sticky xl:top-[9.5rem] xl:self-start">
          <CardHeader>
            <CardTitle>Контекст формы</CardTitle>
            <CardDescription>
              Быстрый контроль над текущим редактором: выбранная форма, поле и состояние публикации.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
              <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Выбрано сейчас</p>
              <p className="mt-2 text-lg font-semibold text-slate-950">
                {selectedForm?.title ?? "Форма не выбрана"}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                {selectedField ? `Поле: ${selectedField.label}` : "Выберите поле для редактирования справа."}
              </p>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Черновик из версии</span>
                <span className="font-medium text-slate-900">{loadedVersion ?? "текущая"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Форм в черновике</span>
                <span className="font-medium text-slate-900">{draft?.forms.length ?? 0}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Всего полей</span>
                <span className="font-medium text-slate-900">
                  {draft?.forms.reduce((sum, form) => sum + form.fields.length, 0) ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Обязательных</span>
                <span className="font-medium text-slate-900">
                  {draft?.forms.reduce(
                    (sum, form) => sum + form.fields.filter((field) => field.required).length,
                    0
                  ) ?? 0}
                </span>
              </div>
            </div>

            <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
              <div className="flex items-center gap-2">
                <FolderClock className="h-4 w-4 text-brand-700" />
                <p className="font-semibold text-slate-900">Последняя публикация</p>
              </div>
              <p className="mt-3 text-sm text-slate-600">
                {formsQuery.data?.summary.last_published_by ?? "builtin_default"}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {formatDateTime(formsQuery.data?.summary.last_published_at)}
              </p>
            </div>

            <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">Предпросмотр маршрута</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Заполните пример значений и проверьте, какая очередь или routing rule сработает для текущей формы.
                  </p>
                </div>
                <Button
                  disabled={!selectedForm || previewMutation.isPending}
                  onClick={() => previewMutation.mutate()}
                  size="sm"
                >
                  {previewMutation.isPending ? "Проверяем..." : "Проверить"}
                </Button>
              </div>

              {selectedForm ? (
                <div className="mt-4 space-y-3">
                  {selectedForm.fields
                    .filter((field) => isPreviewFieldVisible(field, previewValues))
                    .map((field) => {
                      const currentValue = previewValues[field.key];
                      if (field.type === "checkbox") {
                        return (
                          <label
                            key={field.key}
                            className="flex items-center gap-3 rounded-[1rem] border border-border bg-surface-subtle px-4 py-3 text-sm"
                          >
                            <input
                              checked={Boolean(currentValue)}
                              onChange={(event) => {
                                const checked = event.currentTarget.checked;
                                setPreviewValues((current) => ({
                                  ...current,
                                  [field.key]: checked,
                                }));
                              }}
                              type="checkbox"
                            />
                            <span>{field.label}</span>
                          </label>
                        );
                      }
                      if (field.type === "select" || field.type === "radio") {
                        return (
                          <label key={field.key} className="space-y-2 text-sm font-medium text-slate-800">
                            <span>{field.label}</span>
                            <Select
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setPreviewValues((current) => ({
                                  ...current,
                                  [field.key]: nextValue,
                                }));
                              }}
                              value={String(currentValue ?? "")}
                            >
                              <option value="">Не выбрано</option>
                              {field.options.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </Select>
                          </label>
                        );
                      }
                      return (
                        <label key={field.key} className="space-y-2 text-sm font-medium text-slate-800">
                          <span>{field.label}</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) => {
                              const nextValue = event.currentTarget.value;
                              setPreviewValues((current) => ({
                                ...current,
                                [field.key]: nextValue,
                              }));
                            }}
                            placeholder={field.placeholder}
                            value={String(currentValue ?? "")}
                          />
                        </label>
                      );
                    })}
                </div>
              ) : (
                <div className="mt-4 rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
                  Сначала выберите форму в редакторе.
                </div>
              )}

              {previewMutation.isError ? (
                <div className="mt-4 rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
                  {previewMutation.error instanceof Error
                    ? previewMutation.error.message
                    : "Не удалось построить preview маршрута."}
                </div>
              ) : null}

              {routePreview ? (
                <div className="mt-4 space-y-3 rounded-[1rem] bg-surface-subtle px-4 py-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-brand-700">Результат</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">
                      {routePreview.target_queue_name ?? "Очередь не найдена"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {routePreview.fallback_applied
                        ? "Совпадений по правилам не нашлось, сработал fallback."
                        : routePreview.matched_rule
                          ? `Совпало правило #${routePreview.matched_rule.id} с priority ${routePreview.matched_rule.priority_order}.`
                          : "Совпадений по правилам не найдено."}
                    </p>
                  </div>

                  <div className="space-y-2 text-sm text-slate-600">
                    <div className="flex items-center justify-between gap-3">
                      <span>ticket_type</span>
                      <code>{routePreview.ticket_type}</code>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span>request_kind</span>
                      <code>{routePreview.request_kind}</code>
                    </div>
                    {routePreview.matched_rule ? (
                      <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3">
                        <p className="font-medium text-slate-900">Условие правила</p>
                        <p className="mt-2 text-sm font-semibold text-slate-800">
                          {describeRouteCondition(routePreview.matched_rule.condition_json)}
                        </p>
                      </div>
                    ) : null}
                  </div>

                  {routePreview.summary_rows.length > 0 ? (
                    <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3">
                      <p className="font-medium text-slate-900">Нормализованные данные формы</p>
                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        {routePreview.summary_rows.map((row) => (
                          <div key={row.key} className="flex items-center justify-between gap-3">
                            <span>{row.label}</span>
                            <strong className="text-slate-900">{row.value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
              Публикация всегда создаёт новую версию pack и сразу делает её активной. Если нужен откат, загрузите
              прошлую версию слева и либо сделайте её preferred, либо выпустите на её основе новую версию.
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
