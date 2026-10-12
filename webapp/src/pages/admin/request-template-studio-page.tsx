import { useDeferredValue, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { OfferingDetails } from "../../features/request-template-studio/offering-details";
import type { AdminServiceCatalogOffering } from "../../features/service-catalog/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { PageShell, PageHeader, PageActions, ErrorState, LoadingState } from "../../components/ui-page/page-components";
import { useSession } from "../../features/auth/session-provider";
import { fetchScenarioCatalog } from "../../features/request-template-studio/scenario-api";
import { ScenarioCatalogExplorer } from "../../features/request-template-studio/scenario-catalog";
import { ScenarioCategoryForm } from "../../features/request-template-studio/scenario-category-form";
import { ScenarioWizard } from "../../features/request-template-studio/scenario-wizard";
import { useScenarioEditor } from "../../features/request-template-studio/use-scenario-editor";
import { useScenarioContext } from "../../features/request-template-studio/use-scenario-context";
import { useScenarioDirtyGuard } from "../../features/request-template-studio/use-scenario-dirty-guard";
import { ScenarioActionBar } from "../../features/request-template-studio/scenario-action-bar";

export function AdminRequestTemplateStudioPage() {
  const { offeringCode } = useParams();
  const [params] = useSearchParams();
  return <StudioWorkspace key={[offeringCode ?? "catalog", params.get("service"), params.get("offering"), params.get("template")].join(":")} />;
}

function StudioWorkspace() {
  const { session } = useSession();
  const canEdit = session?.actor_role === "admin";
  const cache = useQueryClient();
  const { offeringCode } = useParams();
  const [params] = useSearchParams();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);
  const [category, setCategory] = useState<string | null>(() => params.get("service") ? `service:${params.get("service")}` : null);
  const [categoryEditor, setCategoryEditor] = useState<string | null>(null);
  const [categoryDirty, setCategoryDirty] = useState(false);
  const [inlineCategoryOpen, setInlineCategoryOpen] = useState(false);
  const [confirm, setConfirm] = useState<"leave" | "archive" | null>(null);
  const deferredQuery = useDeferredValue(query);
  const catalog = useQuery({ queryKey: ["scenario-catalog", offeringCode, deferredQuery, status, offset, category], queryFn: () => offeringCode ? fetchScenarioCatalog("", "all", 0, null, offeringCode) : fetchScenarioCatalog(deferredQuery, status, offset, category) });
  const editor = useScenarioEditor();
  const contextNotice = useScenarioContext(catalog.data, editor, canEdit);
  useScenarioDirtyGuard(editor.dirty || categoryDirty);
  const editing = !!editor.definition;
  const offering = catalog.data?.offerings.find(item => item.full_code === offeringCode);
  function createForOffering(item: AdminServiceCatalogOffering) {
    editor.create({ scenario_key: "new_scenario", service_code: item.service_code ?? "", offering_full_code: item.full_code,
      title: item.public_title, blocks: [], process_binding: { request_template_key: item.request_template_key ?? "" } }, false);
  }
  function leave() { if (editor.dirty || categoryDirty) setConfirm("leave"); else editor.close(); }
  return <PageShell width="wide">
    <div className="bg-white/95 pb-3">
      <PageHeader title={offeringCode && !editing ? offering?.public_title ?? "Услуга" : "Студия обращений"} description={editing ? "Настройте сценарий по шагам. Сохранение черновика не включает его для пользователей." : offeringCode ? "Форма, сценарий и история одной услуги." : "Единый каталог: одна карточка на услугу. Видно, какую форму сейчас используют сотрудники."} actions={<ScenarioActionBar><PageActions>
        {editing ? <><Button variant="ghost" disabled={editor.busy || inlineCategoryOpen} onClick={leave}>{offeringCode ? "Вернуться к услуге" : "Вернуться в каталог"}</Button>{canEdit && !editor.detail?.scenario.archived && <Button disabled={editor.busy || inlineCategoryOpen || !editor.dirty || !editor.definition?.title.trim() || !editor.definition.offering_full_code} onClick={() => editor.save.mutate()}>Сохранить черновик</Button>}</> : offeringCode ? <Link className="inline-flex min-h-11 items-center px-4 text-sm font-semibold underline" to="/app/admin/request-template-studio">Вернуться в каталог</Link> : canEdit && !categoryEditor && <><Button variant="secondary" disabled={!catalog.data || editor.busy} onClick={() => setCategoryEditor("new")}>Создать категорию</Button><Button disabled={!catalog.data || editor.busy} onClick={() => editor.create()}>Создать сценарий</Button></>}
      </PageActions></ScenarioActionBar>} />
    </div>
    {!canEdit && <p className="text-sm text-slate-500">Режим чтения: изменения доступны администратору.</p>}
    {contextNotice && <p role="status">{contextNotice}</p>}
    {editor.message && <p role="status" className="rounded-md bg-emerald-50 p-3 text-emerald-900">{editor.message}</p>}
    {editor.error && <div role="alert" className="space-y-2 rounded-md bg-amber-50 p-3"><p>{editor.error}</p>{editor.loadId && <Button variant="secondary" disabled={editor.busy} onClick={() => editor.open(editor.loadId!)}>Загрузить серверную версию</Button>}</div>}
    {catalog.isPending || editor.loading ? <LoadingState label="Загрузка Студии" /> : catalog.isError ? <ErrorState title="Каталог недоступен" message="Не удалось получить сценарии. Проверьте соединение и повторите." onRetry={() => void catalog.refetch()} /> : catalog.data && <>
      {categoryEditor ? <ScenarioCategoryForm key={categoryEditor} catalog={catalog.data} category={catalog.data.categories.find(item => item.id === categoryEditor)} onDirty={setCategoryDirty} onCancel={() => setCategoryEditor(null)} onDone={async () => { await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); setCategoryEditor(null); }} /> : editing && editor.definition ? <>
        <ScenarioWizard key={editor.detail?.scenario.id ?? "new"} definition={editor.definition} detail={editor.detail} catalog={catalog.data} disabled={!canEdit || editor.busy || !!editor.detail?.scenario.archived} simulationDisabled={editor.busy || !!editor.detail?.scenario.archived || !(canEdit || session?.actor_role === "auditor")} dirty={editor.dirty} onChange={editor.change} onAccept={editor.accept} onCategoryDirty={setCategoryDirty} onCategoryOpen={setInlineCategoryOpen} onCategoryCreated={async () => { await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }} />
        {canEdit && editor.detail && <div className="flex flex-wrap gap-2"><Button variant="ghost" disabled={editor.busy || editor.dirty || inlineCategoryOpen} onClick={() => editor.create(editor.definition!)}>Создать копию</Button>{!editor.detail.scenario.archived && <Button variant="ghost" disabled={editor.busy || editor.dirty || inlineCategoryOpen} onClick={() => setConfirm("archive")}>Архивировать сценарий</Button>}</div>}
      </> : offeringCode ? <OfferingDetails data={catalog.data} code={offeringCode} canEdit={canEdit} onOpen={item => void editor.open(item.id)} onCreate={createForOffering} /> : <ScenarioCatalogExplorer data={catalog.data} query={query} status={status} category={category} canEdit={canEdit} onQuery={value => { setQuery(value); setOffset(0); }} onStatus={value => { setStatus(value); setOffset(0); }} onCategory={value => { setCategory(value); setOffset(0); }} onOpen={item => void editor.open(item.id)} onCreateForOffering={offering => editor.create({ scenario_key: "new_scenario", service_code: offering.service_code ?? "", offering_full_code: offering.full_code, title: offering.public_title, blocks: [], process_binding: { request_template_key: offering.request_template_key ?? "" } }, false)} onEditCategory={setCategoryEditor} onPage={setOffset} />}
    </>}
    {confirm && <div role="alert" className="rounded-xl border border-amber-300 p-4"><p>{confirm === "leave" ? "Уйти без сохранения локальных изменений?" : "Архивировать сценарий? Новые пользовательские сеансы будут недоступны."}</p><div className="mt-3 flex flex-wrap gap-2"><Button disabled={editor.busy} onClick={() => { if (confirm === "leave") editor.close(); else editor.archive.mutate(); setConfirm(null); }}>{confirm === "leave" ? "Уйти без сохранения" : "Подтвердить архивирование"}</Button><Button variant="ghost" onClick={() => setConfirm(null)}>Отмена</Button></div></div>}
  </PageShell>;
}
