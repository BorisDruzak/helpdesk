import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { AdvancedDisclosure } from "../../components/ui-page/advanced-disclosure";
import { RequestStudioApiError } from "./api";
import { archiveCategory, saveCategory, type CategoryInput, type ScenarioCatalog, type ScenarioCategory } from "./scenario-api";
import { categoryDescendants } from "./scenario-catalog";

export function ScenarioCategoryForm({ catalog, category, onDone, onCancel, onDirty }: { catalog: ScenarioCatalog; category?: ScenarioCategory; onDone: () => Promise<void>; onCancel: () => void; onDirty: (dirty: boolean) => void }) {
  const [value, setValue] = useState<CategoryInput>(() => category ? { service_code: category.service_code, parent_id: category.parent_id, slug: category.slug, title: category.title, description: category.description, visibility: category.visibility, sort_order: category.sort_order, lifecycle_status: category.lifecycle_status, revision: category.revision } : { service_code: catalog.services[0]?.code ?? "", parent_id: null, slug: `category_${crypto.randomUUID().slice(0, 8)}`, title: "", description: "", sort_order: 0, visibility: "internal", lifecycle_status: "draft" });
  const [confirmArchive, setConfirmArchive] = useState(false);
  const initial = useRef(JSON.stringify(value));
  const dirty = JSON.stringify(value) !== initial.current;
  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  const mutation = useMutation({ mutationFn: (archive: boolean) => archive && category ? archiveCategory(category.id, category.revision) : saveCategory(value, category?.id), onSuccess: onDone });
  const excluded = category ? categoryDescendants(catalog, category.id) : new Set<string>();
  return <form className="min-w-0 space-y-4 rounded-xl border p-5" onSubmit={event => { event.preventDefault(); mutation.mutate(false); }}>
    <h2 className="text-lg font-semibold">{category ? "Изменить категорию" : "Новая категория"}</h2>
    <fieldset disabled={mutation.isPending} className="space-y-4">
      <label className="block">Название категории<Input required maxLength={300} value={value.title} onChange={event => setValue({ ...value, title: event.target.value })} /></label>
      <label className="block">Сервис<Select disabled={!!category} value={value.service_code} onChange={event => setValue({ ...value, service_code: event.target.value, parent_id: null })}>{catalog.services.map(item => <option key={item.code} value={item.code}>{item.public_title}</option>)}</Select></label>
      <label className="block">Родительская категория<Select value={value.parent_id ?? ""} onChange={event => setValue({ ...value, parent_id: event.target.value || null })}><option value="">Корень сервиса</option>{catalog.categories.filter(item => item.service_code === value.service_code && !excluded.has(item.id) && item.lifecycle_status !== "archived").map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
      <AdvancedDisclosure title="Расширенные настройки">
        <label className="block">Код категории<Input required pattern="[a-z0-9][a-z0-9_-]*" value={value.slug} onChange={event => setValue({ ...value, slug: event.target.value })} /></label>
        <label className="block">Описание категории<Input maxLength={2000} value={value.description} onChange={event => setValue({ ...value, description: event.target.value })} /></label>
        <label className="block">Видимость<Select value={value.visibility} onChange={event => setValue({ ...value, visibility: event.target.value as CategoryInput["visibility"] })}><option value="public">Публичная</option><option value="internal">Внутренняя</option><option value="restricted">Ограниченная</option></Select></label>
        <label className="block">Состояние категории<Select value={value.lifecycle_status} onChange={event => setValue({ ...value, lifecycle_status: event.target.value as CategoryInput["lifecycle_status"] })}><option value="draft">Черновик</option><option value="published">Опубликована</option><option value="archived">Архив</option></Select></label>
        <label className="block">Порядок<Input type="number" min={-100000} max={100000} value={value.sort_order} onChange={event => setValue({ ...value, sort_order: Number(event.target.value) })} /></label>
      </AdvancedDisclosure>
    </fieldset>
    {mutation.isError && <p role="alert">{mutation.error instanceof RequestStudioApiError && mutation.error.status === 409 ? "Категория изменена или содержит вложенные объекты. Закройте форму и обновите каталог." : "Категорию не удалось сохранить. Проверьте настройки и повторите."}</p>}
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={mutation.isPending || !value.service_code}>Сохранить категорию</Button><Button variant="ghost" disabled={mutation.isPending} onClick={() => { if (!dirty || window.confirm("Закрыть категорию без сохранения изменений?")) onCancel(); }}>Отмена</Button>{category && <Button variant="ghost" disabled={mutation.isPending || dirty} onClick={() => setConfirmArchive(true)}>Архивировать категорию</Button>}</div>
    {confirmArchive && <div role="alert" className="space-y-2"><p>Архивировать пустую категорию? Вложенные категории и сценарии нужно переместить заранее.</p><Button disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>Подтвердить архивирование</Button><Button variant="ghost" onClick={() => setConfirmArchive(false)}>Оставить категорию</Button></div>}
  </form>;
}
