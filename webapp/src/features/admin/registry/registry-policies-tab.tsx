import { AlertTriangle, RefreshCcw, RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import {
  fetchAdminRegistryPolicies,
  previewAdminRegistryPolicies,
  resetAdminRegistryPolicies,
  updateAdminRegistryPolicies,
  type AdminRegistryPolicyPayload,
} from "../api";

type PolicyEffective = AdminRegistryPolicyPayload["effective"];

const FIELD_LABELS: Record<string, string> = {
  "registration.require_user_confirmation": "Требовать подтверждение пользователя",
  "registration.require_admin_confirmation": "Ручное одобрение администратором",
  "registration.auto_approve_first_binding": "Автоматически подтверждать первую привязку",
  "registration.allow_shared_devices": "Разрешить совместные устройства",
  "registration.allow_responsible_binding": "Разрешить ответственного",
  "registration.max_primary_devices_per_person": "Максимум основных устройств",
  "registration.stale_after_days": "Считать устаревшей через, дней",
  "registration.department_mode": "Режим подразделения",
  "registration.location_mode": "Режим локации",
  "account_sessions.confirmed_binding_ttl_hours": "TTL подтвержденной привязки, часов",
  "account_sessions.verified_other_account_ttl_hours": "TTL другого аккаунта, часов",
  "account_sessions.registration_pending_ttl_hours": "TTL ожидания регистрации, часов",
  "account_sessions.allow_other_account_login": "Разрешить вход в другой аккаунт",
  "account_sessions.other_account_requires_reason": "Причина для другого аккаунта обязательна",
  "account_sessions.other_account_requires_admin_approval": "Другой аккаунт требует одобрения администратора",
  "account_sessions.allow_other_account_on_shared_or_responsible": "Разрешить для совместных и ответственных привязок",
  "ticket_visibility.owner_can_see_historical_tickets": "Владелец видит исторические тикеты",
  "ticket_visibility.other_account_only_own_session_tickets": "Другой аккаунт видит только свои тикеты",
};

const REGISTRATION_ENTITY_MODE_LABELS: Record<string, string> = {
  allow_pending_request: "Разрешить pending-заявку",
  optional: "Необязательно",
  required_existing: "Только существующие значения",
};

function clonePolicies(value: PolicyEffective): PolicyEffective {
  return JSON.parse(JSON.stringify(value)) as PolicyEffective;
}

function valueAtPath(source: Record<string, Record<string, unknown>>, path: string): unknown {
  const [section, field] = path.split(".");
  return source[section]?.[field];
}

function formatValue(value: unknown): string {
  if (value === null) return "не задано";
  if (value === true) return "включено";
  if (value === false) return "выключено";
  return String(value ?? "");
}

function buildChangedFromDefaults(draft: PolicyEffective, defaults: AdminRegistryPolicyPayload["defaults"]) {
  const changed: AdminRegistryPolicyPayload["changed_from_defaults"] = {};
  for (const path of Object.keys(FIELD_LABELS)) {
    const current = valueAtPath(draft as unknown as Record<string, Record<string, unknown>>, path);
    const defaultValue = valueAtPath(defaults, path);
    if (current !== defaultValue) {
      changed[path] = { default: defaultValue, effective: current };
    }
  }
  return changed;
}

function buildWarnings(draft: PolicyEffective): AdminRegistryPolicyPayload["warnings"] {
  return [];
}

export function RegistryPoliciesTab() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-registry-policies"], queryFn: fetchAdminRegistryPolicies, retry: false });
  const [draft, setDraft] = useState<PolicyEffective | null>(null);
  const [reason, setReason] = useState("");
  const [serverPreview, setServerPreview] = useState<AdminRegistryPolicyPayload | null>(null);

  useEffect(() => {
    if (query.data?.effective) {
      setDraft(clonePolicies(query.data.effective));
      setServerPreview(null);
    }
  }, [query.data]);

  const localPreview = useMemo(() => {
    if (!draft || !query.data) return null;
    return {
      changed_from_defaults: buildChangedFromDefaults(draft, query.data.defaults),
      warnings: buildWarnings(draft),
      requires_restart: false,
      restart_required_fields: [] as string[],
    };
  }, [draft, query.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!draft) return null;
      return updateAdminRegistryPolicies({ policies: draft, reason });
    },
    onSuccess: async () => {
      setReason("");
      setServerPreview(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-registry-policies"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    },
  });

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!draft) return null;
      return previewAdminRegistryPolicies(draft);
    },
    onSuccess: (result) => result && setServerPreview(result),
  });

  const resetMutation = useMutation({
    mutationFn: async () => resetAdminRegistryPolicies(reason),
    onSuccess: async () => {
      setReason("");
      setServerPreview(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-registry-policies"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    },
  });

  if (query.isLoading || !draft || !query.data || !localPreview) {
    return <p className="text-sm text-slate-500">Загружаем политики...</p>;
  }

  const setRegistration = (key: keyof typeof draft.registration, value: boolean | number | string) => {
    setDraft({ ...draft, registration: { ...draft.registration, [key]: value } });
    setServerPreview(null);
  };
  const setRegistrationApprovalMode = (mode: "automatic" | "manual") => {
    setDraft({
      ...draft,
      registration: {
        ...draft.registration,
        require_admin_confirmation: mode === "manual",
        auto_approve_first_binding: mode === "automatic",
      },
    });
    setServerPreview(null);
  };
  const setAccount = (key: keyof typeof draft.account_sessions, value: boolean | number | null) => {
    setDraft({ ...draft, account_sessions: { ...draft.account_sessions, [key]: value } });
    setServerPreview(null);
  };
  const setTicket = (key: keyof typeof draft.ticket_visibility, value: boolean) => {
    setDraft({ ...draft, ticket_visibility: { ...draft.ticket_visibility, [key]: value } });
    setServerPreview(null);
  };

  const warnings = serverPreview?.warnings ?? localPreview.warnings;
  const changed = serverPreview?.changed_from_defaults ?? localPreview.changed_from_defaults;
  const requiresRestart = serverPreview?.requires_restart ?? localPreview.requires_restart;
  const restartFields = serverPreview?.restart_required_fields ?? localPreview.restart_required_fields;
  const validation = query.data.validation;
  const error = saveMutation.error ?? resetMutation.error ?? previewMutation.error;

  return (
    <div className="space-y-4">
      {error ? <p className="text-sm text-rose-600">{error instanceof Error ? error.message : "Не удалось выполнить действие с политиками"}</p> : null}
      {warnings.length ? (
        <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {warnings.map((warning) => (
            <p className="flex gap-2" key={warning.field}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span><strong>{FIELD_LABELS[warning.field] ?? warning.field}:</strong> {warning.message}</span>
            </p>
          ))}
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-3">
        <PolicyCard title="Регистрация">
          <ApprovalModeRow
            defaultRequireAdmin={Boolean(query.data.defaults.registration.require_admin_confirmation)}
            defaultAutoApprove={Boolean(query.data.defaults.registration.auto_approve_first_binding)}
            requireAdmin={draft.registration.require_admin_confirmation}
            autoApprove={draft.registration.auto_approve_first_binding}
            onChange={setRegistrationApprovalMode}
          />
          <CheckRow defaultValue={query.data.defaults.registration.require_user_confirmation} label={FIELD_LABELS["registration.require_user_confirmation"]} value={draft.registration.require_user_confirmation} onChange={(value) => setRegistration("require_user_confirmation", value)} />
          <CheckRow defaultValue={query.data.defaults.registration.allow_shared_devices} label={FIELD_LABELS["registration.allow_shared_devices"]} value={draft.registration.allow_shared_devices} onChange={(value) => setRegistration("allow_shared_devices", value)} />
          <CheckRow defaultValue={query.data.defaults.registration.allow_responsible_binding} label={FIELD_LABELS["registration.allow_responsible_binding"]} value={draft.registration.allow_responsible_binding} onChange={(value) => setRegistration("allow_responsible_binding", value)} />
          <NumberRow defaultValue={query.data.defaults.registration.max_primary_devices_per_person} label={FIELD_LABELS["registration.max_primary_devices_per_person"]} rules={validation["registration.max_primary_devices_per_person"]} value={draft.registration.max_primary_devices_per_person} onChange={(value) => setRegistration("max_primary_devices_per_person", value)} />
          <NumberRow defaultValue={query.data.defaults.registration.stale_after_days} label={FIELD_LABELS["registration.stale_after_days"]} rules={validation["registration.stale_after_days"]} value={draft.registration.stale_after_days} onChange={(value) => setRegistration("stale_after_days", value)} />
          <ModeRow defaultValue={query.data.defaults.registration.department_mode} label={FIELD_LABELS["registration.department_mode"]} rules={validation["registration.department_mode"]} value={draft.registration.department_mode} onChange={(value) => setRegistration("department_mode", value)} />
          <ModeRow defaultValue={query.data.defaults.registration.location_mode} label={FIELD_LABELS["registration.location_mode"]} rules={validation["registration.location_mode"]} value={draft.registration.location_mode} onChange={(value) => setRegistration("location_mode", value)} />
        </PolicyCard>
        <PolicyCard title="Аккаунт-сессии">
          <NullableNumberRow defaultValue={query.data.defaults.account_sessions.confirmed_binding_ttl_hours} label={FIELD_LABELS["account_sessions.confirmed_binding_ttl_hours"]} rules={validation["account_sessions.confirmed_binding_ttl_hours"]} value={draft.account_sessions.confirmed_binding_ttl_hours} onChange={(value) => setAccount("confirmed_binding_ttl_hours", value)} />
          <NumberRow defaultValue={query.data.defaults.account_sessions.verified_other_account_ttl_hours} label={FIELD_LABELS["account_sessions.verified_other_account_ttl_hours"]} rules={validation["account_sessions.verified_other_account_ttl_hours"]} value={draft.account_sessions.verified_other_account_ttl_hours} onChange={(value) => setAccount("verified_other_account_ttl_hours", value)} />
          <NumberRow defaultValue={query.data.defaults.account_sessions.registration_pending_ttl_hours} label={FIELD_LABELS["account_sessions.registration_pending_ttl_hours"]} rules={validation["account_sessions.registration_pending_ttl_hours"]} value={draft.account_sessions.registration_pending_ttl_hours} onChange={(value) => setAccount("registration_pending_ttl_hours", value)} />
          <CheckRow defaultValue={query.data.defaults.account_sessions.allow_other_account_login} label={FIELD_LABELS["account_sessions.allow_other_account_login"]} value={draft.account_sessions.allow_other_account_login} onChange={(value) => setAccount("allow_other_account_login", value)} />
          <CheckRow defaultValue={query.data.defaults.account_sessions.other_account_requires_reason} label={FIELD_LABELS["account_sessions.other_account_requires_reason"]} value={draft.account_sessions.other_account_requires_reason} onChange={(value) => setAccount("other_account_requires_reason", value)} />
          <CheckRow defaultValue={query.data.defaults.account_sessions.other_account_requires_admin_approval} label={FIELD_LABELS["account_sessions.other_account_requires_admin_approval"]} value={draft.account_sessions.other_account_requires_admin_approval} onChange={(value) => setAccount("other_account_requires_admin_approval", value)} />
          <CheckRow defaultValue={query.data.defaults.account_sessions.allow_other_account_on_shared_or_responsible} label={FIELD_LABELS["account_sessions.allow_other_account_on_shared_or_responsible"]} value={draft.account_sessions.allow_other_account_on_shared_or_responsible} onChange={(value) => setAccount("allow_other_account_on_shared_or_responsible", value)} />
        </PolicyCard>
        <PolicyCard title="Видимость тикетов">
          <CheckRow defaultValue={query.data.defaults.ticket_visibility.owner_can_see_historical_tickets} label={FIELD_LABELS["ticket_visibility.owner_can_see_historical_tickets"]} value={draft.ticket_visibility.owner_can_see_historical_tickets} onChange={(value) => setTicket("owner_can_see_historical_tickets", value)} />
          <CheckRow defaultValue={query.data.defaults.ticket_visibility.other_account_only_own_session_tickets} label={FIELD_LABELS["ticket_visibility.other_account_only_own_session_tickets"]} value={draft.ticket_visibility.other_account_only_own_session_tickets} onChange={(value) => setTicket("other_account_only_own_session_tickets", value)} />
        </PolicyCard>
      </div>
      <Card>
        <CardHeader><CardTitle>Предпросмотр итоговых политик</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={requiresRestart ? "warning" : "success"}>{requiresRestart ? "Нужен перезапуск" : "Перезапуск не нужен"}</Badge>
            {serverPreview?.dry_run ? <Badge tone="neutral">Серверная проверка</Badge> : <Badge tone="neutral">Локальный расчет</Badge>}
            {restartFields.length ? <span className="text-slate-600">{restartFields.join(", ")}</span> : null}
          </div>
          {Object.keys(changed).length ? (
            <div className="grid gap-2 md:grid-cols-2">
              {Object.entries(changed).map(([path, change]) => (
                <div className="rounded-md border border-border px-3 py-2 text-sm" key={path}>
                  <p className="font-semibold text-slate-900">{FIELD_LABELS[path] ?? path}</p>
                  <p className="mt-1 text-slate-600">по умолчанию: {formatValue(change.default)}</p>
                  <p className="text-slate-600">текущее: {formatValue(change.effective)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Текущий черновик совпадает со значениями по умолчанию.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <Input placeholder="Причина изменения политики" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => previewMutation.mutate()} title="Проверить черновик политик на сервере без сохранения" variant="outline">Предпросмотр</Button>
            <Button leadingIcon={<RotateCcw className="h-4 w-4" />} onClick={() => query.data && setDraft(clonePolicies(query.data.effective))} variant="outline">Отменить</Button>
            <Button disabled={!reason.trim() || resetMutation.isPending} leadingIcon={<RotateCcw className="h-4 w-4" />} onClick={() => resetMutation.mutate()} title="Сбросить политики к значениям по умолчанию; нужна причина" variant="outline">По умолчанию</Button>
            <Button aria-label="save-registry-policies" disabled={!reason.trim() || saveMutation.isPending} leadingIcon={<Save className="h-4 w-4" />} onClick={() => saveMutation.mutate()}>Сохранить</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PolicyCard({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function DefaultHint({ value }: { value: unknown }) {
  return <span className="text-xs font-normal text-slate-500">по умолчанию: {formatValue(value)}</span>;
}

function ApprovalModeRow({
  autoApprove,
  defaultAutoApprove,
  defaultRequireAdmin,
  onChange,
  requireAdmin,
}: {
  autoApprove: boolean;
  defaultAutoApprove: boolean;
  defaultRequireAdmin: boolean;
  onChange: (mode: "automatic" | "manual") => void;
  requireAdmin: boolean;
}) {
  const mode = !requireAdmin && autoApprove ? "automatic" : "manual";
  const defaultMode = !defaultRequireAdmin && defaultAutoApprove ? "автоматически" : "ручное одобрение";
  return (
    <div className="rounded-md border border-border px-3 py-2 text-sm">
      <div className="flex flex-col gap-2">
        <div>
          <p className="font-semibold text-slate-900">Подтверждение привязки устройства</p>
          <p className="text-xs text-slate-500">по умолчанию: {defaultMode}</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            aria-label="registration-approval-automatic"
            className={`rounded-md border px-3 py-2 font-semibold transition-colors ${mode === "automatic" ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-white text-slate-700"}`}
            onClick={() => onChange("automatic")}
            type="button"
          >
            Автоматически
          </button>
          <button
            aria-label="registration-approval-manual"
            className={`rounded-md border px-3 py-2 font-semibold transition-colors ${mode === "manual" ? "border-amber-300 bg-amber-50 text-amber-900" : "border-slate-200 bg-white text-slate-700"}`}
            onClick={() => onChange("manual")}
            type="button"
          >
            Ручное одобрение
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Автоматический режим сразу подтверждает первую неконфликтную привязку. Ручной режим оставляет заявку на проверке администратора.
        </p>
      </div>
    </div>
  );
}

function CheckRow({ defaultValue, label, onChange, value, warning }: { defaultValue: unknown; label: string; value: boolean; onChange: (value: boolean) => void; warning?: boolean }) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
      <span className="flex flex-col gap-1">
        <span className="flex items-center gap-2">{label}{warning ? <Badge tone="warning">внимание</Badge> : null}</span>
        <DefaultHint value={defaultValue} />
      </span>
      <input checked={value} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
    </label>
  );
}

function NumberRow({ defaultValue, label, onChange, rules, value }: { defaultValue: unknown; label: string; rules?: { minimum?: number; maximum?: number }; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block text-sm font-medium">
      <span className="flex items-center justify-between gap-2"><span>{label}</span><DefaultHint value={defaultValue} /></span>
      <Input className="mt-2" max={rules?.maximum} min={rules?.minimum ?? 1} onChange={(event) => onChange(Number(event.target.value || rules?.minimum || 1))} type="number" value={value} />
      {rules ? <span className="mt-1 block text-xs font-normal text-slate-500">диапазон: {rules.minimum}...{rules.maximum}</span> : null}
    </label>
  );
}

function NullableNumberRow({ defaultValue, label, onChange, rules, value }: { defaultValue: unknown; label: string; rules?: { minimum?: number; maximum?: number }; value: number | null; onChange: (value: number | null) => void }) {
  return (
    <label className="block text-sm font-medium">
      <span className="flex items-center justify-between gap-2"><span>{label}</span><DefaultHint value={defaultValue} /></span>
      <Input className="mt-2" max={rules?.maximum} min={rules?.minimum} onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))} placeholder="пусто = без срока" type="number" value={value ?? ""} />
      {rules ? <span className="mt-1 block text-xs font-normal text-slate-500">диапазон: {rules.minimum}...{rules.maximum}, можно оставить пустым</span> : null}
    </label>
  );
}

function ModeRow({ defaultValue, label, onChange, rules, value }: { defaultValue: unknown; label: string; rules?: { values?: string[] }; value: string; onChange: (value: string) => void }) {
  const values = rules?.values?.length ? rules.values : ["allow_pending_request", "optional", "required_existing"];
  return (
    <label className="block text-sm font-medium">
      <span className="flex items-center justify-between gap-2"><span>{label}</span><DefaultHint value={defaultValue} /></span>
      <select className="mt-2 h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-slate-900" onChange={(event) => onChange(event.target.value)} value={value}>
        {values.map((mode) => (
          <option key={mode} value={mode}>{REGISTRATION_ENTITY_MODE_LABELS[mode] ?? mode}</option>
        ))}
      </select>
      <span className="mt-1 block text-xs font-normal text-slate-500">Режим «только существующие значения» запрещает свободный текст и принимает только записи справочника.</span>
    </label>
  );
}
