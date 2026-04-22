import { ImagePlus } from "lucide-react";
import { useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";
import { settingsTabs } from "../../mocks/helpdesk-data";

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState(settingsTabs[0]);

  return (
    <section className="space-y-6">
      <PageHeading
        description="Страница настроек перенесена в тот же визуальный язык: спокойные формы, плотные поля и чистая иерархия без тяжелых карточных сеток."
        eyebrow="Configuration"
        title="Настройки"
      />

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-2 border-b border-border pb-4">
            {settingsTabs.map((tab) => (
              <button
                key={tab}
                className={`rounded-pill px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-brand-50 text-brand-800"
                    : "text-slate-500 hover:bg-surface-subtle hover:text-slate-900"
                }`}
                onClick={() => setActiveTab(tab)}
                type="button"
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
            <Card className="border-dashed shadow-none">
              <CardHeader>
                <CardTitle>Общие настройки</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Название компании</span>
                  <Input defaultValue="Сосновский округ" />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Часовой пояс</span>
                  <Select defaultValue="UTC+5 Екатеринбург">
                    <option>UTC+5 Екатеринбург</option>
                    <option>UTC+3 Москва</option>
                  </Select>
                </label>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Язык интерфейса</span>
                    <Select defaultValue="Русский">
                      <option>Русский</option>
                      <option>English</option>
                    </Select>
                  </label>
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Формат даты</span>
                    <Select defaultValue="DD.MM.YYYY">
                      <option>DD.MM.YYYY</option>
                      <option>YYYY-MM-DD</option>
                    </Select>
                  </label>
                </div>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Первый день недели</span>
                  <Select defaultValue="Понедельник">
                    <option>Понедельник</option>
                    <option>Воскресенье</option>
                  </Select>
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Логотип</span>
                  <div className="flex items-center gap-4 rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-700 text-xl font-black tracking-[0.18em] text-white">
                      PC
                    </div>
                    <Button leadingIcon={<ImagePlus className="h-4 w-4" />} size="sm" variant="outline">
                      Изменить
                    </Button>
                  </div>
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Цветовая тема</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { label: "Основной цвет", value: "#1E5C66", swatch: "bg-[#1E5C66]" },
                  { label: "Вторичный цвет", value: "#0A7C5E", swatch: "bg-[#0A7C5E]" },
                  { label: "Акцентный цвет", value: "#F2C94C", swatch: "bg-[#F2C94C]" }
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                    <div>
                      <p className="text-sm text-slate-500">{item.label}</p>
                      <p className="mt-1 font-semibold text-slate-900">{item.value}</p>
                    </div>
                    <span className={`h-10 w-10 rounded-2xl ${item.swatch}`} />
                  </div>
                ))}
                <Button className="w-full">Сохранить изменения</Button>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
