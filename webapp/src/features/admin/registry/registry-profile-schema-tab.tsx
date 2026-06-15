import { AlertTriangle, Plus, RefreshCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import {
  fetchAdminRegistryProfileSchema,
  previewAdminRegistryProfileSchema,
  saveAdminRegistryProfileSchema,
  type AdminRegistryProfileSchema,
  type AdminRegistryProfileSchemaField,
  type AdminRegistryProfileSchemaPayload,
  type AdminRegistryProfileSchemaUpdatePayload,
} from "../api";

const CUSTOM_STORAGE_PREFIX = "registry_people.metadata_json.profile_custom_fields.";

const FIELD_TYPE_LABELS: Record<string, string> = {
  checkbox: "Флажок",
  date: "Дата",
  email: "Email",
  number: "Число",
  phone: "Телефон",
  select: "Список",
  text: "Текст",
  textarea: "Многострочный текст",
  url: "Ссылка",
};

const CUSTOM_TYPE_OPTIONS = ["text", "textarea", "select", "phone", "email", "url", "number", "date", "checkbox"];

type CustomDraft = {
  key: string;
  label: string;
  type: string;
  help_text: string;
  required: boolean;
};

const EMPTY_CUSTOM_DRAFT: CustomDraft = {
  key: "",
  label: "",
  type: "text",
  help_text: "",
  required: false,
};

function cloneSchema(schema: AdminRegistryProfileSchema): AdminRegistryProfileSchema {
  return JSON.parse(JSON.stringify(schema)) as AdminRegistryProfileSchema;
}

function storageTargetFor(key: string): string {
  return `${CUSTOM_STORAGE_PREFIX}${key}`;
}

function normalizeCustomKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/^_+/, "").slice(0, 64);
}

function toUpdatePayload(schema: AdminRegistryProfileSchema, reason: string): AdminRegistryProfileSchemaUpdatePayload {
  const fieldOverrides: AdminRegistryProfileSchemaUpdatePayload["field_overrides"] = {};
  for (const field of schema.fields) {
    if (field.custom) {
      continue;
    }
    fieldOverrides[field.key] = {
      visible: field.visible !== false,
      required: field.required === true,
      help_text: field.help_text ?? null,
      validation: field.validation ?? {},
    };
  }
  return {
    field_overrides: fieldOverrides,
    custom_fields: (schema.fields ?? [])
      .filter((field) => field.custom)
      .map((field) => ({
        ...field,
        key: normalizeCustomKey(field.key),
        storage_target: storageTargetFor(normalizeCustomKey(field.key)),
        target_kind: "registry_person_metadata",
        custom: true,
        system: false,
      })),
    reason: reason.trim(),
  };
}

export function RegistryProfileSchemaTab() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-registry-profile-schema"], queryFn: fetchAdminRegistryProfileSchema, retry: false });
  const [draft, setDraft] = useState<AdminRegistryProfileSchema | null>(null);
  const [reason, setReason] = useState("");
  const [newCustom, setNewCustom] = useState<CustomDraft>(EMPTY_CUSTOM_DRAFT);
  const [serverPreview, setServerPreview] = useState<AdminRegistryProfileSchemaPayload | null>(null);

  useEffect(() => {
    if (query.data?.schema) {
      setDraft(cloneSchema(query.data.schema));
      setServerPreview(null);
    }
  }, [query.data]);

  const grouped = useMemo(() => {
    const fields = draft?.fields ?? [];
    return {
      system: fields.filter((field) => field.system),
      optional: fields.filter((field) => !field.system && !field.custom),
      custom: fields.filter((field) => field.custom),
    };
  }, [draft?.fields]);

  const updateField = (key: string, patch: Partial<AdminRegistryProfileSchemaField>) => {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        fields: current.fields.map((field) => field.key === key ? { ...field, ...patch } : field),
      };
    });
    setServerPreview(null);
  };

  const removeCustomField = (key: string) => {
    setDraft((current) => current ? { ...current, fields: current.fields.filter((field) => field.key !== key) } : current);
    setServerPreview(null);
  };

  const addCustomField = () => {
    const key = normalizeCustomKey(newCustom.key);
    const label = newCustom.label.trim();
    if (!draft || !key || !label || draft.fields.some((field) => field.key === key)) {
      return;
    }
    const field: AdminRegistryProfileSchemaField = {
      key,
      label,
      type: newCustom.type,
      required: newCustom.required,
      visible: true,
      system: false,
      custom: true,
      editable: true,
      can_delete: true,
      can_hide: true,
      target_kind: "registry_person_metadata",
      storage_target: storageTargetFor(key),
      help_text: newCustom.help_text.trim() || null,
      validation: {},
      options: [],
      audit_behavior: "profile_custom_field_change",
    };
    setDraft({ ...draft, fields: [...draft.fields, field], custom_fields: [...(draft.custom_fields ?? []), field] });
    setNewCustom(EMPTY_CUSTOM_DRAFT);
    setServerPreview(null);
  };

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!draft) return null;
      return previewAdminRegistryProfileSchema(toUpdatePayload(draft, reason));
    },
    onSuccess: (result) => result && setServerPreview(result),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!draft) return null;
      return saveAdminRegistryProfileSchema(toUpdatePayload(draft, reason));
    },
    onSuccess: async (result) => {
      if (result?.schema) {
        setDraft(cloneSchema(result.schema));
      }
      setReason("");
      setServerPreview(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-registry-profile-schema"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    },
  });

  if (query.isLoading || !draft) {
    return <p className="text-sm text-slate-500">Загружаем схему профиля...</p>;
  }

  const error = query.error ?? previewMutation.error ?? saveMutation.error;
  const previewSchema = serverPreview?.schema;
  const requiredFields = previewSchema?.required_fields ?? draft.required_fields ?? [];
  const customKey = normalizeCustomKey(newCustom.key);
  const canAddCustom = Boolean(customKey && newCustom.label.trim() && !draft.fields.some((field) => field.key === customKey));

  return (
    <div className="space-y-4">
      {error ? <p className="text-sm text-rose-600">{error instanceof Error ? error.message : "Не удалось обработать схему профиля"}</p> : null}
      <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
        <p className="font-semibold">Системные поля защищены</p>
        <p className="mt-1">
          ФИО, логин, подразделение, локация, телефон и активные привязки устройств нельзя скрыть или удалить. Пользовательские поля пишутся только в контролируемый блок профиля.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="space-y-4">
          <SchemaSection title="Системные поля" subtitle="Фиксируют идентичность, профиль и привязки устройств. Эти поля доступны только для просмотра в редакторе схемы.">
            {grouped.system.map((field) => (
              <FieldRow field={field} key={field.key} readOnly onChange={(patch) => updateField(field.key, patch)} />
            ))}
          </SchemaSection>

          <SchemaSection title="Настраиваемые поля" subtitle="Можно скрывать, делать обязательными и уточнять подсказку без изменения базовой модели пользователя.">
            {grouped.optional.map((field) => (
              <FieldRow field={field} key={field.key} onChange={(patch) => updateField(field.key, patch)} />
            ))}
          </SchemaSection>

          <SchemaSection title="Пользовательские поля" subtitle="Новые поля создаются только с заранее заданной целью хранения и аудитом изменений профиля.">
            {grouped.custom.length ? (
              grouped.custom.map((field) => (
                <FieldRow field={field} key={field.key} onChange={(patch) => updateField(field.key, patch)} onDelete={() => removeCustomField(field.key)} />
              ))
            ) : (
              <p className="text-sm text-slate-500">Пользовательские поля еще не добавлены.</p>
            )}
          </SchemaSection>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Новое пользовательское поле</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <label className="block text-sm font-medium">
                Ключ поля
                <Input
                  className="mt-1"
                  onChange={(event) => setNewCustom((current) => ({ ...current, key: event.target.value }))}
                  placeholder="cost_center"
                  value={newCustom.key}
                />
                <span className="mt-1 block text-xs font-normal text-slate-500">
                  Хранение: {customKey ? storageTargetFor(customKey) : `${CUSTOM_STORAGE_PREFIX}<key>`}
                </span>
              </label>
              <label className="block text-sm font-medium">
                Название
                <Input
                  className="mt-1"
                  onChange={(event) => setNewCustom((current) => ({ ...current, label: event.target.value }))}
                  placeholder="Центр затрат"
                  value={newCustom.label}
                />
              </label>
              <label className="block text-sm font-medium">
                Тип
                <select
                  className="mt-1 w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
                  onChange={(event) => setNewCustom((current) => ({ ...current, type: event.target.value }))}
                  value={newCustom.type}
                >
                  {CUSTOM_TYPE_OPTIONS.map((type) => <option key={type} value={type}>{FIELD_TYPE_LABELS[type] ?? type}</option>)}
                </select>
              </label>
              <label className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
                <span>Обязательное поле</span>
                <input checked={newCustom.required} onChange={(event) => setNewCustom((current) => ({ ...current, required: event.target.checked }))} type="checkbox" />
              </label>
              <label className="block text-sm font-medium">
                Подсказка
                <textarea
                  className="mt-1 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm font-normal"
                  onChange={(event) => setNewCustom((current) => ({ ...current, help_text: event.target.value }))}
                  placeholder="Где пользователь найдет это значение"
                  value={newCustom.help_text}
                />
              </label>
              <Button disabled={!canAddCustom} leadingIcon={<Plus className="h-4 w-4" />} onClick={addCustomField} type="button" variant="outline">
                Добавить поле
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Предпросмотр</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge tone={serverPreview?.dry_run ? "success" : "neutral"}>
                  {serverPreview?.dry_run ? "Серверная проверка" : "Локальный черновик"}
                </Badge>
                <Badge tone="neutral">Обязательных полей: {requiredFields.length}</Badge>
                <Badge tone="neutral">Пользовательских: {grouped.custom.length}</Badge>
              </div>
              {draft.warnings?.length ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  {draft.warnings.map((warning) => (
                    <p className="flex gap-2" key={warning}>
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{warning}</span>
                    </p>
                  ))}
                </div>
              ) : null}
              <div className="space-y-1 text-sm text-slate-600">
                {requiredFields.map((field) => <p key={field.key}>{field.label}</p>)}
              </div>
              <label className="block text-sm font-medium">
                Причина изменения
                <Input
                  className="mt-1"
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Например: вводим обязательный центр затрат"
                  value={reason}
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => previewMutation.mutate()} type="button" variant="outline">
                  Предпросмотр
                </Button>
                <Button disabled={!reason.trim() || saveMutation.isPending} leadingIcon={<Save className="h-4 w-4" />} onClick={() => saveMutation.mutate()} type="button">
                  Сохранить схему
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SchemaSection({ children, subtitle, title }: { children: ReactNode; subtitle: string; title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-sm font-normal text-slate-500">{subtitle}</p>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function FieldRow({
  field,
  onChange,
  onDelete,
  readOnly,
}: {
  field: AdminRegistryProfileSchemaField;
  onChange: (patch: Partial<AdminRegistryProfileSchemaField>) => void;
  onDelete?: () => void;
  readOnly?: boolean;
}) {
  return (
    <div className="rounded-md border border-border px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-900">{field.label}</p>
            {field.system ? <Badge tone="warning">системное</Badge> : null}
            {field.custom ? <Badge tone="info">пользовательское</Badge> : null}
            {field.required ? <Badge tone="neutral">обязательное</Badge> : null}
          </div>
          <p className="mt-1 break-all text-xs text-slate-500">{field.key} · {FIELD_TYPE_LABELS[field.type] ?? field.type}</p>
          {field.storage_target ? <p className="mt-1 break-all text-xs text-slate-500">Хранение: {field.storage_target}</p> : null}
          {field.system ? <p className="mt-1 text-xs text-amber-700">Нельзя скрыть или удалить</p> : null}
        </div>
        {field.custom && onDelete ? (
          <Button onClick={onDelete} type="button" variant="outline">Удалить</Button>
        ) : null}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
          <span>Показывать в профиле</span>
          <input
            checked={field.visible !== false}
            disabled={readOnly || field.can_hide === false}
            onChange={(event) => onChange({ visible: event.target.checked })}
            type="checkbox"
          />
        </label>
        <label className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
          <span>Обязательное</span>
          <input
            checked={field.required === true}
            disabled={readOnly && field.required === true}
            onChange={(event) => onChange({ required: event.target.checked })}
            type="checkbox"
          />
        </label>
        <label className="block text-sm font-medium md:col-span-2">
          Подсказка
          <Input
            className="mt-1"
            disabled={readOnly && field.system}
            onChange={(event) => onChange({ help_text: event.target.value })}
            placeholder="Не задана"
            value={field.help_text ?? ""}
          />
        </label>
      </div>
    </div>
  );
}
