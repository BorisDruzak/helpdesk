import { RefreshCcw, Save, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ModuleResultRenderer, getPathValue } from "../../components/module-result/module-result-renderer";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Tabs } from "../../components/ui/tabs";
import {
  applyAdminDeviceBindingSuggestion,
  collectAdminDeviceInventory,
  collectAdminDevicePresence,
  fetchAdminDeviceAccountSessions,
  fetchAdminDeviceRegistrationTimeline,
  fetchAdminDeviceInventory,
  ignoreAdminDeviceBindingSuggestion,
  revokeAdminDeviceAccountSession,
  revokeAdminDeviceUserBinding,
  saveAdminDeviceInventoryBinding,
  saveAdminDeviceInventoryRefreshPolicy,
  type AdminBindingSuggestionItem,
  type AdminDeviceInventoryBindingUpdate,
  type AdminDeviceInventoryPayload,
} from "./api";

type DeviceInventoryPanelProps = {
  deviceId: string | null;
  deviceLabel?: string | null;
};

const emptyBinding: AdminDeviceInventoryBindingUpdate = {
  building: null,
  floor: null,
  room: null,
  department: null,
  responsible_user: null,
  responsible_user_login: null,
  inventory_number: null,
  status: null,
  tags: [],
  notes: null,
};

function valueText(value: unknown, empty = "—"): string {
  if (value === undefined || value === null || value === "") {
    return empty;
  }
  if (Array.isArray(value)) {
    return value.join(", ") || empty;
  }
  return String(value);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function percentText(value: unknown): string {
  return typeof value === "number" ? `${Math.round(value)}%` : valueText(value);
}

function uptimeText(seconds: unknown): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) {
    return "—";
  }
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  return days > 0 ? `${days} д ${hours} ч` : `${hours} ч`;
}

function durationText(seconds: unknown): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) {
    return "—";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
}

function suggestionFields(suggestion: Record<string, unknown>): string[] {
  return Object.entries(suggestion)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key]) => key);
}

function worstDiskPercent(result: Record<string, unknown>): string {
  const disks = getPathValue(result, "resources.disks");
  if (!Array.isArray(disks)) {
    return "—";
  }
  const values = disks
    .map((item) => (typeof item === "object" && item !== null ? (item as Record<string, unknown>).used_percent : undefined))
    .filter((value): value is number => typeof value === "number");
  return values.length ? `${Math.round(Math.max(...values))}%` : "—";
}

function schemaSourceLabel(source: string | undefined): string {
  if (source === "server_override") {
    return "server override";
  }
  if (source === "module_default") {
    return "module default";
  }
  return "none";
}

function cleanFormValue(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function staleTone(collectedAt: string | null | undefined): "danger" | "success" | "warning" {
  if (!collectedAt) {
    return "danger";
  }
  const date = new Date(collectedAt);
  if (Number.isNaN(date.getTime())) {
    return "warning";
  }
  const ageMs = Date.now() - date.getTime();
  return ageMs > 7 * 24 * 60 * 60 * 1000 ? "warning" : "success";
}

function staleLabel(collectedAt: string | null | undefined): string {
  if (!collectedAt) {
    return "missing inventory";
  }
  return staleTone(collectedAt) === "warning" ? "stale inventory" : "fresh inventory";
}

function MiniPresence({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-white px-3 py-2">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

export function DeviceInventoryPanel({ deviceId, deviceLabel }: DeviceInventoryPanelProps) {
  const [tab, setTab] = useState("overview");
  const [bindingForm, setBindingForm] = useState<AdminDeviceInventoryBindingUpdate>(emptyBinding);
  const [bindingReason, setBindingReason] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [refreshInterval, setRefreshInterval] = useState("1440");
  const [refreshEnabled, setRefreshEnabled] = useState(false);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["admin-device-inventory", deviceId],
    queryFn: () => fetchAdminDeviceInventory(deviceId!),
    enabled: Boolean(deviceId),
    retry: false,
    refetchInterval: 30_000,
  });
  const registrationTimelineQuery = useQuery({
    queryKey: ["admin-device-registration-timeline", deviceId],
    queryFn: () => fetchAdminDeviceRegistrationTimeline(deviceId!),
    enabled: Boolean(deviceId),
    retry: false,
  });
  const accountSessionsQuery = useQuery({
    queryKey: ["admin-device-account-sessions", deviceId],
    queryFn: () => fetchAdminDeviceAccountSessions(deviceId!),
    enabled: Boolean(deviceId),
    retry: false,
  });

  const collectMutation = useMutation({
    mutationFn: () => collectAdminDeviceInventory(deviceId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const bindingMutation = useMutation({
    mutationFn: () => saveAdminDeviceInventoryBinding(deviceId!, bindingForm, cleanFormValue(bindingReason)),
    onSuccess: () => {
      setBindingReason("");
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () =>
      saveAdminDeviceInventoryRefreshPolicy(deviceId!, {
        enabled: refreshEnabled,
        interval_minutes: Number.parseInt(refreshInterval, 10) || 1440,
        jitter_minutes: 30,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const presenceMutation = useMutation({
    mutationFn: () => collectAdminDevicePresence(deviceId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const applySuggestionMutation = useMutation({
    mutationFn: (suggestion: AdminBindingSuggestionItem) =>
      applyAdminDeviceBindingSuggestion(
        deviceId!,
        suggestion.id,
        suggestionFields(suggestion.suggested_binding),
        "Применено из профиля агента"
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const ignoreSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) => ignoreAdminDeviceBindingSuggestion(deviceId!, suggestionId, "Оставлено без изменений"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  const data: AdminDeviceInventoryPayload | undefined = query.data;
  const latest = data?.latest_snapshot ?? null;
  const result = latest?.result ?? null;
  const effectiveSchema = latest?.effective_presentation_schema ?? latest?.presentation_schema ?? undefined;
  const binding = data?.binding ?? null;
  const refreshPolicy = data?.refresh_policy ?? null;
  const profiles = data?.profiles ?? [];
  const suggestions = data?.binding_suggestions ?? [];
  const pendingSuggestions = suggestions.filter((item) => item.status === "pending");
  const presence = data?.presence ?? null;
  const registrationTimeline = registrationTimelineQuery.data?.items ?? [];
  const accountSessions = accountSessionsQuery.data?.items ?? [];

  const revokeRegistrationMutation = useMutation({
    mutationFn: () => revokeAdminDeviceUserBinding(binding?.source_binding_id ?? "", "revoked from device card"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-device-registration-timeline", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-device-account-sessions", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    },
  });
  const revokeAccountSessionMutation = useMutation({
    mutationFn: (sessionId: string) => revokeAdminDeviceAccountSession(sessionId, "revoked from device card"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-device-account-sessions", deviceId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-device-inventory", deviceId] });
    },
  });

  useEffect(() => {
    setBindingForm({
      building: binding?.building ?? null,
      floor: binding?.floor ?? null,
      room: binding?.room ?? null,
      department: binding?.department ?? null,
      responsible_user: binding?.responsible_user ?? null,
      responsible_user_login: binding?.responsible_user_login ?? null,
      inventory_number: binding?.inventory_number ?? null,
      status: binding?.status ?? null,
      tags: binding?.tags ?? [],
      notes: binding?.notes ?? null,
    });
    setTagsText((binding?.tags ?? []).join(", "));
  }, [binding]);

  useEffect(() => {
    setRefreshEnabled(Boolean(refreshPolicy?.enabled));
    setRefreshInterval(String(refreshPolicy?.interval_minutes ?? 1440));
  }, [refreshPolicy]);

  const updateBinding = (key: keyof AdminDeviceInventoryBindingUpdate, value: string) => {
    setBindingForm((current) => ({ ...current, [key]: cleanFormValue(value) }));
  };

  const updateTags = (value: string) => {
    setTagsText(value);
    setBindingForm((current) => ({
      ...current,
      tags: value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    }));
  };

  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Паспорт устройства</CardTitle>
            <CardDescription>
              {deviceLabel ?? deviceId ?? "Выберите устройство"} · latest inventory.collect snapshot
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {latest ? <Badge tone="info">{schemaSourceLabel(latest.presentation_schema_source)}</Badge> : null}
            {latest ? <Badge tone={staleTone(latest.collected_at)}>{staleLabel(latest.collected_at)}</Badge> : null}
            {refreshPolicy ? (
              <Badge tone={refreshPolicy.enabled ? "success" : "neutral"}>
                {refreshPolicy.enabled ? "refresh enabled" : "refresh disabled"}
              </Badge>
            ) : null}
            <Button
              disabled={!deviceId || collectMutation.isPending}
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => collectMutation.mutate()}
              size="sm"
              variant="outline"
            >
              {collectMutation.isPending ? "Отправляем" : "Обновить инвентарь"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {!deviceId ? (
          <div className="rounded-lg border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
            Выберите устройство, чтобы открыть latest inventory snapshot.
          </div>
        ) : null}
        {query.isLoading ? <p className="text-sm text-slate-500">Загружаем инвентарь...</p> : null}
        {query.isError ? (
          <p className="text-sm text-rose-600">
            {query.error instanceof Error ? query.error.message : "Не удалось загрузить инвентарь устройства."}
          </p>
        ) : null}
        {collectMutation.isSuccess ? <p className="text-sm text-emerald-700">{collectMutation.data.message}</p> : null}
        {collectMutation.isError ? (
          <p className="text-sm text-rose-600">
            {collectMutation.error instanceof Error ? collectMutation.error.message : "Не удалось отправить inventory.collect."}
          </p>
        ) : null}

        {deviceId && !query.isLoading && !latest ? (
          <div className="rounded-lg border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
            Snapshot ещё не собран. Запустите inventory.collect или дождитесь следующего результата агента.
          </div>
        ) : null}

        {latest && result ? (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Host</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{valueText(getPathValue(result, "identity.hostname"))}</p>
                <p className="mt-1 text-sm text-slate-500">{valueText(getPathValue(result, "network.primary_ip"))}</p>
              </div>
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Привязка</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{valueText(binding?.inventory_number, "Без номера")}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {[binding?.building, binding?.room, binding?.department].filter(Boolean).join(" · ") || "Место не задано"}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Collected</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{formatDateTime(latest.collected_at)}</p>
                <p className="mt-1 text-sm text-slate-500">Agent {valueText(getPathValue(result, "agent.version"))}</p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg bg-surface-subtle px-4 py-3">
                <p className="text-sm text-slate-500">CPU</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{percentText(getPathValue(result, "resources.cpu_percent"))}</p>
              </div>
              <div className="rounded-lg bg-surface-subtle px-4 py-3">
                <p className="text-sm text-slate-500">RAM</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{percentText(getPathValue(result, "resources.memory_percent"))}</p>
              </div>
              <div className="rounded-lg bg-surface-subtle px-4 py-3">
                <p className="text-sm text-slate-500">Disk worst</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{worstDiskPercent(result)}</p>
              </div>
              <div className="rounded-lg bg-surface-subtle px-4 py-3">
                <p className="text-sm text-slate-500">Uptime</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{uptimeText(getPathValue(result, "platform.uptime_seconds"))}</p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-sm font-medium text-slate-700">Ответственный</p>
                <p className="mt-1 text-sm text-slate-500">{valueText(binding?.responsible_user)}</p>
              </div>
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-sm font-medium text-slate-700">Расписание</p>
                <p className="mt-1 text-sm text-slate-500">
                  {refreshPolicy?.enabled ? `каждые ${refreshPolicy.interval_minutes} мин` : "отключено"}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-white px-4 py-3">
                <p className="text-sm font-medium text-slate-700">Следующий запуск</p>
                <p className="mt-1 text-sm text-slate-500">{formatDateTime(refreshPolicy?.next_due_at)}</p>
              </div>
            </div>
          </>
        ) : null}

        {deviceId ? (
          <>
            <Tabs
              items={[
                { value: "overview", label: "Обзор" },
                { value: "hardware", label: "Железо" },
                { value: "network", label: "Сеть" },
                { value: "printers", label: "Принтеры" },
                { value: "processes", label: "Процессы" },
                { value: "binding", label: "Привязка" },
                { value: "history", label: "История" },
                { value: "registration", label: "Регистрация" },
                { value: "presence", label: "Присутствие" },
                { value: "raw", label: "Raw" },
              ]}
              onValueChange={setTab}
              value={tab}
            />

            {tab === "raw" && result ? (
              <pre className="max-h-[420px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
                {JSON.stringify(result, null, 2)}
              </pre>
            ) : null}

            {tab === "binding" ? (
              <div className="space-y-4 rounded-lg border border-border bg-white p-4">
                <div className="grid gap-3 md:grid-cols-3">
                  {[
                    ["building", "Здание"],
                    ["floor", "Этаж"],
                    ["room", "Кабинет"],
                    ["department", "Подразделение"],
                    ["responsible_user", "Ответственный"],
                    ["responsible_user_login", "Логин"],
                    ["inventory_number", "Инвентарный номер"],
                    ["status", "Status"],
                  ].map(([key, label]) => (
                    <label key={key} className="space-y-1 text-sm">
                      <span className="font-medium text-slate-700">{label}</span>
                      <Input
                        value={valueText(bindingForm[key as keyof AdminDeviceInventoryBindingUpdate], "")}
                        onChange={(event) => updateBinding(key as keyof AdminDeviceInventoryBindingUpdate, event.target.value)}
                      />
                    </label>
                  ))}                </div>
                <label className="space-y-1 text-sm">
                  <span className="font-medium text-slate-700">Tags</span>
                  <Input
                    value={tagsText}
                    onChange={(event) => updateTags(event.target.value)}
                    placeholder="laptop, shared, spare"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="font-medium text-slate-700">Reason / comment</span>
                  <Input
                    value={bindingReason}
                    onChange={(event) => setBindingReason(event.target.value)}
                    placeholder="move, import, correction"
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="font-medium text-slate-700">Notes</span>
                  <textarea
                    className="field-base min-h-24 w-full px-4 py-3 text-sm text-slate-900"
                    value={valueText(bindingForm.notes, "")}
                    onChange={(event) => updateBinding("notes", event.target.value)}
                  />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    disabled={!deviceId || bindingMutation.isPending}
                    leadingIcon={<Save className="h-4 w-4" />}
                    onClick={() => bindingMutation.mutate()}
                    size="sm"
                  >
                    {bindingMutation.isPending ? "Сохраняем" : "Сохранить привязку"}
                  </Button>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      checked={refreshEnabled}
                      onChange={(event) => setRefreshEnabled(event.target.checked)}
                      type="checkbox"
                    />
                    Периодическое обновление
                  </label>
                  <Input
                    className="w-28"
                    min={15}
                    onChange={(event) => setRefreshInterval(event.target.value)}
                    type="number"
                    value={refreshInterval}
                  />
                  <span className="text-sm text-slate-500">мин</span>
                  <Button
                    disabled={!deviceId || refreshMutation.isPending}
                    onClick={() => refreshMutation.mutate()}
                    size="sm"
                    variant="outline"
                  >
                    {refreshMutation.isPending ? "Сохраняем" : "Сохранить расписание"}
                  </Button>
                </div>
                {bindingMutation.isSuccess ? <p className="text-sm text-emerald-700">Привязка сохранена</p> : null}
                {bindingMutation.isError ? <p className="text-sm text-rose-600">Не удалось сохранить привязку</p> : null}
                {refreshMutation.isSuccess ? <p className="text-sm text-emerald-700">Расписание сохранено</p> : null}
                {refreshMutation.isError ? <p className="text-sm text-rose-600">Не удалось сохранить расписание</p> : null}
              </div>
            ) : null}

            {tab === "registration" ? (
              <div className="grid gap-4 xl:grid-cols-3">
                <div className="rounded-lg border border-border bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-950">Регистрация пользователя</h4>
                  <p className="mt-1 text-sm text-slate-500">Текущий подтвержденный контекст берется из active device_user_binding.</p>
                  <div className="mt-4 grid gap-2 text-sm">
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">Статус</p>
                      <p className="mt-1 font-semibold text-slate-950">{valueText(binding?.registration_status, "Не зарегистрирован")}</p>
                    </div>
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">Пользователь</p>
                      <p className="mt-1 font-semibold text-slate-950">{valueText(binding?.responsible_user, "Нет active binding")}</p>
                    </div>
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">Логин</p>
                      <p className="mt-1 font-semibold text-slate-950">{valueText(binding?.responsible_user_login)}</p>
                    </div>
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">История</p>
                      <p className="mt-1 font-semibold text-slate-950">{registrationTimeline.length} событий</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-950">Активная привязка</h4>
                  <div className="mt-4 grid gap-2 text-sm">
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">ID привязки</p>
                      <p className="mt-1 break-all font-semibold text-slate-950">{valueText(binding?.source_binding_id)}</p>
                    </div>
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">ID пользователя</p>
                      <p className="mt-1 break-all font-semibold text-slate-950">{valueText(binding?.person_id)}</p>
                    </div>
                    <div className="rounded-md bg-surface-subtle px-3 py-2">
                      <p className="text-xs uppercase text-slate-500">Статус</p>
                      <p className="mt-1 font-semibold text-slate-950">{valueText(binding?.registration_status)}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button
                      disabled={!binding?.source_binding_id || revokeRegistrationMutation.isPending}
                      leadingIcon={<Trash2 className="h-4 w-4" />}
                      onClick={() => revokeRegistrationMutation.mutate()}
                      size="sm"
                      variant="outline"
                    >
                      {revokeRegistrationMutation.isPending ? "Отзывается" : "Отозвать регистрацию"}
                    </Button>
                    {revokeRegistrationMutation.isError ? (
                      <span className="text-sm text-rose-600">Не удалось отозвать регистрацию</span>
                    ) : null}
                    {revokeRegistrationMutation.isSuccess ? (
                      <span className="text-sm text-emerald-700">Регистрация отозвана</span>
                    ) : null}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-semibold text-slate-950">Аккаунт-сессии агента</h4>
                      <p className="mt-1 text-sm text-slate-500">
                        Серверные сессии, которыми агент подтверждает текущий аккаунт обращения.
                      </p>
                    </div>
                    <Badge tone={accountSessions.some((item) => item.verification_status === "verified" || item.verification_status === "pending_verification") ? "info" : "neutral"}>
                      {accountSessions.length}
                    </Badge>
                  </div>
                  <div className="mt-4 space-y-3">
                    {accountSessions.length === 0 ? (
                      <p className="text-sm text-slate-500">Сессии аккаунтов пока не создавались.</p>
                    ) : (
                      accountSessions.slice(0, 8).map((session) => (
                        <div className="rounded-lg bg-surface-subtle px-3 py-3 text-sm" key={session.session_id}>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-semibold text-slate-900">
                              {session.display_name || session.full_name || session.login || session.session_id.slice(0, 8)}
                            </span>
                            <Badge tone={session.verification_status === "verified" ? "success" : session.verification_status === "revoked" ? "neutral" : "warning"}>
                              {session.account_mode} / {session.verification_status}
                            </Badge>
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            <div className="rounded-md bg-white px-3 py-2">
                              <p className="text-xs uppercase text-slate-500">Session</p>
                              <p className="mt-1 break-all text-slate-900">{session.session_id}</p>
                            </div>
                            <div className="rounded-md bg-white px-3 py-2">
                              <p className="text-xs uppercase text-slate-500">Login / phone</p>
                              <p className="mt-1 text-slate-900">{[session.login, session.phone].filter(Boolean).join(" · ") || "—"}</p>
                            </div>
                            <div className="rounded-md bg-white px-3 py-2">
                              <p className="text-xs uppercase text-slate-500">Verification</p>
                              <p className="mt-1 text-slate-900">{valueText(session.verification_method)}</p>
                            </div>
                            <div className="rounded-md bg-white px-3 py-2">
                              <p className="text-xs uppercase text-slate-500">Base binding</p>
                              <p className="mt-1 break-all text-slate-900">{valueText(session.base_binding_id || session.binding_id)}</p>
                            </div>
                          </div>
                          {session.reason ? <p className="mt-2 text-slate-600">Причина: {session.reason}</p> : null}
                          {session.warning_code ? <p className="mt-1 text-amber-700">{session.warning_code}</p> : null}
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <span className="text-xs text-slate-500">
                              {formatDateTime(session.created_at)}
                              {session.revoked_at ? ` · revoked ${formatDateTime(session.revoked_at)}` : ""}
                            </span>
                            <Button
                              disabled={session.verification_status === "revoked" || revokeAccountSessionMutation.isPending}
                              onClick={() => revokeAccountSessionMutation.mutate(session.session_id)}
                              size="sm"
                              variant="outline"
                            >
                              Отозвать сессию
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-semibold text-slate-950">Профили агента</h4>
                      <p className="mt-1 text-sm text-slate-500">
                        На одном устройстве может быть несколько профилей. Профиль не перезаписывает подтверждённую привязку без решения ИТ.
                      </p>
                    </div>
                    <Badge tone={profiles.length > 1 ? "warning" : "neutral"}>{profiles.length}</Badge>
                  </div>
                  <div className="mt-4 space-y-3">
                    {profiles.length === 0 ? (
                      <p className="text-sm text-slate-500">Профили агента пока не поступали.</p>
                    ) : (
                      profiles.map((profile, index) => (
                        <div className="rounded-lg bg-surface-subtle px-3 py-3 text-sm" key={`${profile.requester_id ?? "profile"}-${index}`}>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-semibold text-slate-900">{profile.full_name || profile.display_name || "Профиль без имени"}</span>
                            <Badge tone={profile.active ? "success" : "neutral"}>{profile.active ? "текущий" : profile.status}</Badge>
                          </div>
                          <p className="mt-1 text-slate-600">
                            {[profile.department, profile.building, profile.room].filter(Boolean).join(" · ") || "Место не указано"}
                          </p>
                          <p className="mt-1 text-slate-500">
                            {[profile.phone, profile.login || profile.email, formatDateTime(profile.last_seen_at)].filter(Boolean).join(" · ")}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-950">Предложения привязки</h4>
                  <p className="mt-1 text-sm text-slate-500">
                    Сравнивайте профиль агента с текущей подтверждённой привязкой и применяйте только нужные поля.
                  </p>
                  <div className="mt-4 space-y-3">
                    {pendingSuggestions.length === 0 ? (
                      <p className="text-sm text-slate-500">Нет ожидающих предложений.</p>
                    ) : (
                      pendingSuggestions.map((suggestion) => {
                        const suggested = suggestion.suggested_binding;
                        const fields = suggestionFields(suggested);
                        return (
                          <div className="rounded-lg bg-surface-subtle px-3 py-3 text-sm" key={suggestion.id}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-semibold text-slate-900">
                                {String(suggestion.profile_snapshot.full_name ?? suggestion.profile_snapshot.display_name ?? "Профиль агента")}
                              </span>
                              <Badge tone="warning">ожидает</Badge>
                            </div>
                            <div className="mt-3 grid gap-2 md:grid-cols-2">
                              {fields.map((field) => (
                                <div className="rounded-md bg-white px-3 py-2" key={field}>
                                  <p className="text-xs uppercase text-slate-500">{field}</p>
                                  <p className="mt-1 text-slate-900">{valueText(suggested[field])}</p>
                                </div>
                              ))}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                disabled={applySuggestionMutation.isPending}
                                onClick={() => applySuggestionMutation.mutate(suggestion)}
                                size="sm"
                              >
                                Применить поля
                              </Button>
                              <Button
                                disabled={ignoreSuggestionMutation.isPending}
                                onClick={() => ignoreSuggestionMutation.mutate(suggestion.id)}
                                size="sm"
                                variant="outline"
                              >
                                Оставить без изменений
                              </Button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4 xl:col-span-3">
                  <h4 className="text-sm font-semibold text-slate-950">Timeline регистрации</h4>
                  <div className="mt-4 space-y-2">
                    {registrationTimeline.length ? registrationTimeline.slice(0, 8).map((item) => (
                      <div className="rounded-md bg-surface-subtle px-3 py-2 text-sm" key={item.event_id}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold text-slate-900">{item.event_type}</span>
                          <span className="text-xs text-slate-500">{formatDateTime(item.event_at)}</span>
                        </div>
                        <p className="mt-1 text-slate-500">{[item.actor_role, item.actor_id].filter(Boolean).join(" · ") || "system"}</p>
                      </div>
                    )) : (
                      <p className="text-sm text-slate-500">События регистрации пока не записаны.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : null}

            {tab === "presence" ? (
              <div className="space-y-4 rounded-lg border border-border bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-950">Присутствие рабочего места</h4>
                    <p className="mt-1 text-sm text-slate-500">
                      Показывает состояние агента и сеанса без сбора содержимого действий пользователя.
                    </p>
                  </div>
                  <Button
                    disabled={!deviceId || presenceMutation.isPending}
                    leadingIcon={<RefreshCcw className="h-4 w-4" />}
                    onClick={() => presenceMutation.mutate()}
                    size="sm"
                    variant="outline"
                  >
                    {presenceMutation.isPending ? "Отправляем" : "Обновить состояние"}
                  </Button>
                </div>
                {presence?.latest ? (
                  <>
                    <div className="grid gap-3 md:grid-cols-4">
                      <div className="rounded-lg bg-surface-subtle px-4 py-3">
                        <p className="text-sm text-slate-500">Состояние</p>
                        <p className="mt-1 text-2xl font-semibold text-slate-950">{presence.latest.session_state ?? "unknown"}</p>
                      </div>
                      <div className="rounded-lg bg-surface-subtle px-4 py-3">
                        <p className="text-sm text-slate-500">Сеанс</p>
                        <p className="mt-1 text-2xl font-semibold text-slate-950">{presence.latest.current_user ?? "—"}</p>
                      </div>
                      <div className="rounded-lg bg-surface-subtle px-4 py-3">
                        <p className="text-sm text-slate-500">Простой</p>
                        <p className="mt-1 text-2xl font-semibold text-slate-950">{durationText(presence.latest.idle_seconds ?? 0)}</p>
                      </div>
                      <div className="rounded-lg bg-surface-subtle px-4 py-3">
                        <p className="text-sm text-slate-500">Собрано</p>
                        <p className="mt-1 text-sm font-semibold text-slate-950">{formatDateTime(presence.latest.collected_at)}</p>
                      </div>
                    </div>
                    {presence.today ? (
                      <div className="grid gap-3 md:grid-cols-5">
                        <MiniPresence label="Активно" value={durationText(presence.today.active_seconds)} />
                        <MiniPresence label="Простой" value={durationText(presence.today.idle_seconds)} />
                        <MiniPresence label="Заблокировано" value={durationText(presence.today.locked_seconds)} />
                        <MiniPresence label="Офлайн" value={durationText(presence.today.offline_seconds)} />
                        <MiniPresence label="Неизвестно" value={durationText(presence.today.unknown_seconds)} />
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-slate-500">Presence snapshot ещё не поступал.</p>
                )}
                {presenceMutation.isSuccess ? <p className="text-sm text-emerald-700">{presenceMutation.data.message}</p> : null}
                {presenceMutation.isError ? <p className="text-sm text-rose-600">Не удалось отправить presence.collect</p> : null}
              </div>
            ) : null}

            {tab === "history" ? (
              <div className="space-y-4">
                {latest ? (
                  <div className="overflow-hidden rounded-lg border border-border">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-surface-subtle text-slate-600">
                        <tr>
                          <th className="px-3 py-2">Time</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Summary</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(data?.history ?? []).map((item) => (
                          <tr key={item.id} className="border-t border-border">
                            <td className="px-3 py-2">{formatDateTime(item.collected_at)}</td>
                            <td className="px-3 py-2">{item.status}</td>
                            <td className="px-3 py-2">{item.summary ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <div className="rounded-lg border border-border bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-950">Binding changes</h4>
                  <div className="mt-3 space-y-3">
                    {(data?.binding_history ?? []).length === 0 ? (
                      <p className="text-sm text-slate-500">No binding changes yet.</p>
                    ) : (
                      (data?.binding_history ?? []).map((item, index) => (
                        <div className="rounded-lg bg-surface-subtle px-3 py-2 text-sm" key={`${item.changed_at}-${index}`}>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-medium text-slate-800">{formatDateTime(item.changed_at)}</span>
                            <span className="text-slate-500">{item.changed_by ?? "system"}</span>
                          </div>
                          <p className="mt-1 text-slate-600">{item.changed_fields.join(", ") || "fields changed"}</p>
                          {item.reason ? <p className="mt-1 text-slate-500">{item.reason}</p> : null}
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-white p-4">
                  <h4 className="text-sm font-semibold text-slate-950">Refresh runs</h4>
                  <div className="mt-3 space-y-2">
                    {(data?.refresh_runs ?? []).length === 0 ? (
                      <p className="text-sm text-slate-500">No refresh runs recorded.</p>
                    ) : (
                      (data?.refresh_runs ?? []).map((item) => (
                        <div className="grid gap-2 rounded-lg bg-surface-subtle px-3 py-2 text-sm md:grid-cols-[150px_120px_minmax(0,1fr)]" key={item.id}>
                          <span>{formatDateTime(item.requested_at)}</span>
                          <Badge tone={item.status === "dispatched" ? "success" : item.status === "failed" ? "danger" : "neutral"}>{item.status}</Badge>
                          <span className="text-slate-500">{item.error ?? item.job_id ?? "-"}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            ) : null}
            {result && !["raw", "binding", "registration", "presence", "history"].includes(tab) ? (
              <ModuleResultRenderer result={result} presentationSchema={effectiveSchema} />
            ) : null}

            {latest?.device_card_slots && latest.device_card_slots.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {latest.device_card_slots.map((slot) => (
                  <Badge key={slot} tone="neutral">
                    {slot}
                  </Badge>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
