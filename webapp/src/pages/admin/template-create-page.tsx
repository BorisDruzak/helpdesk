import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { PageHeader, PageShell, LoadingState, ErrorState } from "../../components/ui-page/page-components";
import { useSession } from "../../features/auth/session-provider";
import { hasPermission } from "../../features/auth/permissions";
import { fetchHelpdeskModelRegistry, publishHelpdeskTemplateFromForm, type AdminFormsSaveRequest } from "../../features/forms-builder/api";
import { ScenarioActionBar } from "../../features/request-template-studio/scenario-action-bar";
import { useScenarioDirtyGuard } from "../../features/request-template-studio/use-scenario-dirty-guard";

type Form = AdminFormsSaveRequest["forms"][number];
const policyLabels = { routing: "Очередь и маршрут", priority: "Приоритет", sla: "Сроки обслуживания", ola: "Внутренние сроки", approval: "Согласование", closure: "Закрытие", visibility: "Видимость", notification: "Уведомления" } as const;
const newField = (): Form["fields"][number] => ({ key: `field_${crypto.randomUUID().replaceAll("-", "")}`, label: "Новый вопрос", type: "text", required: false, options: [] });

export function AdminTemplateCreatePage() {
  const { session } = useSession();
  const canCreate = session?.actor_role === "admin" && hasPermission(session, "admin.forms.publish");
  const registry = useQuery({ queryKey: ["template-create-registry"], queryFn: fetchHelpdeskModelRegistry, enabled: canCreate });
  const [form, setForm] = useState<Form>(() => { const key = `template_${crypto.randomUUID().replaceAll("-", "")}`; return { key, request_kind: key, title: "", description: "", ticket_type: "incident", fields: [{ ...newField(), label: "Опишите проблему", type: "textarea", required: true }] }; });
  const [dirty, setDirty] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const publication = useMutation({ mutationFn: () => publishHelpdeskTemplateFromForm({ form, publish_policies: false }), onSuccess: () => { setDirty(false); setConfirming(false); } });
  useScenarioDirtyGuard(dirty && !publication.isSuccess);
  function change(next: Form) { setForm(next); setDirty(true); setConfirming(false); }
  function updateField(index: number, patch: Partial<Form["fields"][number]>) { change({ ...form, fields: form.fields.map((field, i) => i === index ? { ...field, ...patch } : field) }); }
  const valid = !!form.title.trim() && form.fields.length > 0 && form.fields.every(field => field.label.trim());
  return <PageShell width="wide">
    <PageHeader title="Создать шаблон" description="Шаблон задаёт обычную форму обращения и правила её обработки. Его можно использовать для одной или нескольких услуг." actions={<Link className="text-sm underline" to="/app/admin/forms">Вернуться в конструктор</Link>} />
    {!canCreate ? <p>Создание шаблонов доступно администратору с правом публикации форм.</p> : publication.isSuccess ? <section className="space-y-4 rounded-xl border bg-white p-5" role="status"><h2 className="font-semibold">Шаблон опубликован: {form.title}</h2><p>Вернитесь во вкладку создания услуги, нажмите «Обновить список шаблонов» и выберите этот шаблон. Введённая услуга останется в своей вкладке.</p></section> : registry.isPending ? <LoadingState label="Загрузка правил обработки" /> : registry.isError ? <ErrorState title="Правила обработки недоступны" message="Повторите загрузку перед созданием шаблона." onRetry={() => void registry.refetch()} /> : <form id="template-create" className="space-y-5 rounded-xl border bg-white p-5" onSubmit={event => { event.preventDefault(); if (valid && !publication.isPending) setConfirming(true); }}>
      <ScenarioActionBar><div className="flex flex-wrap items-center gap-3"><Button type="submit" form="template-create" disabled={!valid || publication.isPending}>Опубликовать шаблон</Button><p className="text-sm">Услуги и сценарии создаются отдельно.</p></div></ScenarioActionBar>
      <fieldset disabled={publication.isPending} className="space-y-4">
        <h2 className="text-lg font-semibold">Форма и правила обработки</h2>
        <label className="block">Название шаблона<Input required maxLength={300} value={form.title} onChange={event => change({ ...form, title: event.target.value })} /></label>
        <label className="block">Описание шаблона<Input maxLength={2000} value={form.description} onChange={event => change({ ...form, description: event.target.value })} /></label>
        <label className="block">Тип обращения<Select value={form.ticket_type ?? "incident"} onChange={event => change({ ...form, ticket_type: event.target.value })}><option value="incident">Инцидент — что-то не работает</option><option value="service_request">Запрос услуги</option><option value="access">Запрос доступа</option><option value="consultation">Консультация</option></Select></label>
        <section aria-label="Вопросы обычной формы" className="space-y-3"><h3 className="font-semibold">Что спросить у сотрудника</h3>
          {form.fields.map((field, index) => <fieldset key={field.key} className="space-y-3 rounded-lg border p-4"><legend>Вопрос {index + 1}</legend>
            <label className="block">Название вопроса {index + 1}<Input required maxLength={300} value={field.label} onChange={event => updateField(index, { label: event.target.value })} /></label>
            <label className="block">Тип ответа {index + 1}<Select value={field.type} onChange={event => updateField(index, { type: event.target.value as "text" | "textarea" | "checkbox" })}><option value="text">Короткий текст</option><option value="textarea">Подробный ответ</option><option value="checkbox">Да / нет</option></Select></label>
            <label><input type="checkbox" checked={field.required} onChange={event => updateField(index, { required: event.target.checked })} /> Обязательный ответ {index + 1}</label>
            <Button variant="ghost" disabled={form.fields.length === 1} onClick={() => change({ ...form, fields: form.fields.filter((_, i) => i !== index) })}>Удалить вопрос {index + 1}</Button>
          </fieldset>)}
          <Button variant="secondary" disabled={form.fields.length >= 100} onClick={() => change({ ...form, fields: [...form.fields, newField()] })}>Добавить вопрос</Button>
          <p className="text-sm text-slate-600">Здесь доступны текстовые вопросы и ответы «Да / нет».</p>
        </section>
        <details className="space-y-3 rounded-lg border p-4"><summary className="cursor-pointer font-semibold">Как обрабатывать обращение</summary><p className="text-sm">Можно выбрать действующие правила или наследовать настройки системы и раздела услуги.</p><div className="grid gap-4 md:grid-cols-2">{Object.entries(policyLabels).map(([kind, label]) => {
          const key = `${kind}_policy_ref` as keyof Form;
          return <label key={kind} className="block">{label}<Select value={String(form[key] ?? "")} onChange={event => change({ ...form, [key]: event.target.value || null })}><option value="">Наследовать настройки</option>{(registry.data?.policies[kind] ?? []).filter((item, index, items) => item.is_active && item.published_at && items.findIndex(other => other.code === item.code && other.is_active && other.published_at) === index).map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</Select></label>;
        })}</div></details>
      </fieldset>
      {confirming && <section aria-label="Подтверждение публикации шаблона" className="space-y-3 rounded-lg border border-amber-300 p-4"><p>Опубликовать «{form.title.trim()}»? Шаблон станет доступен для выбора при создании услуги. Существующие услуги и формы сохраняют свои настройки.</p><Button type="button" disabled={publication.isPending || !valid} onClick={() => publication.mutate()}>Подтвердить публикацию шаблона</Button><Button variant="ghost" disabled={publication.isPending} onClick={() => setConfirming(false)}>Продолжить редактирование</Button></section>}
      {publication.isError && <p role="alert">Не удалось опубликовать шаблон. Данные сохранены на этой странице; проверьте настройки и повторите.</p>}
    </form>}
  </PageShell>;
}
