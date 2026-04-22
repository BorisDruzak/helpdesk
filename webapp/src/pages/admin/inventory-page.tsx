import { Activity, ArrowUpRight, RefreshCcw, ServerCog } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import { type AdminStatusFilter, fetchAdminDevices } from "../../features/admin/api";


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


function getConnectionTone(value: boolean): "neutral" | "success" {
  return value ? "success" : "neutral";
}


function getUpdateTone(value: string | null | undefined): "danger" | "info" | "neutral" | "success" | "warning" {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "neutral";
  }
  if (["succeeded", "ok", "completed", "up_to_date"].includes(normalized)) {
    return "success";
  }
  if (["queued", "running", "in_progress"].includes(normalized)) {
    return "info";
  }
  if (["failed", "timed_out", "error"].includes(normalized)) {
    return "danger";
  }
  return "warning";
}


export function AdminInventoryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<AdminStatusFilter>("all");
  const deferredQuery = useDeferredValue(query);

  const devicesQuery = useQuery({
    queryKey: ["admin-devices-page", deferredQuery, statusFilter],
    queryFn: () =>
      fetchAdminDevices({
        query: deferredQuery,
        statusFilter,
      }),
    retry: false,
    refetchInterval: 15_000,
  });

  const devices = devicesQuery.data?.devices ?? [];
  const selectedDeviceId = searchParams.get("device");
  const selectedDevice = devices.find((item) => item.device_id === selectedDeviceId) ?? devices[0] ?? null;
  const rolloutAssignments = selectedDevice
    ? (devicesQuery.data?.rollout ?? []).filter((item) => item.target === selectedDevice.target)
    : devicesQuery.data?.rollout ?? [];
  const alertCount = devices.filter((device) => {
    const status = String(device.latest_update.status ?? "").trim().toLowerCase();
    return ["failed", "timed_out", "error"].includes(status);
  }).length;

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

  function openDeviceCard() {
    if (!selectedDevice) {
      return;
    }
    startTransition(() => {
      navigate(`/app/admin/device?device=${encodeURIComponent(selectedDevice.device_id)}`);
    });
  }

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => void devicesQuery.refetch()}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
            <Button
              disabled={!selectedDevice}
              leadingIcon={<ArrowUpRight className="h-4 w-4" />}
              onClick={openDeviceCard}
              size="sm"
            >
              Открыть карточку
            </Button>
          </>
        }
        description="Реальный инвентарь устройств, rollout-назначения и текущее состояние агентов в том же рабочем SaaS-слое, без моков и без возврата в legacy admin shell."
        eyebrow="Admin workspace"
        title="Инвентарь устройств"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile
          helper="По текущему server-side срезу"
          label="Устройств в инвентаре"
          value={String(devicesQuery.data?.summary.visible_count ?? 0)}
        />
        <StatTile
          helper="По heartbeat и last_seen"
          label="Онлайн сейчас"
          value={String(devicesQuery.data?.summary.online_count ?? 0)}
        />
        <StatTile
          helper="Активные rollout-направления"
          label="Rollout targets"
          value={String(devicesQuery.data?.summary.rollout_targets ?? 0)}
        />
        <StatTile
          helper="Последний статус обновления устройства"
          label="Требуют внимания"
          value={String(alertCount)}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Список устройств</CardTitle>
            <CardDescription>Выбор устройства, фильтр статуса и быстрый переход к реальной карточке агента.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SearchField
              onChange={(event) => setQuery(event.target.value)}
              placeholder="device_id, hostname, ОС или версия"
              value={query}
            />
            <Select
              onChange={(event) => setStatusFilter(event.target.value as AdminStatusFilter)}
              value={statusFilter}
            >
              {(devicesQuery.data?.filters.status_options ?? [
                { value: "all", label: "Все устройства" },
                { value: "online", label: "Только онлайн" },
                { value: "offline", label: "Только офлайн" },
              ]).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>

            {devicesQuery.isLoading ? <p className="text-sm text-slate-500">Собираем реальный inventory-срез…</p> : null}
            {devicesQuery.isError ? (
              <p className="text-sm text-rose-600">
                {devicesQuery.error instanceof Error ? devicesQuery.error.message : "Не удалось загрузить устройства."}
              </p>
            ) : null}

            <div className="space-y-3">
              {devices.length ? (
                devices.map((device) => {
                  const active = selectedDevice?.device_id === device.device_id;
                  return (
                    <button
                      key={device.device_id}
                      className={`w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors ${
                        active
                          ? "border-brand-200 bg-brand-50"
                          : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                      }`}
                      onClick={() => {
                        const nextSearchParams = new URLSearchParams(searchParams);
                        nextSearchParams.set("device", device.device_id);
                        startTransition(() => {
                          setSearchParams(nextSearchParams);
                        });
                      }}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-950">{device.hostname ?? device.device_id}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">{device.device_id}</p>
                        </div>
                        <Badge tone={getConnectionTone(device.online)} withDot>
                          {device.connection_status_label}
                        </Badge>
                      </div>
                      <p className="mt-3 text-sm text-slate-500">
                        {(device.os ?? "ОС не определена")} • {device.target ?? "target не определён"}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">Последний контакт: {formatDateTime(device.last_seen_at)}</p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  По текущему фильтру устройств не найдено.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader className="gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>{selectedDevice?.hostname ?? "Карточка устройства"}</CardTitle>
                  <CardDescription>
                    {selectedDevice
                      ? `${selectedDevice.os ?? "ОС не определена"} • ${selectedDevice.target ?? "target не определён"}`
                      : "Выберите устройство слева, чтобы открыть реальное состояние агента."}
                  </CardDescription>
                </div>
                {selectedDevice ? (
                  <Badge tone={getUpdateTone(selectedDevice.latest_update.status)} withDot>
                    {selectedDevice.latest_update.label}
                  </Badge>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              {selectedDevice ? (
                <>
                  <div className="rounded-[1.3rem] bg-surface-subtle px-5 py-5">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">{selectedDevice.device_id}</p>
                    <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                      {selectedDevice.hostname ?? selectedDevice.device_id}
                    </p>
                    <p className="mt-3 text-sm text-slate-500">
                      Агент {selectedDevice.agent_version ?? "не сообщил версию"} • {selectedDevice.connection_status_label}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Последний контакт: {formatDateTime(selectedDevice.last_seen_at)}
                    </p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Текущее обновление</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.latest_update.label}</p>
                      <p className="mt-2 text-sm text-slate-500">
                        {selectedDevice.latest_update.summary ?? "Сервер ещё не сформировал подробности по update flow."}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                      <p className="text-sm text-slate-500">Rollout target</p>
                      <p className="mt-2 text-xl font-semibold text-slate-950">{selectedDevice.target ?? "Не назначен"}</p>
                      <p className="mt-2 text-sm text-slate-500">Полная карточка устройства откроет update workflow и observer quick panel.</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Нет активного устройства для предпросмотра.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Назначения rollout</CardTitle>
              <CardDescription>Серверные назначения по текущему target устройства без моков.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {rolloutAssignments.length ? (
                rolloutAssignments.map((assignment) => (
                  <div key={`${assignment.target}:${assignment.channel}:${assignment.version}`} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{assignment.target}</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">
                      {assignment.channel}/{assignment.version}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Обновлено {formatDateTime(assignment.updated_at)}{assignment.updated_by ? ` • ${assignment.updated_by}` : ""}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Для выбранного target rollout-назначений пока нет.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Операторский инспектор</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Device ID</span>
                <span className="font-medium text-slate-900">{selectedDevice?.device_id ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Статус связи</span>
                <span className="font-medium text-slate-900">{selectedDevice?.connection_status_label ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">ОС</span>
                <span className="font-medium text-slate-900">{selectedDevice?.os ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Версия агента</span>
                <span className="font-medium text-slate-900">{selectedDevice?.agent_version ?? "—"}</span>
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
                onClick={openDeviceCard}
                type="button"
              >
                <span className="font-medium text-slate-900">Карточка устройства</span>
                <ServerCog className="h-4 w-4 text-brand-700" />
              </button>
              <button
                className="flex w-full items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-left"
                onClick={() => {
                  startTransition(() => {
                    navigate("/app/admin/modules");
                  });
                }}
                type="button"
              >
                <span className="font-medium text-slate-900">Реестр модулей</span>
                <ArrowUpRight className="h-4 w-4 text-brand-700" />
              </button>
              <button
                className="flex w-full items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-left"
                onClick={() => {
                  startTransition(() => {
                    navigate("/app/admin/observer");
                  });
                }}
                type="button"
              >
                <span className="font-medium text-slate-900">Observer overview</span>
                <Activity className="h-4 w-4 text-brand-700" />
              </button>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
