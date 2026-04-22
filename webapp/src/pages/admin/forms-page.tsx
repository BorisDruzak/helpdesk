import { Plus } from "lucide-react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageHeading } from "../../components/ui/page-heading";
import { Select } from "../../components/ui/select";

export function AdminFormsPage() {
  return (
    <section className="space-y-6">
      <PageHeading
        actions={<Button leadingIcon={<Plus className="h-4 w-4" />}>Новая форма</Button>}
        description="Конструктор форм перенесен в отдельную admin-зону и оформлен теми же токенами, что и support workspace."
        eyebrow="Forms builder"
        title="Конструктор форм"
      />

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Каталог форм</CardTitle>
            <CardDescription>Активная версия пакета 1.0.4</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              "Доступ и аккаунты",
              "Печать / принтер",
              "Сайт / система"
            ].map((item, index) => (
              <button
                key={item}
                className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                  index === 0 ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                }`}
                type="button"
              >
                <p className="font-medium">{item}</p>
                <p className="mt-1 text-xs text-current/70">request kind: {index === 0 ? "access" : index === 1 ? "printer" : "site_system"}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Редактор формы</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Название формы</span>
                <Input defaultValue="Доступ и аккаунты" />
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Ключ формы</span>
                  <Input defaultValue="access" />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Request kind</span>
                  <Input defaultValue="access" />
                </label>
              </div>
              <label className="space-y-2 text-sm font-medium text-slate-800">
                <span>Описание</span>
                <textarea className="field-base min-h-[120px] w-full resize-none px-4 py-4 text-sm" defaultValue="Сценарий для сброса пароля, проблем со входом и управления доступами." />
              </label>
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Поле 1</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input defaultValue="Логин пользователя" />
                <Select defaultValue="text">
                  <option value="text">Текст</option>
                  <option value="textarea">Большой текст</option>
                  <option value="select">Список</option>
                </Select>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Поле 2</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input defaultValue="Подразделение" />
                <Select defaultValue="select">
                  <option value="select">Список</option>
                  <option value="radio">Переключатель</option>
                  <option value="checkbox">Флажок</option>
                </Select>
              </CardContent>
            </Card>
          </div>

          <Button className="w-full">Сохранить изменения</Button>
        </div>
      </div>
    </section>
  );
}
