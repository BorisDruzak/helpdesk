import { RefreshCcw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ModuleResultRenderer, getPathValue } from "../../components/module-result/module-result-renderer";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Tabs } from "../../components/ui/tabs";
import {
  collectAdminDeviceInventory,
  fetchAdminDeviceInventory,
  type AdminDeviceInventoryPayload,
} from "./api";

type DeviceInventoryPanelProps = {
  deviceId: string | null;
  deviceLabel?: string | null;
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

export function DeviceInventoryPanel({ deviceId, deviceLabel }: DeviceInventoryPanelProps) {
  const [tab, setTab] = useState("overview");
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

  const data: AdminDeviceInventoryPayload | undefined = query.data;
  const latest = data?.latest_snapshot ?? null;
  const result = latest?.result ?? null;
  const effectiveSchema = latest?.effective_presentation_schema ?? latest?.presentation_schema ?? undefined;

  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Инвентарь устройства</CardTitle>
            <CardDescription>
              {deviceLabel ?? deviceId ?? "Выберите устройство"} · latest inventory.collect snapshot
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {latest ? <Badge tone="info">{schemaSourceLabel(latest.presentation_schema_source)}</Badge> : null}
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
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">User / OS</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{valueText(getPathValue(result, "identity.current_user"))}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {valueText(getPathValue(result, "platform.os_name"))} {valueText(getPathValue(result, "platform.os_version"), "")}
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

            <Tabs
              items={[
                { value: "overview", label: "Обзор" },
                { value: "platform", label: "ОС и агент" },
                { value: "hardware", label: "Железо" },
                { value: "network", label: "Сеть" },
                { value: "printers", label: "Принтеры" },
                { value: "software", label: "ПО" },
                { value: "raw", label: "Raw" },
              ]}
              onValueChange={setTab}
              value={tab}
            />

            {tab === "raw" ? (
              <pre className="max-h-[420px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
                {JSON.stringify(result, null, 2)}
              </pre>
            ) : (
              <ModuleResultRenderer result={result} presentationSchema={effectiveSchema} />
            )}

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
