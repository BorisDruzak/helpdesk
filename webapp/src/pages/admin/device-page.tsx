import { ArrowUpRight, Cpu, RefreshCcw } from "lucide-react";
import { useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";
import { devices, getDeviceById } from "../../mocks/helpdesk-data";

export function AdminDevicePage() {
  const [selectedDeviceId, setSelectedDeviceId] = useState(devices[0].id);
  const device = getDeviceById(selectedDeviceId);

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Select className="min-w-[260px]" onChange={(event) => setSelectedDeviceId(event.target.value)} value={device.id}>
            {devices.map((item) => (
              <option key={item.id} value={item.id}>
                {item.hostname}
              </option>
            ))}
          </Select>
        }
        description="Выделенная device card собрана отдельно в меню и больше не прячется внутри карточек. Здесь главный фокус на состоянии устройства, обновлении и истории действий."
        eyebrow="Admin detail"
        title="Карточка устройства"
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{device.hostname}</CardTitle>
              <CardDescription>
                {device.platform} • {device.target} • Последний контакт: {device.lastSeen}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              {[
                { label: "Версия агента", value: device.version },
                { label: "Rollout status", value: device.rolloutStatus },
                { label: "Observer health", value: device.observerHealth },
                { label: "Владелец", value: device.owner }
              ].map((item) => (
                <div key={item.label} className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                  <p className="text-sm text-slate-500">{item.label}</p>
                  <p className="mt-2 text-xl font-semibold text-slate-950">{item.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Таймлайн изменений</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "22 апр. 2026, 09:54 — агент вышел на связь",
                "22 апр. 2026, 09:24 — observer сохранил предупреждение по rollout",
                "21 апр. 2026, 23:12 — назначена целевая версия stable/3.1.20"
              ].map((item) => (
                <div key={item} className="rounded-[1.1rem] border border-border bg-white px-4 py-4 text-sm text-slate-600">
                  {item}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Обновление агента</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-sm text-slate-500">Текущая версия</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{device.version}</p>
                <p className="mt-2 text-sm text-slate-500">Рекомендуемая версия: stable/3.1.21</p>
              </div>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Причина запуска</span>
                <textarea className="field-base min-h-[120px] w-full resize-none px-4 py-4 text-sm" defaultValue="Плановый canary после smoke." />
              </label>
              <Button className="w-full" leadingIcon={<RefreshCcw className="h-4 w-4" />}>
                Запустить rollout
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Быстрые действия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { label: "Открыть observer drilldown", tone: "info" as const },
                { label: "Проверить модульный состав", tone: "brand" as const },
                { label: "Экспортировать карточку", tone: "success" as const }
              ].map((item) => (
                <button key={item.label} className="flex w-full items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-left" type="button">
                  <span className="font-medium text-slate-900">{item.label}</span>
                  <Badge tone={item.tone}>
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Badge>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Hardware summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "CPU: Intel Core i7 / 8 cores",
                "RAM: 32 GB",
                "Storage: NVMe 512 GB",
                "Network: корпоративный VLAN"
              ].map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm text-slate-600">
                  <Cpu className="h-4 w-4 text-brand-700" />
                  <span>{item}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
