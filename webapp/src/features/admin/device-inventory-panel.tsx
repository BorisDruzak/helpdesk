import { RefreshCcw, Save } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ModuleResultRenderer, getPathValue } from "../../components/module-result/module-result-renderer";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Tabs } from "../../components/ui/tabs";
import {
  collectAdminDeviceInventory,
  fetchAdminDeviceInventory,
  saveAdminDeviceInventoryBinding,
  saveAdminDeviceInventoryRefreshPolicy,
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

  const data: AdminDeviceInventoryPayload | undefined = query.data;
  const latest = data?.latest_snapshot ?? null;
  const result = latest?.result ?? null;
  const effectiveSchema = latest?.effective_presentation_schema ?? latest?.presentation_schema ?? undefined;
  const binding = data?.binding ?? null;
  const refreshPolicy = data?.refresh_policy ?? null;

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

            <Tabs
              items={[
                { value: "overview", label: "Обзор" },
                { value: "hardware", label: "Железо" },
                { value: "network", label: "Сеть" },
                { value: "printers", label: "Принтеры" },
                { value: "software", label: "ПО" },
                { value: "binding", label: "Привязка" },
                { value: "history", label: "История" },
                { value: "raw", label: "Raw" },
              ]}
              onValueChange={setTab}
              value={tab}
            />

            {tab === "raw" ? (
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

            {tab === "history" ? (
              <div className="space-y-4">
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
            {!["raw", "binding", "history"].includes(tab) ? (
              <ModuleResultRenderer result={result} presentationSchema={effectiveSchema} />
            ) : null}

            {latest.device_card_slots && latest.device_card_slots.length > 0 ? (
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
