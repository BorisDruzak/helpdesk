import { FolderSync, ShieldAlert } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { moduleRegistry } from "../../mocks/helpdesk-data";

export function AdminModulesPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<FolderSync className="h-4 w-4" />} size="sm" variant="outline">
              Синхронизировать реестр
            </Button>
            <Button size="sm">Опубликовать preferred</Button>
          </>
        }
        description="Модули перенесены в отдельный пункт меню. Здесь больше нет случайных карточек, только понятная таблица реестра и контур preferred-version rollout."
        eyebrow="Registry"
        title="Модули"
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Реестр модулей</CardTitle>
            <CardDescription>Единые линии, плотные ряды и статусные бейджи для быстрого сканирования.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-hidden rounded-[1.1rem] border border-border">
              <table className="min-w-full divide-y divide-border text-left text-sm">
                <thead className="bg-surface-subtle text-slate-500">
                  <tr>
                    <th className="px-5 py-3.5 font-medium">Модуль</th>
                    <th className="px-5 py-3.5 font-medium">Preferred</th>
                    <th className="px-5 py-3.5 font-medium">Latest</th>
                    <th className="px-5 py-3.5 font-medium">Статус</th>
                    <th className="px-5 py-3.5 font-medium">Обновлен</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-white">
                  {moduleRegistry.map((moduleItem) => (
                    <tr key={moduleItem.name}>
                      <td className="px-5 py-4">
                        <p className="font-semibold text-slate-950">{moduleItem.name}</p>
                        <p className="mt-1 text-xs text-slate-500">{moduleItem.summary}</p>
                      </td>
                      <td className="px-5 py-4 font-medium text-slate-900">{moduleItem.preferredVersion}</td>
                      <td className="px-5 py-4 font-medium text-slate-600">{moduleItem.latestVersion}</td>
                      <td className="px-5 py-4">
                        <Badge tone={moduleItem.statusTone}>{moduleItem.statusLabel}</Badge>
                      </td>
                      <td className="px-5 py-4 text-slate-500">{moduleItem.updatedAt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Rollout policy</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-slate-500">Режим preferred-rollout</p>
                <p className="mt-2 text-xl font-semibold text-slate-950">Обновлять установленные устройства</p>
              </div>
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-slate-500">После смены preferred</p>
                <p className="mt-2 text-xl font-semibold text-slate-950">Не запускать авто-sync</p>
              </div>
              <Button className="w-full" variant="outline">
                Изменить политику
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Риски публикации</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "observer_quick имеет RC-версию",
                "devices_inventory требует ревью schema diff",
                "forms_builder ожидает согласование UX"
              ].map((item) => (
                <div key={item} className="flex items-start gap-3 rounded-[1.1rem] bg-amber-50 px-4 py-4 text-sm text-amber-800">
                  <ShieldAlert className="mt-0.5 h-4 w-4" />
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
