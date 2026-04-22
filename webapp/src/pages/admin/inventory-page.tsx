import { Activity, Layers3, RefreshCcw } from "lucide-react";
import { startTransition, useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import { devices, getDeviceById } from "../../mocks/helpdesk-data";

export function AdminInventoryPage() {
  const [selectedDeviceId, setSelectedDeviceId] = useState(devices[0].id);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const deferredQuery = useDeferredValue(query);
  const selectedDevice = getDeviceById(selectedDeviceId);

  const visibleDevices = devices.filter((device) => {
    const matchesStatus = statusFilter === "all" ? true : device.status === statusFilter;
    const matchesQuery =
      deferredQuery.trim().length === 0
        ? true
        : [device.hostname, device.platform, device.target, device.owner]
            .join(" ")
            .toLowerCase()
            .includes(deferredQuery.trim().toLowerCase());

    return matchesStatus && matchesQuery;
  });

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} size="sm" variant="outline">
              Синхронизировать
            </Button>
            <Button leadingIcon={<Activity className="h-4 w-4" />} size="sm">
              Запустить проверку
            </Button>
          </>
        }
        description="Админка теперь тоже живет как рабочий SaaS-интерфейс: список устройств слева, выбранное устройство в центре, полезный инспектор справа."
        eyebrow="Admin workspace"
        title="Инвентарь устройств"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile helper="Видно в рабочем срезе" label="Всего в инвентаре" value="28" />
        <StatTile helper="Сейчас на связи" label="Онлайн" value="16" />
        <StatTile helper="Назначенных каналов" label="Rollout targets" value="4" />
        <StatTile helper="С активными замечаниями" label="Observer alerts" value="3" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Список устройств</CardTitle>
            <CardDescription>Панель вынесена отдельно, чтобы device card в центре оставалась главной.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="device_id, hostname, ОС" value={query} />
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">Все устройства</option>
              <option value="online">Только онлайн</option>
              <option value="attention">Требуют внимания</option>
              <option value="offline">Только оффлайн</option>
            </Select>

            <div className="space-y-3">
              {visibleDevices.map((device) => {
                const active = selectedDeviceId === device.id;
                const tone = device.status === "online" ? "success" : device.status === "attention" ? "warning" : "neutral";

                return (
                  <button
                    key={device.id}
                    className={`w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors ${
                      active
                        ? "border-brand-200 bg-brand-50"
                        : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                    }`}
                    onClick={() =>
                      startTransition(() => {
                        setSelectedDeviceId(device.id);
                      })
                    }
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-base font-semibold text-slate-950">{device.hostname}</p>
                      <Badge tone={tone}>
                        {device.status === "online"
                          ? "Онлайн"
                          : device.status === "attention"
                            ? "Внимание"
                            : "Оффлайн"}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm text-slate-500">
                      {device.platform} • {device.target}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">{device.lastSeen}</p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader className="gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Карточка устройства</CardTitle>
                  <CardDescription>Единая SaaS-структура и те же визуальные токены, что у support workspace.</CardDescription>
                </div>
                <Link className="text-sm font-semibold text-brand-700" to="/app/admin/device">
                  Открыть полную карточку
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-[1.3rem] bg-surface-subtle px-5 py-5">
                <p className="text-xs uppercase tracking-[0.22em] text-brand-700">{selectedDevice.id}</p>
                <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{selectedDevice.hostname}</p>
                <p className="mt-3 text-sm text-slate-500">
                  {selectedDevice.platform} • Target: {selectedDevice.target}
                </p>
                <p className="mt-2 text-sm text-slate-500">Последний контакт: {selectedDevice.lastSeen}</p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                  <p className="text-sm text-slate-500">Версия агента</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">{selectedDevice.version}</p>
                  <p className="mt-2 text-sm text-slate-500">Срез нужен для rollout-решений и контроля расхождений по парку устройств.</p>
                </div>
                <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                  <p className="text-sm text-slate-500">Готовность к обновлению</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">{selectedDevice.rolloutStatus}</p>
                  <p className="mt-2 text-sm text-slate-500">{selectedDevice.notes}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Назначения rollout</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { target: "windows_amd64", version: "stable/3.1.20", updatedBy: "admin" },
                { target: "linux_alt_x86_64", version: "stable/3.1.18", updatedBy: "release-bot" }
              ].map((item) => (
                <div key={item.target} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{item.target}</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">{item.version}</p>
                  <p className="mt-2 text-sm text-slate-500">Обновил {item.updatedBy}</p>
                </div>
              ))}
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
                <span className="text-slate-500">Ответственный</span>
                <span className="font-medium text-slate-900">{selectedDevice.owner}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Локация</span>
                <span className="font-medium text-slate-900">{selectedDevice.location}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Observer</span>
                <span className="font-medium text-slate-900">{selectedDevice.observerHealth}</span>
              </div>
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Модули</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge tone="brand">devices_inventory</Badge>
                  <Badge tone="success">agent_rollout</Badge>
                  <Badge tone="info">observer_quick</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Текущее действие</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-sm text-slate-500">Запуск обновления</p>
                <p className="mt-2 font-semibold text-slate-950">Текущая версия {selectedDevice.version}</p>
                <p className="mt-2 text-sm text-slate-500">Следующее окно раскатки доступно после подтверждения канарейки.</p>
              </div>
              <Button className="w-full" leadingIcon={<Layers3 className="h-4 w-4" />}>
                Открыть rollout workflow
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
