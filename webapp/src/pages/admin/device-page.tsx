import { ArrowLeft, ArrowUpRight, RefreshCcw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { startTransition, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";
import { fetchAdminDevices } from "../../features/admin/api";
import { DeviceInventoryPanel } from "../../features/admin/device-inventory-panel";
import { ObserverQuickPanel } from "../../features/tech/observer-quick-panel";


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


type DeviceDrilldownTab = "inventory" | "observer" | "status";


export function AdminDevicePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [deviceDrilldownTab, setDeviceDrilldownTab] = useState<DeviceDrilldownTab>("status");

  const devicesQuery = useQuery({
    queryKey: ["admin-device-page", query],
    queryFn: () =>
      fetchAdminDevices({
        query,
        statusFilter: "all",
      }),
    retry: false,
    refetchInterval: 15_000,
  });

  const devices = devicesQuery.data?.devices ?? [];
  const selectedDeviceId = searchParams.get("device");
  const selectedDevice = devices.find((item) => item.device_id === selectedDeviceId) ?? devices[0] ?? null;

  useEffect(() => {
    if (!selectedDevice?.device_id) {
      return;
    }
    if (searchParams.get("device") === selectedDevice.device_id) {
      return;
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("device", selectedDevice.device_id);
    startTransition(() => {
      setSearchParams(nextSearchParams, { replace: true });
    });
  }, [searchParams, selectedDevice?.device_id, setSearchParams]);

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => {
                startTransition(() => {
                  navigate(selectedDevice ? `/app/admin/inventory?device=${encodeURIComponent(selectedDevice.device_id)}` : "/app/admin/inventory");
                });
              }}
              size="sm"
              variant="outline"
            >
              К инвентарю
            </Button>
            {selectedDevice ? (
              <Button
                leadingIcon={<ArrowUpRight className="h-4 w-4" />}
                onClick={() => {
                  startTransition(() => {
                    navigate(`/app/admin/device?device=${encodeURIComponent(selectedDevice.device_id)}`);
                  });
                }}
                size="sm"
                variant="outline"
              >
                Карточка устройства
              </Button>
            ) : null}
            <Select
              aria-label="Выбор устройства"
              className="min-w-[280px]"
              onChange={(event) => {
                const nextSearchParams = new URLSearchParams(searchParams);
                nextSearchParams.set("device", event.target.value);
                startTransition(() => {
                  setSearchParams(nextSearchParams);
                });
              }}
              value={selectedDevice?.device_id ?? ""}
            >
              {devices.map((item) => (
                <option key={item.device_id} value={item.device_id}>
                  {item.hostname ?? item.device_id}
                </option>
              ))}
            </Select>
            <Button
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => void devicesQuery.refetch()}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
          </>
        }
        description="Выделенная карточка устройства с текущим состоянием подключения, инвентарём и observer quick panel."
        eyebrow="Admin detail"
        title="Карточка устройства"
      />

      {devicesQuery.isLoading ? <p className="text-sm text-slate-500">Собираем реальную карточку устройства…</p> : null}
      {devicesQuery.isError ? (
        <p className="text-sm text-rose-600">
          {devicesQuery.error instanceof Error ? devicesQuery.error.message : "Не удалось загрузить список устройств."}
        </p>
      ) : null}

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_320px]" data-audit-layout="identity-first" data-testid="device-page-layout">
        <div className="space-y-6">
          <Card>
            <CardHeader className="gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>{selectedDevice?.hostname ?? "Устройство"}</CardTitle>
                  <CardDescription>
                    {selectedDevice
                      ? `${selectedDevice.os ?? "ОС не определена"} • ${selectedDevice.target ?? "target не определён"}`
                      : "Выберите устройство, чтобы открыть реальный update flow."}
                  </CardDescription>
                </div>
                {selectedDevice ? <Badge tone={selectedDevice.online ? "success" : "neutral"} withDot>{selectedDevice.connection_status_label}</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              {selectedDevice ? (
                <>
                  <div
                    aria-label="Основная идентификация и статус устройства"
                    className="rounded-[1.3rem] bg-surface-subtle px-5 py-5"
                    data-testid="device-primary-identity"
                  >
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">{selectedDevice.device_id}</p>
                    <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                      {selectedDevice.hostname ?? selectedDevice.device_id}
                    </p>
                    <p className="mt-3 text-sm text-slate-500">
                      Агент {selectedDevice.agent_version ?? "не сообщил версию"} • {selectedDevice.connection_status_label}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">Последний контакт: {formatDateTime(selectedDevice.last_seen_at)}</p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Последний контакт</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.connection_status_label}</p>
                      <p className="mt-2 text-sm text-slate-500">{formatDateTime(selectedDevice.last_seen_at)}</p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Целевой target</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.target ?? "Не назначен"}</p>
                      <p className="mt-2 text-sm text-slate-500">Идентификатор доступен для диагностики и observer drilldown.</p>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Статус связи</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.connection_status_label}</p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Операционная система</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.os ?? "Не определена"}</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Нет устройства для отображения.
                </div>
              )}
            </CardContent>
          </Card>

          <section className="surface-panel overflow-hidden">
            <div
              aria-label="Device drilldown sections"
              className="flex gap-1 overflow-x-auto border-b border-border bg-surface-subtle p-2"
              data-layout="tabbed-drilldown"
              data-testid="device-drilldown-tabs"
              role="tablist"
            >
              {[
                ["status", "Status"],
                ["inventory", "Inventory"],
                ["observer", "Observer"],
              ].map(([value, label]) => (
                <button
                  aria-selected={deviceDrilldownTab === value}
                  className={`rounded-[0.8rem] px-3 py-2 text-sm font-semibold transition ${
                    deviceDrilldownTab === value
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-500 hover:bg-white/70 hover:text-slate-900"
                  }`}
                  key={value}
                  onClick={() => setDeviceDrilldownTab(value as DeviceDrilldownTab)}
                  role="tab"
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="p-5" data-active-tab={deviceDrilldownTab} data-testid="device-drilldown-panel">
              {deviceDrilldownTab === "status" ? (
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="text-sm text-slate-500">Connection</p>
                    <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice?.connection_status_label ?? "n/a"}</p>
                    <p className="mt-2 text-sm text-slate-500">{formatDateTime(selectedDevice?.last_seen_at)}</p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="text-sm text-slate-500">Agent version</p>
                    <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice?.agent_version ?? "n/a"}</p>
                    <p className="mt-2 text-sm text-slate-500">{selectedDevice?.os ?? "OS n/a"}</p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="text-sm text-slate-500">Diagnostic target</p>
                    <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice?.target ?? "Select device"}</p>
                    <p className="mt-2 text-sm text-slate-500">Endpoint Platform owns agent lifecycle and releases.</p>
                  </div>
                </div>
              ) : null}
              {deviceDrilldownTab === "inventory" ? (
                <DeviceInventoryPanel
                  deviceId={selectedDevice?.device_id ?? null}
                  deviceLabel={selectedDevice?.hostname ?? selectedDevice?.device_id ?? null}
                />
              ) : null}
              {deviceDrilldownTab === "observer" ? (
                <ObserverQuickPanel
                  deviceId={selectedDevice?.device_id ?? null}
                  deviceLabel={selectedDevice?.hostname ?? selectedDevice?.device_id ?? "selected device"}
                />
              ) : null}
            </div>
          </section>

        </div>

        <div className="space-y-4" data-testid="device-secondary-rail" aria-label="Вторичный контекст устройства">
          <Card>
            <CardHeader>
              <CardTitle>Контекст устройства</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Device ID</span>
                <span className="font-medium text-slate-900">{selectedDevice?.device_id ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Hostname</span>
                <span className="font-medium text-slate-900">{selectedDevice?.hostname ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Версия агента</span>
                <span className="font-medium text-slate-900">{selectedDevice?.agent_version ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Target</span>
                <span className="font-medium text-slate-900">{selectedDevice?.target ?? "—"}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Быстрые переходы</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <button
                className="flex w-full items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-left"
                onClick={() => {
                  startTransition(() => {
                    navigate("/app/admin/capabilities");
                  });
                }}
                type="button"
              >
                <span className="font-medium text-slate-900">Возможности Endpoint</span>
                <ArrowUpRight className="h-4 w-4 text-brand-700" />
              </button>
              <button
                className="flex w-full items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-left"
                onClick={() => {
                  startTransition(() => {
                    navigate("/app/admin/forms");
                  });
                }}
                type="button"
              >
                <span className="font-medium text-slate-900">Конструктор форм</span>
                <ArrowUpRight className="h-4 w-4 text-brand-700" />
              </button>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
